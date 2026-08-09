"""
Tests for src/pricing_engine.py (Phase G, rung G3).

Covers the full MODULES.md set (catalog, discounts, engine, validation,
currency, shipping, notifications, tax, loyalty, reporting, audit_log,
inventory), the G2+ order-lifecycle state machine, and the G3+ shared
audit-log entry helper (_audit_entry) threaded through reserve_stock,
redeem_loyalty_points, confirm_order, and apply_coupon.

Tiebreaker note (coupon-order contradiction): this file pins the
"volume, then membership, then coupon-last" resolution. That is the order
actually IMPLEMENTED (not just described) by the precedent at
../../phaseE-leaf-ceiling-v2/rungs/E5/src/discounts.py's stack_discounts,
and it also matches engine.py's own MODULES.md description
("coupon applied to the post-membership amount"). See
test_stack_discounts_numerically_pins_coupon_last_order below for the
numerically discriminating case (the two orders diverge by a cent once
rounding is applied at each stacking step, so this is not a case where
both orders coincidentally agree).

Standalone functions (per leaf-G3 brief) get plain state-check tests only,
no interaction/spy machinery: low_stock_alert, summarize_orders,
release_stock.
"""
import pytest

import pricing_engine as pe


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_audit_log():
    pe.AUDIT_LOG.clear()
    yield
    pe.AUDIT_LOG.clear()


def _fresh_catalog():
    return {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }


def _valid_order(**overrides):
    order = {
        "order_id": "ORD-777",
        "items": [{"sku": "widget", "qty": 5}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }
    order.update(overrides)
    return order


# ---------------------------------------------------------------------------
# catalog.py
# ---------------------------------------------------------------------------

def test_build_line_items_happy_path():
    per_sku, subtotal, total_qty = pe.build_line_items(
        [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    )
    assert per_sku == {"widget": 29.97, "gadget": 49.0}
    assert subtotal == 78.97
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        pe.build_line_items([{"sku": "nonexistent", "qty": 1}])


def test_build_line_items_qty_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        pe.build_line_items([{"sku": "gadget", "qty": 999}])


# ---------------------------------------------------------------------------
# discounts.py
# ---------------------------------------------------------------------------

def test_volume_discount_rate_bands():
    assert pe.volume_discount_rate(0) == 0.0
    assert pe.volume_discount_rate(9) == 0.0
    assert pe.volume_discount_rate(10) == 0.05
    assert pe.volume_discount_rate(49) == 0.05
    assert pe.volume_discount_rate(50) == 0.10


def test_membership_discount_rate_known_tiers():
    assert pe.membership_discount_rate("none") == 0.0
    assert pe.membership_discount_rate("silver") == 0.03
    assert pe.membership_discount_rate("gold") == 0.07
    assert pe.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        pe.membership_discount_rate("diamond")


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "NOTACODE")


def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(pe.COUPONS, "SAVE10", {**pe.COUPONS["SAVE10"], "expired": True})
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "SAVE10")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_applies_rate():
    assert pe.apply_coupon(100.0, "SAVE10") == 90.0


def test_stack_discounts_numerically_pins_coupon_last_order():
    # subtotal=333.33, total_qty=20 -> volume rate 0.05, tier="silver" -> 0.03,
    # coupon SAVE10 -> 0.10. Rounding at each stacking step makes the two
    # contradictory orders diverge by a cent:
    #   volume -> membership -> coupon-last:  333.33 -> 316.66 -> 307.16 -> 276.44
    #   coupon-first -> volume -> membership: 333.33 -> 300.00 -> 285.00 -> 276.45
    # This test pins the coupon-last resolution (276.44), matching the
    # precedent implementation and engine.py's own description.
    result = pe.stack_discounts(333.33, 20, "silver", coupon_code="SAVE10")
    assert result == 276.44
    assert result != 276.45  # explicitly rules out the coupon-first order


def test_stack_discounts_no_coupon():
    # volume 0.05 then membership 0.03, no coupon involved at all.
    result = pe.stack_discounts(333.33, 20, "silver", coupon_code=None)
    assert result == 307.16


# ---------------------------------------------------------------------------
# validation.py + G2+ state machine on validate_order
# ---------------------------------------------------------------------------

def test_validate_order_missing_region_raises():
    order = _valid_order()
    del order["region"]
    with pytest.raises(ValueError):
        pe.validate_order(order)


def test_validate_order_empty_items_raises():
    order = _valid_order(items=[])
    with pytest.raises(ValueError):
        pe.validate_order(order)


def test_validate_order_happy_path_transitions_draft_to_validated():
    order = _valid_order()
    assert order.get("state", "draft") == "draft"
    result = pe.validate_order(order)
    assert result is None
    assert order["state"] == "validated"


@pytest.mark.parametrize("wrong_state", ["validated", "priced", "confirmed", "shipped"])
def test_validate_order_wrong_state_rejected(wrong_state):
    order = _valid_order(state=wrong_state)
    with pytest.raises(ValueError, match="draft"):
        pe.validate_order(order)
    assert order["state"] == wrong_state  # rejected calls must not mutate state


# ---------------------------------------------------------------------------
# currency.py
# ---------------------------------------------------------------------------

def test_convert_known_currencies():
    assert pe.convert(100.0, "USD") == 100.0
    assert pe.convert(100.0, "EUR") == 92.0
    assert pe.convert(100.0, "GBP") == 79.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        pe.convert(100.0, "JPY")


def test_format_currency():
    assert pe.format_currency(12.5, "USD") == "$12.50"
    assert pe.format_currency(12.5, "EUR") == "€12.50"
    assert pe.format_currency(12.5, "GBP") == "£12.50"


# ---------------------------------------------------------------------------
# shipping.py
# ---------------------------------------------------------------------------

def test_shipping_cost_standard():
    assert pe.shipping_cost(2.0, 10.0, express=False) == round(2.5 + 0.8 + 0.5, 2)


def test_shipping_cost_express_multiplies():
    standard = pe.shipping_cost(2.0, 10.0, express=False)
    express = pe.shipping_cost(2.0, 10.0, express=True)
    assert express == round(standard * 1.5, 2)


def test_shipping_cost_nonpositive_raises():
    with pytest.raises(ValueError):
        pe.shipping_cost(0, 10.0, express=False)
    with pytest.raises(ValueError):
        pe.shipping_cost(2.0, -1.0, express=False)


# ---------------------------------------------------------------------------
# notifications.py -- standalone
# ---------------------------------------------------------------------------

def test_low_stock_alert_standalone():
    catalog = _fresh_catalog()
    assert pe.low_stock_alert(catalog, threshold=10) == ["gadget", "gizmo"]


def test_low_stock_alert_narrow_threshold():
    # MECHANICAL FIX (overlord-applied, recorded per 3.4.3): the original
    # assertion here was `== []` at threshold=1, but gizmo's stock is 0 and
    # "strictly below threshold" means 0 < 1 is True — gizmo must appear.
    # This was an objectively wrong expected value (0 < 1 is unambiguous
    # per MODULES.md's own spec text), not a design-decision ambiguity, so
    # it's fixed directly rather than routed back through a fresh
    # test-writer spawn. Caught by the builder (a real impl faithfully
    # following the spec could not satisfy the original assertion), not by
    # either the test-writer or the fresh test-auditor — a genuine gap in
    # this pass's audit coverage, logged for the Phase G report.
    catalog = _fresh_catalog()
    assert pe.low_stock_alert(catalog, threshold=1) == ["gizmo"]


# ---------------------------------------------------------------------------
# tax.py
# ---------------------------------------------------------------------------

def test_calculate_tax_known_regions():
    assert pe.calculate_tax(100.0, "US-CA") == 8.25
    assert pe.calculate_tax(100.0, "US-OR") == 0.0
    assert pe.calculate_tax(100.0, "US-NY") == 8.88
    assert pe.calculate_tax(100.0, "EU") == 20.0


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        pe.calculate_tax(100.0, "US-TX")


# ---------------------------------------------------------------------------
# reporting.py -- standalone
# ---------------------------------------------------------------------------

def test_summarize_orders_empty():
    assert pe.summarize_orders([]) == {"order_count": 0, "total_revenue": 0.0}


def test_summarize_orders_totals():
    orders = [{"total": 10.5}, {"total": 20.25}, {"total": 5.0}]
    result = pe.summarize_orders(orders)
    assert result == {"order_count": 3, "total_revenue": 35.75}


# ---------------------------------------------------------------------------
# audit_log.py -- record() is distinct from the G3+ _audit_entry helper
# ---------------------------------------------------------------------------

def test_audit_log_starts_empty():
    assert pe.AUDIT_LOG == []


def test_record_appends_order_id_total_shape():
    pe.record("ORD-1", 42.5)
    assert len(pe.AUDIT_LOG) == 1
    entry = pe.AUDIT_LOG[0]
    assert set(entry.keys()) == {"order_id", "total"}
    assert entry["order_id"] == "ORD-1"
    assert entry["total"] == 42.5


# ---------------------------------------------------------------------------
# inventory.py
# ---------------------------------------------------------------------------

def test_reserve_stock_decrements():
    catalog = _fresh_catalog()
    pe.reserve_stock(catalog, "widget", 10)
    assert catalog["widget"]["stock"] == 90


def test_reserve_stock_going_negative_raises():
    catalog = _fresh_catalog()
    with pytest.raises(ValueError):
        pe.reserve_stock(catalog, "gadget", 999)


def test_reserve_stock_unknown_sku_raises_keyerror():
    catalog = _fresh_catalog()
    with pytest.raises(KeyError):
        pe.reserve_stock(catalog, "nonexistent", 1)


def test_release_stock_standalone_increments():
    catalog = _fresh_catalog()
    pe.release_stock(catalog, "gizmo", 5)
    assert catalog["gizmo"]["stock"] == 5


def test_release_stock_unknown_sku_raises_keyerror():
    catalog = _fresh_catalog()
    with pytest.raises(KeyError):
        pe.release_stock(catalog, "nonexistent", 1)


# ---------------------------------------------------------------------------
# loyalty.py
# ---------------------------------------------------------------------------

def test_redeem_loyalty_points_normal():
    result = pe.redeem_loyalty_points(20.0, 500, 100)
    assert result == 19.0


def test_redeem_loyalty_points_floors_at_zero():
    result = pe.redeem_loyalty_points(5.0, 1000, 1000)
    assert result == 0.0


def test_redeem_loyalty_points_over_available_raises():
    with pytest.raises(ValueError):
        pe.redeem_loyalty_points(20.0, 100, 200)


def test_redeem_loyalty_points_negative_raises():
    with pytest.raises(ValueError):
        pe.redeem_loyalty_points(20.0, 100, -5)


# ---------------------------------------------------------------------------
# engine.py -- build_invoice orchestration + return contract
# ---------------------------------------------------------------------------

def test_build_invoice_returns_post_discount_amount_and_total():
    order = _valid_order()
    result = pe.build_invoice(order)
    assert "post_discount_amount" in result
    assert "total" in result


# ---------------------------------------------------------------------------
# G2+ order-lifecycle state machine (draft -> validated -> priced ->
# confirmed -> shipped), happy path + wrong-state rejection across states.
# ---------------------------------------------------------------------------

def test_lifecycle_happy_path_full_chain():
    order = _valid_order()
    assert order.get("state", "draft") == "draft"

    pe.build_invoice(order)
    assert order["state"] == "priced"

    confirmed = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert confirmed is order

    shipped = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert shipped is order


@pytest.mark.parametrize("wrong_state", ["priced", "confirmed", "shipped"])
def test_build_invoice_pricing_wrong_state_rejected(wrong_state):
    order = _valid_order(state=wrong_state)
    with pytest.raises(ValueError):
        pe.build_invoice(order)


@pytest.mark.parametrize("wrong_state", ["draft", "validated", "confirmed", "shipped"])
def test_confirm_order_wrong_state_rejected(wrong_state):
    order = _valid_order(state=wrong_state)
    with pytest.raises(ValueError, match="priced"):
        pe.confirm_order(order)
    assert order["state"] == wrong_state


@pytest.mark.parametrize("wrong_state", ["draft", "validated", "priced", "shipped"])
def test_ship_order_wrong_state_rejected(wrong_state):
    order = _valid_order(state=wrong_state)
    with pytest.raises(ValueError, match="confirmed"):
        pe.ship_order(order)
    assert order["state"] == wrong_state


def test_confirm_order_correct_state_transitions():
    order = _valid_order(state="priced")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_ship_order_correct_state_transitions():
    order = _valid_order(state="confirmed")
    result = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert result is order


# ---------------------------------------------------------------------------
# G3+ shared audit-log entry helper -- INTERACTION test.
#
# This does not just check "AUDIT_LOG grew" (a state-only check any
# independently-inlined dict literal would also satisfy). It replaces
# pricing_engine._audit_entry itself with a spy that returns a distinctive
# sentinel object per call, then asserts the objects appended to AUDIT_LOG
# by each of the four mutators ARE (by identity) the exact sentinel objects
# the spy returned. That is only possible if each call site genuinely calls
# through to the module-level _audit_entry and appends its return value --
# four independently-inlined dict literals with a matching shape would
# never produce entries that are identical objects to the spy's return
# values, so this discriminates a real shared call site from convergent
# inlined copies.
# ---------------------------------------------------------------------------

def test_four_mutators_call_through_shared_audit_entry_helper(monkeypatch):
    calls = []
    sentinels = []

    def fake_audit_entry(action, order_id, detail):
        sentinel = {"action": action, "order_id": order_id, "detail": detail}
        calls.append((action, order_id, detail))
        sentinels.append(sentinel)
        return sentinel

    monkeypatch.setattr(pe, "_audit_entry", fake_audit_entry)

    catalog = _fresh_catalog()
    pe.reserve_stock(catalog, "widget", 5)
    pe.redeem_loyalty_points(20.0, 500, 100)
    order = _valid_order(state="priced")
    pe.confirm_order(order)
    pe.apply_coupon(100.0, "SAVE10")

    # Exactly one call to the shared helper per mutator invocation.
    assert len(calls) == 4
    assert len(pe.AUDIT_LOG) == 4

    # Every entry actually appended to AUDIT_LOG is the very object the
    # shared helper returned for that call, in call order -- proving the
    # mutators append the helper's return value rather than building their
    # own dict.
    for logged_entry, sentinel in zip(pe.AUDIT_LOG, sentinels):
        assert logged_entry is sentinel

    # Every logged entry has exactly the helper's declared shape: no more,
    # no fewer keys, regardless of which of the four call sites produced it.
    for logged_entry in pe.AUDIT_LOG:
        assert set(logged_entry.keys()) == {"action", "order_id", "detail"}

    # The four call sites are genuinely distinct call sites (not the same
    # action logged four times) ...
    actions = [action for action, _order_id, _detail in calls]
    assert len(set(actions)) == 4
    assert all(isinstance(a, str) and a for a in actions)

    # ... while the confirm_order call specifically threads the real
    # order's own id through to the helper (order_id varies correctly with
    # the call, it isn't a constant baked into the helper usage).
    confirm_call = calls[2]
    assert confirm_call[1] == "ORD-777"


def test_audit_entry_helper_return_shape_directly():
    entry = pe._audit_entry("reserve_stock", "ORD-42", {"sku": "widget", "qty": 5})
    assert entry == {
        "action": "reserve_stock",
        "order_id": "ORD-42",
        "detail": {"sku": "widget", "qty": 5},
    }
    assert set(entry.keys()) == {"action", "order_id", "detail"}

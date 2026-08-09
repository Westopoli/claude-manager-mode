"""
Tests for src/pricing_engine.py (rung G4).

This single file must cover everything G3 covers (all 12 base modules from
MODULES.md, the order-lifecycle state machine, and the shared _audit_entry
helper used at 4 mutator call sites) PLUS G4's multi-currency settlement
feature on confirm_order.

Two seeded intra-file contradictions are pinned here, each with a numerically
discriminating test (see the dedicated sections below for the tiebreaker
reasoning):

1. Coupon-order contradiction (carried from all prior rungs): discounts.py's
   comment says "coupon first, then volume, then membership"; engine.py's
   comment says "volume discount, then membership discount, then coupon
   last", explicitly claiming to match "the canonical order used elsewhere
   in this system". TIEBREAKER: coupon-last wins, because engine.py's
   comment is the one that asserts system-wide consistency; discounts.py's
   comment makes no such claim about the rest of the system.

2. Currency-timing contradiction (new in G4, no prior-phase precedent): one
   comment near convert()/format_currency() says conversion happens "as the
   very last step, after total is finalized"; a comment on confirm_order
   says conversion happens "before tax is applied, so tax is computed in
   the settlement currency". TIEBREAKER: convert-last wins. Reasoning: the
   order-lifecycle state machine requires state "priced" before
   confirm_order can even run, and pricing (the part of build_invoice that
   computes total, including tax) already completed and transitioned the
   order out of "validated" by the time confirm_order executes. Tax was
   therefore already finalized, in USD, at the pricing stage -- a stage
   that has already run and cannot be re-entered from confirm_order without
   duplicating tax logic across two call sites with no state-machine
   sanction for doing so. Converting the already-finalized total as
   confirm_order's last step treats currency conversion as a presentation
   step layered on top of a pipeline the state machine says is already
   done, which is the reading consistent with the lifecycle contract this
   file itself enforces elsewhere. The "before tax" comment would require
   confirm_order to reach backward into a stage it has no state-machine
   permission to redo.
"""
import pytest

import pricing_engine as pe


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_audit_log():
    pe.AUDIT_LOG.clear()
    yield
    pe.AUDIT_LOG.clear()


@pytest.fixture
def fresh_catalog():
    return {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }


# ---------------------------------------------------------------------------
# catalog.py behavior
# ---------------------------------------------------------------------------

def test_build_line_items_normal():
    per_sku, subtotal, total_qty = pe.build_line_items([{"sku": "widget", "qty": 3}])
    assert per_sku == {"widget": 29.97}
    assert subtotal == 29.97
    assert total_qty == 3


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        pe.build_line_items([{"sku": "does-not-exist", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        pe.build_line_items([{"sku": "gizmo", "qty": 1}])  # gizmo stock is 0


# ---------------------------------------------------------------------------
# discounts.py behavior (excluding the coupon-order contradiction, see below)
# ---------------------------------------------------------------------------

def test_volume_discount_rate_bands():
    assert pe.volume_discount_rate(5) == 0.0
    assert pe.volume_discount_rate(9) == 0.0
    assert pe.volume_discount_rate(10) == 0.05
    assert pe.volume_discount_rate(49) == 0.05
    assert pe.volume_discount_rate(50) == 0.10


def test_membership_discount_rate_values():
    assert pe.membership_discount_rate("none") == 0.0
    assert pe.membership_discount_rate("silver") == 0.03
    assert pe.membership_discount_rate("gold") == 0.07
    assert pe.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_raises():
    with pytest.raises(ValueError):
        pe.membership_discount_rate("diamond")


def test_apply_coupon_normal():
    assert pe.apply_coupon(100.0, "SAVE10", "ORD-COUPON-1") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "NOPE", "ORD-COUPON-2")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(10.0, "SAVE10", "ORD-COUPON-3")  # min_spend is 50.0


def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(pe.COUPONS["SAVE10"], "expired", True)
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "SAVE10", "ORD-COUPON-4")


# ---------------------------------------------------------------------------
# CONTRADICTION 1: coupon-order. Pinned to coupon-last (see module docstring
# for the tiebreaker reasoning). The two candidate numeric results below
# differ by a cent, so this genuinely discriminates rather than coincidentally
# matching either interpretation.
# ---------------------------------------------------------------------------

def test_coupon_order_contradiction_pinned_to_coupon_last():
    subtotal = 123.45
    total_qty = 12          # -> volume_discount_rate = 0.05
    tier = "silver"         # -> membership_discount_rate = 0.03
    coupon_code = "SAVE10"  # -> rate 0.10, min_spend 50.0, not expired

    result = pe.stack_discounts(subtotal, total_qty, tier, coupon_code)

    coupon_last_result = 102.38   # volume, then membership, then coupon last
    coupon_first_result = 102.39  # coupon first, then volume, then membership

    assert coupon_last_result != coupon_first_result, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result == coupon_last_result
    assert result != coupon_first_result


# ---------------------------------------------------------------------------
# engine.py / order-lifecycle state machine (G2+)
# ---------------------------------------------------------------------------

def test_order_defaults_to_draft_state():
    order = {"items": [], "region": "US-CA", "membership_tier": "none", "currency": "USD"}
    assert order.get("state", "draft") == "draft"


def test_build_invoice_requires_validated_state():
    order = {
        "state": "draft",
        "items": [{"sku": "widget", "qty": 12}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }
    with pytest.raises(ValueError, match="validated"):
        pe.build_invoice(order)


def test_validate_order_requires_draft_state():
    order = {
        "state": "validated",
        "items": [{"sku": "widget", "qty": 1}],
        "region": "US-CA",
        "membership_tier": "none",
        "currency": "USD",
    }
    with pytest.raises(ValueError, match="draft"):
        pe.validate_order(order)


def test_validate_order_missing_fields_raise_valueerror():
    with pytest.raises(ValueError, match="items"):
        pe.validate_order({"region": "US-CA", "membership_tier": "none", "currency": "USD"})
    with pytest.raises(ValueError, match="region"):
        pe.validate_order({"items": [{"sku": "widget", "qty": 1}], "membership_tier": "none", "currency": "USD"})
    with pytest.raises(ValueError, match="membership_tier"):
        pe.validate_order({"items": [{"sku": "widget", "qty": 1}], "region": "US-CA", "currency": "USD"})
    with pytest.raises(ValueError, match="currency"):
        pe.validate_order({"items": [{"sku": "widget", "qty": 1}], "region": "US-CA", "membership_tier": "none"})


def test_full_order_lifecycle_happy_path():
    order = {
        "order_id": "ORD-LIFECYCLE-1",
        "items": [{"sku": "widget", "qty": 12}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }

    # draft -> validated
    pe.validate_order(order)
    assert order["state"] == "validated"

    # validated -> priced
    invoice = pe.build_invoice(order)
    assert order["state"] == "priced"
    assert "post_discount_amount" in invoice
    assert "total" in invoice
    assert isinstance(invoice["post_discount_amount"], float)
    assert isinstance(invoice["total"], float)
    assert invoice["total"] >= invoice["post_discount_amount"]

    # priced -> confirmed
    confirmed = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert confirmed is order

    # confirmed -> shipped
    shipped = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert shipped is order


def test_confirm_order_requires_priced_state():
    order = {"order_id": "ORD-BAD-1", "state": "validated"}
    with pytest.raises(ValueError, match="priced"):
        pe.confirm_order(order)


def test_ship_order_requires_confirmed_state():
    order = {"order_id": "ORD-BAD-2", "state": "priced"}
    with pytest.raises(ValueError, match="confirmed"):
        pe.ship_order(order)


# ---------------------------------------------------------------------------
# validation.py / currency.py / shipping.py / notifications.py (E2-E3)
# ---------------------------------------------------------------------------

def test_convert_known_currencies():
    assert pe.convert(100.0, "EUR") == 92.0
    assert pe.convert(100.0, "GBP") == 79.0
    assert pe.convert(100.0, "USD") == 100.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        pe.convert(100.0, "ZZZ")


def test_format_currency():
    assert pe.format_currency(9.5, "USD") == "$9.50"
    assert pe.format_currency(9.5, "EUR") == "€9.50"
    assert pe.format_currency(9.5, "GBP") == "£9.50"


def test_shipping_cost_normal_and_express():
    base = pe.shipping_cost(1.0, 10.0, False)
    assert base == 3.4
    express = pe.shipping_cost(1.0, 10.0, True)
    assert express == 5.1


def test_shipping_cost_nonpositive_raises():
    with pytest.raises(ValueError):
        pe.shipping_cost(0.0, 10.0, False)
    with pytest.raises(ValueError):
        pe.shipping_cost(1.0, 0.0, False)


def test_low_stock_alert(fresh_catalog):
    fresh_catalog["widget"]["stock"] = 5
    fresh_catalog["gadget"]["stock"] = 20
    fresh_catalog["gizmo"]["stock"] = 9
    assert pe.low_stock_alert(fresh_catalog, 10) == ["gizmo", "widget"]


# ---------------------------------------------------------------------------
# tax.py / loyalty.py (E4)
# ---------------------------------------------------------------------------

def test_calculate_tax_known_regions():
    assert pe.calculate_tax(100.0, "US-CA") == 8.25
    assert pe.calculate_tax(100.0, "US-OR") == 0.0
    assert pe.calculate_tax(100.0, "US-NY") == 8.88
    assert pe.calculate_tax(100.0, "EU") == 20.0


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        pe.calculate_tax(100.0, "US-TX")


def test_redeem_loyalty_points_normal():
    result = pe.redeem_loyalty_points(100.0, 500, 200, "ORD-LOYALTY-1")
    assert result == 98.0


def test_redeem_loyalty_points_over_redeem_raises():
    with pytest.raises(ValueError):
        pe.redeem_loyalty_points(100.0, 100, 200, "ORD-LOYALTY-2")


def test_redeem_loyalty_points_negative_raises():
    with pytest.raises(ValueError):
        pe.redeem_loyalty_points(100.0, 500, -10, "ORD-LOYALTY-3")


def test_redeem_loyalty_points_floors_at_zero():
    result = pe.redeem_loyalty_points(1.0, 1000, 1000, "ORD-LOYALTY-4")
    assert result == 0.0


# ---------------------------------------------------------------------------
# reporting.py / audit_log.py / inventory.py (E5) -- ordinary state checks
# ---------------------------------------------------------------------------

def test_summarize_orders_normal():
    orders = [{"total": 100.0}, {"total": 50.5}]
    assert pe.summarize_orders(orders) == {"order_count": 2, "total_revenue": 150.5}


def test_summarize_orders_empty():
    assert pe.summarize_orders([]) == {"order_count": 0, "total_revenue": 0.0}


def test_audit_log_starts_empty_and_record_appends():
    assert pe.AUDIT_LOG == []
    pe.record("ORD-RECORD-1", 42.0)
    assert pe.AUDIT_LOG == [{"order_id": "ORD-RECORD-1", "total": 42.0}]


def test_reserve_stock_decrements(fresh_catalog):
    pe.reserve_stock(fresh_catalog, "widget", 5, "ORD-INV-1")
    assert fresh_catalog["widget"]["stock"] == 95


def test_reserve_stock_over_stock_raises(fresh_catalog):
    with pytest.raises(ValueError):
        pe.reserve_stock(fresh_catalog, "widget", 1000, "ORD-INV-2")


def test_reserve_stock_unknown_sku_raises(fresh_catalog):
    with pytest.raises(KeyError):
        pe.reserve_stock(fresh_catalog, "nope", 1, "ORD-INV-3")


def test_release_stock_increments(fresh_catalog):
    pe.release_stock(fresh_catalog, "widget", 5)
    assert fresh_catalog["widget"]["stock"] == 105


def test_release_stock_unknown_sku_raises(fresh_catalog):
    with pytest.raises(KeyError):
        pe.release_stock(fresh_catalog, "nope", 1)


# ---------------------------------------------------------------------------
# G3: shared _audit_entry helper, used at all 4 mutator call sites
# ---------------------------------------------------------------------------

def test_audit_entry_helper_shape():
    entry = pe._audit_entry("some_action", "ORD-HELPER-1", {"x": 1})
    assert entry == {"action": "some_action", "order_id": "ORD-HELPER-1", "detail": {"x": 1}}


def _assert_well_shaped_audit_entry(entry, expected_order_id):
    assert set(entry.keys()) == {"action", "order_id", "detail"}
    assert isinstance(entry["action"], str) and entry["action"] != ""
    assert entry["order_id"] == expected_order_id
    assert isinstance(entry["detail"], dict)


def test_reserve_stock_appends_audit_entry(fresh_catalog):
    before = len(pe.AUDIT_LOG)
    pe.reserve_stock(fresh_catalog, "widget", 3, "ORD-AUDIT-1")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-AUDIT-1")


def test_redeem_loyalty_points_appends_audit_entry():
    before = len(pe.AUDIT_LOG)
    pe.redeem_loyalty_points(50.0, 500, 100, "ORD-AUDIT-2")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-AUDIT-2")


def test_apply_coupon_appends_audit_entry():
    before = len(pe.AUDIT_LOG)
    pe.apply_coupon(100.0, "SAVE10", "ORD-AUDIT-3")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-AUDIT-3")


def test_confirm_order_appends_audit_entry():
    order = {"order_id": "ORD-AUDIT-4", "state": "priced", "post_discount_amount": 100.0, "total": 110.0}
    before = len(pe.AUDIT_LOG)
    pe.confirm_order(order)
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-AUDIT-4")


def test_all_four_mutator_audit_entries_share_identical_shape(fresh_catalog):
    pe.reserve_stock(fresh_catalog, "widget", 1, "ORD-SHAPE-1")
    pe.redeem_loyalty_points(50.0, 500, 100, "ORD-SHAPE-1")
    pe.apply_coupon(100.0, "SAVE10", "ORD-SHAPE-1")
    order = {"order_id": "ORD-SHAPE-1", "state": "priced", "post_discount_amount": 100.0, "total": 110.0}
    pe.confirm_order(order)

    assert len(pe.AUDIT_LOG) == 4
    key_shapes = {frozenset(entry.keys()) for entry in pe.AUDIT_LOG}
    assert key_shapes == {frozenset({"action", "order_id", "detail"})}
    for entry in pe.AUDIT_LOG:
        assert entry["order_id"] == "ORD-SHAPE-1"
        assert isinstance(entry["detail"], dict)


# ---------------------------------------------------------------------------
# CONTRADICTION 2 (G4, new, no precedent): currency-conversion timing on
# confirm_order. Pinned to convert-last (see module docstring for the
# tiebreaker reasoning). The two candidate interpretations produce different
# cent-level settlement totals for the case below, so this genuinely
# discriminates.
#
# Setup: post_discount_amount = 123.45 USD, region = "EU" (tax rate 0.20),
# so pricing already finalized total = 123.45 + round(123.45*0.20, 2)
#                                     = 123.45 + 24.69 = 148.14 USD.
# settlement_currency = "EUR" (rate 0.92).
#
#   convert-last:       round(148.14 * 0.92, 2)                     = 136.29
#   convert-before-tax: pre = round(123.45 * 0.92, 2) = 113.57
#                        tax_settlement = round(113.57 * 0.20, 2) = 22.71
#                        round(113.57 + 22.71, 2)                    = 136.28
# ---------------------------------------------------------------------------

def test_currency_timing_contradiction_pinned_to_convert_last():
    order = {
        "order_id": "ORD-CURRENCY-1",
        "state": "priced",
        "region": "EU",
        "post_discount_amount": 123.45,
        "total": 148.14,  # already includes tax, finalized during pricing
    }

    result = pe.confirm_order(order, settlement_currency="EUR")

    convert_last_total = 136.29        # convert the already-finalized USD total
    convert_before_tax_total = 136.28  # convert pre-tax, then tax in settlement currency

    assert convert_last_total != convert_before_tax_total, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result["settlement_total"] == convert_last_total
    assert result["settlement_total"] != convert_before_tax_total
    assert result["settlement_currency"] == "EUR"
    assert result["settlement_total_formatted"] == pe.format_currency(convert_last_total, "EUR")
    assert order["state"] == "confirmed"


def test_confirm_order_without_settlement_currency_does_not_set_settlement_fields():
    order = {
        "order_id": "ORD-CURRENCY-2",
        "state": "priced",
        "region": "EU",
        "post_discount_amount": 123.45,
        "total": 148.14,
    }
    result = pe.confirm_order(order)
    assert "settlement_total" not in result
    assert "settlement_currency" not in result
    assert order["state"] == "confirmed"


def test_confirm_order_settlement_currency_unknown_raises():
    order = {
        "order_id": "ORD-CURRENCY-3",
        "state": "priced",
        "region": "EU",
        "post_discount_amount": 100.0,
        "total": 110.0,
    }
    with pytest.raises(ValueError):
        pe.confirm_order(order, settlement_currency="ZZZ")

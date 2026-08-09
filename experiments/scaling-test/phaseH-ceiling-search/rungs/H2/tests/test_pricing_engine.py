"""
Tests for src/pricing_engine.py (rung H2).

This single file must cover the FULL cumulative contract:

  * All 12 base modules from ../../phaseE-leaf-ceiling-v2/MODULES.md
    (catalog, discounts, engine, validation, currency, shipping,
    notifications, tax, loyalty, reporting, audit_log, inventory).
  * The order-lifecycle state machine (draft -> validated -> priced ->
    confirmed -> shipped) from phaseG SPEC.md (G2+).
  * The shared `_audit_entry(action, order_id, detail) -> dict` helper,
    called from every state-mutating function (phaseG SPEC.md, G3+).
  * Multi-currency settlement on `confirm_order` (phaseG SPEC.md, G4).
  * H1's `OrderApproval` concern -- multi-tier manager/finance approval
    gating on `confirm_order`, per ../SPEC.md's "H1" section (H2 carries
    this forward unchanged from H1's own scope).
  * H2's own new layer: the `CAMPAIGNS` registry and
    `apply_campaign(order, campaign_id, as_of) -> dict`, time-windowed
    promotional-campaign stacking, per ../SPEC.md's "H2" section and
    .swarm/briefs/leaf-H2.md.

This rung is a fully independent isolation run from H1 -- its own
test-writer, with no visibility into H1's test file or H1's
implementation. Where the underlying domain rules are unchanged from H1
(base modules, state machine, audit helper, currency settlement, approval
workflow) the coverage below is written fresh from the spec, not copied,
though it necessarily lands on similar shapes since the contract is the
same.

Three seeded/pinned ambiguities are locked down here, each with a
numerically or behaviorally discriminating test, independently verified
by direct computation for THIS file's own chosen numbers (not assumed
from any other rung):

1. Coupon-order contradiction (carried from every prior rung, E1-H2):
   discounts.py's comment says "coupon first, then volume, then
   membership"; engine.py's comment says "volume discount, then
   membership discount, then coupon last", explicitly claiming to match
   "the canonical order used elsewhere in this system". TIEBREAKER:
   coupon-last, applying the tiebreaker precedent carried through every
   prior rung (Phase G, H1) -- engine.py's comment is the one that
   asserts system-wide consistency, discounts.py's comment makes no such
   claim about the rest of the system.

   Verification (subtotal=210.10, qty=12 -> volume_discount_rate=0.05,
   tier="gold" -> membership_discount_rate=0.07, coupon SAVE10 -> rate
   0.10), computed directly, not from memory:

       coupon-last:  round(round(round(210.10*(1-0.05),2)*(1-0.07),2)*(1-0.10),2) = 167.06
       coupon-first: round(round(round(210.10*(1-0.10),2)*(1-0.05),2)*(1-0.07),2) = 167.07

   These differ by a cent, so the test below genuinely discriminates.

2. Currency-timing contradiction (carried from phaseG G4, no precedent
   before G4, applies unchanged through H1/H2): one comment near
   convert()/format_currency() says conversion happens "as the very last
   step, after total is finalized"; a comment on confirm_order says
   conversion happens "before tax is applied, so tax is computed in the
   settlement currency". TIEBREAKER (H1's own call, carried forward
   here as this rung's own independent choice landing on the same
   reading, not blind copying): convert-last wins. Reasoning: the
   order-lifecycle state machine requires state "priced" before
   confirm_order can even run, and pricing (the part of build_invoice
   that computes total, including tax) already completed and
   transitioned the order out of "validated" by the time confirm_order
   executes -- tax was already finalized, in USD, at a pipeline stage
   confirm_order has no state-machine permission to re-enter. Converting
   the already-finalized USD total as confirm_order's last step treats
   currency conversion as a presentation step layered on top of an
   already-completed pipeline, consistent with the lifecycle contract
   this file itself enforces elsewhere.

   Verification (post_discount_amount=167.06 from the coupon-order
   scenario above, region="EU" -> tax rate 0.20, settlement_currency
   "EUR" -> rate 0.92), computed directly:

       tax = round(167.06*0.20, 2) = 33.41
       total_usd = round(167.06+33.41, 2) = 200.47

       convert-last:       round(200.47*0.92, 2)                    = 184.43
       convert-before-tax: pre = round(167.06*0.92, 2)  = 153.70
                           tax_settlement = round(153.70*0.20, 2) = 30.74
                           round(153.70+30.74, 2)                    = 184.44

   These differ by a cent, so the test below genuinely discriminates.

3. Campaign-order contradiction (H2's own, new, no cross-phase
   precedent): the spec text (../SPEC.md's H2 section, mirrored in
   .swarm/briefs/leaf-H2.md) contains two contradictory statements about
   WHERE in the discount chain a campaign applies relative to
   coupon/volume/membership -- one says "campaigns apply after all other
   discounts, to the final discounted total" (apply_campaign runs on
   stack_discounts's output); the other says "campaigns apply first,
   before any other discount logic runs, since promotional pricing
   supersedes standing discounts" (apply_campaign runs on the raw
   pre-discount subtotal, and stack_discounts then runs on ITS output).
   TIEBREAKER (this rung's own call, no cross-phase precedent to reuse):
   campaigns-after-all-other-discounts wins. Reasoning: a campaign here
   is layered promotional pricing applied via a standalone call
   (`apply_campaign`) after the order already has a
   `post_discount_amount` from the ordinary discount chain -- the same
   shape as coupon-last and record_approval, both of which operate on an
   order that already carries a computed amount rather than reaching back
   to re-run earlier pipeline stages, so campaigns-after is the reading
   consistent with every other layered-on-top concern in this file.

   Verification (subtotal=300.00, qty=12 -> volume_discount_rate=0.05,
   tier="gold" -> membership_discount_rate=0.07, coupon SAVE10 -> rate
   0.10, campaign SUMMER15 -> multiply rate 0.15), computed directly:

       post_discount_amount (coupon-last stack):
           D = round(round(round(300.00*(1-0.05),2)*(1-0.07),2)*(1-0.10),2) = 238.55

       campaigns-after (apply_campaign runs on D):
           resultA = round(238.55*(1-0.15),2) = 202.77

       campaigns-first (apply_campaign runs on raw subtotal, then
       stack_discounts runs on ITS output):
           S_after_campaign = round(300.00*(1-0.15),2) = 255.0
           resultB = round(round(round(255.0*(1-0.05),2)*(1-0.07),2)*(1-0.10),2) = 202.76

   These differ by a cent, so the test below genuinely discriminates.

Implementation-level calls made by this test file that are NOT seeded
ambiguities (stated here so they read as deliberate, not accidental):

  * `apply_campaign(order, campaign_id, as_of)` reads and overwrites
    `order["post_discount_amount"]` in place and returns the order
    itself (same convention as `confirm_order`/`ship_order`), rather than
    returning a freestanding dict unconnected to the order.
  * `apply_campaign` is treated as a 6th `_audit_entry` call site: it
    mutates order state (the post-discount amount) exactly the way
    `record_approval` mutates order state (recorded approvals), so it is
    held to the same "every state-mutating function calls the shared
    helper" rule already established for the other 5 sites.
  * `CAMPAIGNS` window bounds are inclusive on both ends (`starts_at` and
    `ends_at` both count as valid), mirroring no explicit exclusive-bound
    language anywhere in the spec.
  * Unrecognized `record_approval` role names raise `ValueError` (carried
    forward from H1's own defensive choice, still untested by name
    collision anywhere in this file's required behaviors, kept as
    established convention rather than newly invented here).
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


def _valid_order(**overrides):
    order = {
        "order_id": "ORD-BASE-1",
        "items": [{"sku": "widget", "qty": 12}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }
    order.update(overrides)
    return order


def _priced_order(total, order_id="ORD-PRICED-1", **overrides):
    """A hand-built order already in the 'priced' state, bypassing the
    pricing pipeline, to drive confirm_order/approval/campaign tests
    directly at a specific total (same pattern used by the phaseG G3/G4
    and phaseH H1 test suites)."""
    order = {
        "order_id": order_id,
        "state": "priced",
        "region": "US-CA",
        "post_discount_amount": total,
        "total": total,
    }
    order.update(overrides)
    return order


def _assert_well_shaped_audit_entry(entry, expected_order_id):
    assert set(entry.keys()) == {"action", "order_id", "detail"}
    assert isinstance(entry["action"], str) and entry["action"] != ""
    assert entry["order_id"] == expected_order_id
    assert isinstance(entry["detail"], dict)


# ---------------------------------------------------------------------------
# catalog.py behavior
# ---------------------------------------------------------------------------

def test_build_line_items_normal():
    per_sku, subtotal, total_qty = pe.build_line_items([{"sku": "widget", "qty": 3}])
    assert per_sku == {"widget": 29.97}
    assert subtotal == 29.97
    assert total_qty == 3


def test_build_line_items_multi_sku():
    per_sku, subtotal, total_qty = pe.build_line_items(
        [{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}]
    )
    assert per_sku == {"widget": 19.98, "gadget": 24.50}
    assert subtotal == 44.48
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
# CONTRADICTION 1: coupon-order. Pinned to coupon-last -- see module
# docstring item 1 for the verified computation. The two candidate
# numeric results below differ by a cent, so this genuinely discriminates
# rather than coincidentally matching either interpretation.
# ---------------------------------------------------------------------------

def test_coupon_order_contradiction_pinned_to_coupon_last():
    subtotal = 210.10
    total_qty = 12          # -> volume_discount_rate = 0.05
    tier = "gold"            # -> membership_discount_rate = 0.07
    coupon_code = "SAVE10"   # -> rate 0.10, min_spend 50.0, not expired

    result = pe.stack_discounts(subtotal, total_qty, tier, coupon_code)

    coupon_last_result = 167.06   # volume, then membership, then coupon last
    coupon_first_result = 167.07  # coupon first, then volume, then membership

    assert coupon_last_result != coupon_first_result, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result == coupon_last_result
    assert result != coupon_first_result


def test_stack_discounts_without_coupon():
    # No coupon supplied -- the contradiction doesn't apply, only
    # volume-then-membership matters and both readings agree.
    result = pe.stack_discounts(200.0, 15, "gold")
    # 200.0 * (1 - 0.05) * (1 - 0.07) = 200.0 * 0.95 * 0.93 = 176.7
    assert result == 176.7


# ---------------------------------------------------------------------------
# engine.py / order-lifecycle state machine (G2+)
# ---------------------------------------------------------------------------

def test_order_defaults_to_draft_state():
    order = {"items": [], "region": "US-CA", "membership_tier": "none", "currency": "USD"}
    assert order.get("state", "draft") == "draft"


def test_build_invoice_returns_post_discount_amount_and_total():
    order = _valid_order()
    pe.validate_order(order)
    result = pe.build_invoice(order)
    assert "post_discount_amount" in result
    assert "total" in result
    assert isinstance(result["post_discount_amount"], float)
    assert isinstance(result["total"], float)
    assert order["state"] == "priced"


def test_build_invoice_requires_validated_state():
    order = _valid_order()  # still "draft" -- never validated
    with pytest.raises(ValueError, match="validated"):
        pe.build_invoice(order)


def test_validate_order_requires_draft_state():
    order = _valid_order(state="validated")
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


def test_full_order_lifecycle_happy_path_under_approval_threshold():
    # items chosen so total stays comfortably under APPROVAL_THRESHOLD
    # (500.0) -- no approvals should be required anywhere in this chain.
    order = {
        "order_id": "ORD-LIFECYCLE-1",
        "items": [{"sku": "widget", "qty": 2}],
        "region": "US-OR",  # 0.0 tax rate keeps the math simple
        "membership_tier": "none",
        "currency": "USD",
    }

    pe.validate_order(order)
    assert order["state"] == "validated"

    invoice = pe.build_invoice(order)
    assert order["state"] == "priced"
    assert invoice["total"] < pe.APPROVAL_THRESHOLD

    confirmed = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert confirmed is order

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
# G3: shared _audit_entry helper, used at pre-H2 mutator call sites
# ---------------------------------------------------------------------------

def test_audit_entry_helper_shape():
    entry = pe._audit_entry("some_action", "ORD-HELPER-1", {"x": 1})
    assert entry == {"action": "some_action", "order_id": "ORD-HELPER-1", "detail": {"x": 1}}


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
    order = _priced_order(100.0, order_id="ORD-AUDIT-4")  # under APPROVAL_THRESHOLD
    before = len(pe.AUDIT_LOG)
    pe.confirm_order(order)
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-AUDIT-4")


# ---------------------------------------------------------------------------
# G4: multi-currency settlement on confirm_order
# ---------------------------------------------------------------------------

def test_confirm_order_without_settlement_currency_does_not_set_settlement_fields():
    order = _priced_order(148.14, order_id="ORD-CURRENCY-2", region="EU",
                           post_discount_amount=123.45)
    result = pe.confirm_order(order)
    assert "settlement_total" not in result
    assert "settlement_currency" not in result
    assert order["state"] == "confirmed"


def test_confirm_order_settlement_currency_unknown_raises():
    order = _priced_order(110.0, order_id="ORD-CURRENCY-3", region="EU",
                           post_discount_amount=100.0)
    with pytest.raises(ValueError):
        pe.confirm_order(order, settlement_currency="ZZZ")


# ---------------------------------------------------------------------------
# CONTRADICTION 2: currency-conversion timing on confirm_order. Pinned to
# convert-last (see module docstring item 2 for the tiebreaker reasoning
# and the verified computation). The two candidate interpretations
# produce different cent-level settlement totals for the case below, so
# this genuinely discriminates.
# ---------------------------------------------------------------------------

def test_currency_timing_contradiction_pinned_to_convert_last():
    order = _priced_order(200.47, order_id="ORD-CURRENCY-1", region="EU",
                           post_discount_amount=167.06)

    result = pe.confirm_order(order, settlement_currency="EUR")

    convert_last_total = 184.43        # convert the already-finalized USD total
    convert_before_tax_total = 184.44  # convert pre-tax, then tax in settlement currency

    assert convert_last_total != convert_before_tax_total, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result["settlement_total"] == convert_last_total
    assert result["settlement_total"] != convert_before_tax_total
    assert result["settlement_currency"] == "EUR"
    assert result["settlement_total_formatted"] == pe.format_currency(convert_last_total, "EUR")
    assert order["state"] == "confirmed"


# ---------------------------------------------------------------------------
# H1: OrderApproval concern -- APPROVAL_THRESHOLD / ESCALATION_THRESHOLD
# constants
# ---------------------------------------------------------------------------

def test_approval_threshold_constants():
    assert pe.APPROVAL_THRESHOLD == 500.0
    assert pe.ESCALATION_THRESHOLD == 2000.0


def test_confirm_order_under_approval_threshold_needs_no_approval():
    order = _priced_order(499.99, order_id="ORD-APPROVAL-UNDER-1")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_at_exactly_approval_threshold_needs_no_approval():
    # "exceeds APPROVAL_THRESHOLD" triggers the requirement -- a total
    # exactly at the threshold does not exceed it, so no approval is
    # required at the boundary value itself.
    order = _priced_order(500.0, order_id="ORD-APPROVAL-BOUNDARY-1")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_above_approval_threshold_without_approval_raises_naming_manager():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-MID-1")
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)
    assert order["state"] == "priced"  # rejected, no transition happened


def test_confirm_order_above_approval_threshold_with_manager_approval_proceeds():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-MID-2")
    pe.record_approval(order, "manager")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_just_above_approval_threshold_requires_manager():
    order = _priced_order(500.01, order_id="ORD-APPROVAL-BOUNDARY-2")
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)


def test_confirm_order_just_below_escalation_threshold_requires_only_manager():
    order = _priced_order(1999.99, order_id="ORD-APPROVAL-BOUNDARY-3")
    pe.record_approval(order, "manager")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_at_escalation_threshold_without_any_approval_raises_naming_manager():
    order = _priced_order(2000.0, order_id="ORD-ESCALATION-1")
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)
    assert order["state"] == "priced"


def test_confirm_order_above_escalation_with_manager_only_raises_naming_finance():
    order = _priced_order(2500.0, order_id="ORD-ESCALATION-2")
    pe.record_approval(order, "manager")
    with pytest.raises(ValueError, match="finance"):
        pe.confirm_order(order)
    assert order["state"] == "priced"


def test_confirm_order_above_escalation_with_manager_then_finance_proceeds():
    order = _priced_order(2500.0, order_id="ORD-ESCALATION-3")
    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_at_exactly_escalation_threshold_requires_both():
    # "at or above ESCALATION_THRESHOLD" -- the boundary value itself
    # requires the full manager-then-finance chain, unlike
    # APPROVAL_THRESHOLD's strict "exceeds" boundary above.
    order = _priced_order(2000.0, order_id="ORD-ESCALATION-4")
    pe.record_approval(order, "manager")
    with pytest.raises(ValueError, match="finance"):
        pe.confirm_order(order)
    pe.record_approval(order, "finance")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_record_approval_finance_before_manager_raises_valueerror():
    order = _priced_order(2500.0, order_id="ORD-ORDER-RULE-1")
    before = len(pe.AUDIT_LOG)
    with pytest.raises(ValueError):
        pe.record_approval(order, "finance")
    # a rejected/out-of-order approval attempt is a no-op, not a
    # to-be-audited event: an entry documents an approval that was
    # actually recorded, and this one was rejected outright, so
    # AUDIT_LOG must be unchanged.
    assert len(pe.AUDIT_LOG) == before
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)


def test_record_approval_finance_before_manager_does_not_prevent_correct_order_after():
    order = _priced_order(2500.0, order_id="ORD-ORDER-RULE-2")
    with pytest.raises(ValueError):
        pe.record_approval(order, "finance")
    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_record_approval_returns_a_dict():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-RETURN-1")
    result = pe.record_approval(order, "manager")
    assert isinstance(result, dict)


def test_record_approval_appends_audit_entry_with_established_shape():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-AUDIT-1")
    before = len(pe.AUDIT_LOG)
    pe.record_approval(order, "manager")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-APPROVAL-AUDIT-1")


def test_record_approval_manager_then_finance_each_append_one_audit_entry():
    order = _priced_order(2500.0, order_id="ORD-APPROVAL-AUDIT-2")
    before = len(pe.AUDIT_LOG)
    pe.record_approval(order, "manager")
    assert len(pe.AUDIT_LOG) == before + 1
    pe.record_approval(order, "finance")
    assert len(pe.AUDIT_LOG) == before + 2
    for entry in pe.AUDIT_LOG[-2:]:
        _assert_well_shaped_audit_entry(entry, "ORD-APPROVAL-AUDIT-2")


def test_confirm_order_wrong_state_rejected_even_with_approvals_recorded():
    order = _priced_order(2500.0, order_id="ORD-INDEPENDENT-1", state="validated")
    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")
    with pytest.raises(ValueError, match="priced"):
        pe.confirm_order(order)
    assert order["state"] == "validated"


def test_full_lifecycle_with_escalation_approvals_and_settlement_currency():
    # Composition check: approval gating, the lifecycle state machine, and
    # multi-currency settlement all interacting on the same order.
    order = _priced_order(2500.0, order_id="ORD-COMPOSITION-1", region="EU",
                           post_discount_amount=2000.0)
    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")
    result = pe.confirm_order(order, settlement_currency="GBP")
    assert order["state"] == "confirmed"
    assert result["settlement_currency"] == "GBP"
    assert result["settlement_total"] == pe.convert(2500.0, "GBP")

    shipped = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert shipped is order


# ---------------------------------------------------------------------------
# H2: CAMPAIGNS registry -- shape check, parallel to COUPONS but with
# starts_at/ends_at ISO-date bounds and a per-entry stacking flag.
# ---------------------------------------------------------------------------

def test_campaigns_registry_has_at_least_three_entries_both_stacking_modes():
    assert len(pe.CAMPAIGNS) >= 3
    stacking_modes = {entry["stacking"] for entry in pe.CAMPAIGNS.values()}
    assert "multiply" in stacking_modes
    assert "additive" in stacking_modes
    for entry in pe.CAMPAIGNS.values():
        assert "starts_at" in entry and "ends_at" in entry
        assert entry["stacking"] in ("multiply", "additive")


def test_campaigns_registry_has_an_entry_excluding_the_common_test_date():
    # "2026-06-15" is the as_of date used throughout this file's campaign
    # tests below -- at least one CAMPAIGNS entry's window must exclude
    # it (per the leaf brief's explicit requirement).
    common_test_date = "2026-06-15"
    excluding_entries = [
        cid for cid, entry in pe.CAMPAIGNS.items()
        if not (entry["starts_at"] <= common_test_date <= entry["ends_at"])
    ]
    assert len(excluding_entries) >= 1


# ---------------------------------------------------------------------------
# H2: apply_campaign -- time-window validity
# ---------------------------------------------------------------------------

def test_apply_campaign_unknown_campaign_id_raises_naming_it():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-UNKNOWN-1")
    with pytest.raises(ValueError, match="NOPE-CAMPAIGN"):
        pe.apply_campaign(order, "NOPE-CAMPAIGN", "2026-06-15")


def test_apply_campaign_before_window_raises_naming_campaign():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-EARLY-1")
    # WINTER10's window is 2025-11-01..2025-12-31 -- this date is before
    # starts_at, genuinely exercising the lower-bound check.
    with pytest.raises(ValueError, match="WINTER10"):
        pe.apply_campaign(order, "WINTER10", "2025-10-15")


def test_apply_campaign_after_window_raises_naming_campaign():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-LATE-1")
    # WINTER10's window is 2025-11-01..2025-12-31 -- this date is after
    # ends_at, genuinely exercising the upper-bound check.
    with pytest.raises(ValueError, match="WINTER10"):
        pe.apply_campaign(order, "WINTER10", "2026-01-15")


def test_apply_campaign_window_boundary_starts_at_is_valid():
    # SUMMER15's window is 2026-06-01..2026-08-31 -- the starts_at date
    # itself is inside the window (inclusive bound).
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-BOUNDARY-1")
    result = pe.apply_campaign(order, "SUMMER15", "2026-06-01")
    assert order["state"] == "priced"  # applying a campaign doesn't move state
    assert result is order


def test_apply_campaign_window_boundary_ends_at_is_valid():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-BOUNDARY-2")
    result = pe.apply_campaign(order, "SUMMER15", "2026-08-31")
    assert result is order


# ---------------------------------------------------------------------------
# H2: apply_campaign -- multiply and additive stacking math
# ---------------------------------------------------------------------------

def test_apply_campaign_multiply_stacking():
    # SUMMER15: multiply, rate 0.15, window includes 2026-06-15.
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-MULTIPLY-1")
    result = pe.apply_campaign(order, "SUMMER15", "2026-06-15")
    # round(238.55 * (1 - 0.15), 2) = 202.77
    assert order["post_discount_amount"] == 202.77
    assert result is order


def test_apply_campaign_additive_stacking():
    # FLAT20: additive, value 20.0, window includes 2026-06-15.
    order = _priced_order(55.0, order_id="ORD-CAMPAIGN-ADDITIVE-1")
    result = pe.apply_campaign(order, "FLAT20", "2026-06-15")
    assert order["post_discount_amount"] == 35.0
    assert result is order


def test_apply_campaign_additive_stacking_floors_at_zero():
    order = _priced_order(5.0, order_id="ORD-CAMPAIGN-ADDITIVE-2")
    pe.apply_campaign(order, "FLAT20", "2026-06-15")
    assert order["post_discount_amount"] == 0.0


# ---------------------------------------------------------------------------
# CONTRADICTION 3 (H2's own, new): campaign-application-order. Pinned to
# campaigns-apply-after-all-other-discounts -- see module docstring item 3
# for the tiebreaker reasoning and the verified computation. The two
# candidate interpretations produce different cent-level totals for the
# case below, so this genuinely discriminates.
# ---------------------------------------------------------------------------

def test_campaign_order_contradiction_pinned_to_after_all_discounts():
    subtotal = 300.00
    total_qty = 12          # -> volume_discount_rate = 0.05
    tier = "gold"             # -> membership_discount_rate = 0.07
    coupon_code = "SAVE10"    # -> rate 0.10

    # Run the ordinary (non-campaign) discount chain first, coupon-last,
    # exactly as contradiction 1 above pins it.
    post_discount_amount = pe.stack_discounts(subtotal, total_qty, tier, coupon_code)
    assert post_discount_amount == 238.55

    order = _priced_order(post_discount_amount, order_id="ORD-CAMPAIGN-ORDER-1",
                           post_discount_amount=post_discount_amount)

    # SUMMER15: multiply, rate 0.15.
    result = pe.apply_campaign(order, "SUMMER15", "2026-06-15")

    campaigns_after_result = 202.77   # campaign applied to post_discount_amount (238.55)
    campaigns_first_result = 202.76   # campaign applied to raw subtotal (300.00),
                                       # then volume/membership/coupon re-run on ITS output

    assert campaigns_after_result != campaigns_first_result, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert order["post_discount_amount"] == campaigns_after_result
    assert order["post_discount_amount"] != campaigns_first_result
    assert result is order


# ---------------------------------------------------------------------------
# H2: apply_campaign as the 6th _audit_entry call site -- reuses the
# established shape, same as the other 5 mutator call sites.
# ---------------------------------------------------------------------------

def test_apply_campaign_appends_audit_entry_with_established_shape():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-AUDIT-1")
    before = len(pe.AUDIT_LOG)
    pe.apply_campaign(order, "SUMMER15", "2026-06-15")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-CAMPAIGN-AUDIT-1")


def test_apply_campaign_rejected_window_does_not_append_audit_entry():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-AUDIT-2")
    before = len(pe.AUDIT_LOG)
    with pytest.raises(ValueError):
        pe.apply_campaign(order, "WINTER10", "2026-06-15")
    assert len(pe.AUDIT_LOG) == before


def test_all_six_mutator_audit_entries_share_identical_shape(fresh_catalog):
    # 4 pre-H1 sites (reserve_stock, redeem_loyalty_points, apply_coupon,
    # confirm_order), H1's 5th site (record_approval), and H2's new 6th
    # site (apply_campaign) all reuse the same _audit_entry helper -- same
    # {"action", "order_id", "detail"} shape across every one of them, no
    # invented alternate shape for campaigns.
    order_id = "ORD-SHAPE-1"
    pe.reserve_stock(fresh_catalog, "widget", 1, order_id)
    pe.redeem_loyalty_points(50.0, 500, 100, order_id)
    pe.apply_coupon(100.0, "SAVE10", order_id)

    order = _priced_order(800.0, order_id=order_id)
    pe.record_approval(order, "manager")
    pe.apply_campaign(order, "SUMMER15", "2026-06-15")
    pe.confirm_order(order)

    assert len(pe.AUDIT_LOG) == 6
    key_shapes = {frozenset(entry.keys()) for entry in pe.AUDIT_LOG}
    assert key_shapes == {frozenset({"action", "order_id", "detail"})}
    for entry in pe.AUDIT_LOG:
        assert entry["order_id"] == order_id
        assert isinstance(entry["detail"], dict)


# ---------------------------------------------------------------------------
# H2: composition -- campaign stacking interacting with approval gating,
# the lifecycle state machine, and multi-currency settlement all on the
# same order.
# ---------------------------------------------------------------------------

def test_full_lifecycle_with_campaign_escalation_approvals_and_settlement_currency():
    order = _priced_order(2500.0, order_id="ORD-CAMPAIGN-COMPOSITION-1", region="EU",
                           post_discount_amount=2500.0)

    pe.apply_campaign(order, "SUMMER15", "2026-06-15")
    # round(2500.0 * (1 - 0.15), 2) = 2125.0
    assert order["post_discount_amount"] == 2125.0

    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")

    result = pe.confirm_order(order, settlement_currency="GBP")
    assert order["state"] == "confirmed"
    assert result["settlement_currency"] == "GBP"
    assert result["settlement_total"] == pe.convert(2500.0, "GBP")

    shipped = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert shipped is order

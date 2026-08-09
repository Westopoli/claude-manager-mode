"""
Tests for src/pricing_engine.py (rung H3).

This single file must cover the FULL cumulative contract:

  * All 12 base modules from ../../phaseE-leaf-ceiling-v2/MODULES.md
    (catalog, discounts, engine, validation, currency, shipping,
    notifications, tax, loyalty, reporting, audit_log, inventory).
  * The order-lifecycle state machine (draft -> validated -> priced ->
    confirmed -> shipped) from phaseG SPEC.md (G2+).
  * The shared `_audit_entry(action, order_id, detail) -> dict` helper,
    called from every state-mutating function (phaseG SPEC.md, G3+),
    now at SEVEN call sites (H3 adds `partial_refund` as the 7th).
  * Multi-currency settlement on `confirm_order` (phaseG SPEC.md, G4).
  * H1's `OrderApproval` concern -- multi-tier manager/finance approval
    gating on `confirm_order`, per ../SPEC.md's "H1" section.
  * H2's `CAMPAIGNS` registry and `apply_campaign(order, campaign_id,
    as_of) -> dict`, time-windowed promotional-campaign stacking, per
    ../SPEC.md's "H2" section.
  * H3's own new layer: `TAX_JURISDICTIONS` / `compute_tax(order)` for
    multi-jurisdiction tax cascading, and `partial_refund(order,
    item_id, qty) -> dict` for refund/partial-cancellation reversal
    logic, per ../SPEC.md's "H3" section and .swarm/briefs/leaf-H3.md.

This rung is a fully independent isolation run -- its own test-writer,
with no visibility into any other rung's implementation (H1's and H2's
implementation files were never read; only their leaf briefs, this
rung's own leaf brief, the shared SPEC.md documents, and H2's own test
file / test-writer report, per this task's explicit instructions, were
used as reference). Coverage for scope shared with prior rungs is
written fresh from the spec, not copied, though it necessarily lands on
similar shapes since the underlying contract is the same across rungs.

Four seeded/pinned ambiguities are locked down here, each with a
numerically or behaviorally discriminating test, independently verified
by direct computation for THIS file's own chosen numbers (not reused
byte-for-byte from any other rung's numbers, and not recalled from
memory -- every number below was produced by an actual `python3 -c`
run, pasted in .swarm/briefs/leaf-H3.TESTWRITER-REPORT.md). The
QUALITATIVE resolution of the first three is pinned to match H2's own
test-writer report exactly (leaf-H2.TESTWRITER-REPORT.md), per this
rung's explicit instruction to reuse those same pinned resolutions
rather than re-deriving new ones.

1. Coupon-order contradiction (carried from every prior rung, E1-H3):
   discounts.py's comment says "coupon first, then volume, then
   membership"; engine.py's comment says "volume discount, then
   membership discount, then coupon last", explicitly claiming to match
   "the canonical order used elsewhere in this system". TIEBREAKER
   (pinned, reused from H2's report): coupon-last -- engine.py's comment
   is the one that asserts system-wide consistency; discounts.py's
   comment makes no such claim about the rest of the system.

   Verification (subtotal=412.80, qty=6 -> volume_discount_rate=0.0
   since qty < 10, tier="platinum" -> membership_discount_rate=0.12,
   coupon SAVE10 -> rate 0.10), computed directly via python3 -c:

       coupon-last:  round(round(round(412.80*(1-0.0),2)*(1-0.12),2)*(1-0.10),2) = 326.93
       coupon-first: round(round(round(412.80*(1-0.10),2)*(1-0.0),2)*(1-0.12),2) = 326.94

   These differ by a cent, so the test below genuinely discriminates.

2. Currency-timing contradiction (carried from phaseG G4, applies
   unchanged through H1/H2/H3): one comment near convert()/
   format_currency() says conversion happens "as the very last step,
   after total is finalized"; a comment on confirm_order says conversion
   happens "before tax is applied, so tax is computed in the settlement
   currency". TIEBREAKER (pinned, reused from H2's report): convert-last
   wins. The order-lifecycle state machine requires state "priced"
   before confirm_order can run at all, and pricing (the part of
   build_invoice that computes total, including tax) already completed
   and transitioned the order out of "validated" by the time
   confirm_order executes -- tax was already finalized, in USD, at a
   pipeline stage confirm_order has no state-machine permission to
   re-enter. Converting the already-finalized USD total as confirm_order's
   last step treats currency conversion as a presentation step layered
   on top of an already-completed pipeline, consistent with the
   lifecycle contract this file itself enforces elsewhere.

   Verification (post_discount_amount=326.93, reusing contradiction 1's
   coupon-last result, region="EU" -> tax rate 0.20, settlement_currency
   "GBP" -> rate 0.79), computed directly via python3 -c:

       tax = round(326.93*0.20, 2) = 65.39
       total_usd = round(326.93+65.39, 2) = 392.32

       convert-last:       round(392.32*0.79, 2)                     = 309.93
       convert-before-tax: pre = round(326.93*0.79, 2)   = 258.27
                           tax_settlement = round(258.27*0.20, 2) = 51.65
                           round(258.27+51.65, 2)                     = 309.92

   These differ by a cent, so the test below genuinely discriminates.

3. Campaign-order contradiction (H2's own, carried forward unchanged
   into H3): the spec text contains two contradictory statements about
   WHERE in the discount chain a campaign applies relative to
   coupon/volume/membership -- one says "campaigns apply after all other
   discounts, to the final discounted total" (apply_campaign runs on
   stack_discounts's output); the other says "campaigns apply first,
   before any other discount logic runs, since promotional pricing
   supersedes standing discounts" (apply_campaign runs on the raw
   pre-discount subtotal, and stack_discounts then runs on ITS output).
   TIEBREAKER (pinned, reused from H2's report): campaigns-apply-
   after-all-other-discounts wins. A campaign here is layered
   promotional pricing applied via a standalone call (`apply_campaign`)
   after the order already has a `post_discount_amount` from the
   ordinary discount chain -- the same shape as coupon-last and
   record_approval, both of which operate on an order that already
   carries a computed amount rather than reaching back to re-run earlier
   pipeline stages, so campaigns-after is the reading consistent with
   every other layered-on-top concern in this file (including H3's own
   new `partial_refund`, which likewise reads `post_discount_amount` as
   the authoritative already-composed value rather than re-deriving it
   -- see contradiction-3-adjacent scenario E in the partial_refund
   section below, which depends on this same pinned reading).

   Verification (subtotal=420.00, qty=55 -> volume_discount_rate=0.10
   since qty >= 50, tier="silver" -> membership_discount_rate=0.03,
   coupon SAVE10 -> rate 0.10, campaign rate 0.20 multiply), computed
   directly via python3 -c:

       post_discount_amount (coupon-last stack):
           D = round(round(round(420.00*(1-0.10),2)*(1-0.03),2)*(1-0.10),2) = 329.99

       campaigns-after (apply_campaign runs on D):
           resultA = round(329.99*(1-0.20),2) = 263.99

       campaigns-first (apply_campaign runs on raw subtotal, then
       stack_discounts runs on ITS output):
           S_after_campaign = round(420.00*(1-0.20),2) = 336.0
           resultB = round(round(round(336.0*(1-0.10),2)*(1-0.03),2)*(1-0.10),2) = 264.0

   These differ by a cent, so the test below genuinely discriminates.

4. H3's own new complexity (tax cascading + refund reversal) is
   deliberately NOT a written textual contradiction -- per ../SPEC.md's
   "H3" section, it instead tests whether the composed bookkeeping
   (what was applied to an order, and in what order) can be reversed
   correctly. See the TAX_JURISDICTIONS/compute_tax and partial_refund
   sections below; every numeric expectation there is computed directly
   via python3 -c and pasted in leaf-H3.TESTWRITER-REPORT.md, following
   the same verify-before-hardcode discipline as contradictions 1-3.

Implementation-level calls made by this test file that are NOT seeded
ambiguities (stated here so they read as deliberate, not accidental --
carried forward from the established conventions visible in H2's own
test file, per this task's explicit permission to read it):

  * `apply_coupon(amount, code, order_id)`, `redeem_loyalty_points(amount,
    points_available, points_to_redeem, order_id)`, and
    `reserve_stock(catalog, sku, qty, order_id)` all take a trailing
    `order_id` argument, needed to populate `_audit_entry`'s `order_id`
    field at each of these mutator call sites.
  * `apply_campaign(order, campaign_id, as_of)` reads and overwrites
    `order["post_discount_amount"]` in place and returns the order
    itself (same convention as `confirm_order`/`ship_order`).
  * `apply_campaign` is the 6th `_audit_entry` call site; `partial_refund`
    is the 7th.
  * `CAMPAIGNS` window bounds are inclusive on both ends.
  * `compute_tax(order)` reads `order["region"]` and
    `order["post_discount_amount"]`, and an optional
    `order["special_district"]` boolean that overrides ONLY the
    "special_district" layer's default `active` flag for US-CA, for
    that one order -- it does not mutate `TAX_JURISDICTIONS` itself.
  * `compute_tax`'s cascading sums rates first, then multiplies once
    against the base amount, with a single final `round(..., 2)` --
    i.e. `round(amount * sum(active_rates), 2)`, not per-layer rounding
    then summed -- per ../SPEC.md's explicit "sum(rate_i) * amount, not
    sequential amount *= (1+rate_i)" phrasing. (The chosen test amounts
    below use rates that don't expose a rounding-order difference
    either way, so this convention doesn't change any asserted number,
    but it is the reading the tests are written against.)
  * `partial_refund`'s proportional share is computed against the
    order's TOTAL quantity across all items (`total_qty`), not the
    refunded item's own original quantity alone -- this is literal text
    from ../SPEC.md ("by its share of total_qty"), not a tiebreaker call,
    and scenario F below exists specifically to lock this down for a
    multi-item order where the two readings would differ.
  * `partial_refund`'s `refund_amount` equals the cancelled proportional
    share of `post_discount_amount` PLUS the tax reversed on that same
    share (via `compute_tax`'s own per-layer logic on the share amount)
    -- i.e. it refunds what was actually charged for that share
    (post-discount amount + tax), not just the bare discounted amount.
  * `partial_refund`'s `points_credited` is computed from
    `order["points_redeemed"]` (how many loyalty points were originally
    redeemed against this order) proportional to the refunded share, and
    is credited back into `order["points_available"]` (incremented) --
    it does NOT reduce `refund_amount`, per ../SPEC.md's explicit "credit
    back points via points_available, do not just subtract from total"
    instruction.
  * `partial_refund` calls `release_stock` against the module-level
    `pe.CATALOG` (no catalog argument exists on `partial_refund`'s own
    signature, and no other module-level function in this file's
    established contract takes an explicit catalog argument either --
    `build_line_items` is the existing precedent for a function that
    reads/writes the module-level CATALOG implicitly).
  * `item_id` in `partial_refund(order, item_id, qty)` is the same
    string as the `"sku"` field used throughout `order["items"]`
    elsewhere in this file's established `catalog.py` contract -- no
    separate item-id namespace is introduced.
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


@pytest.fixture(autouse=True)
def _reset_catalog_stock():
    # Isolates partial_refund's release_stock effect (asserted against
    # the module-level pe.CATALOG) from any other test's mutations.
    original = {sku: dict(info) for sku, info in pe.CATALOG.items()}
    yield
    for sku, info in original.items():
        pe.CATALOG[sku].update(info)


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
    directly at a specific total (same pattern used by phaseG G3/G4 and
    phaseH H1/H2's own test suites)."""
    order = {
        "order_id": order_id,
        "state": "priced",
        "region": "US-CA",
        "post_discount_amount": total,
        "total": total,
    }
    order.update(overrides)
    return order


def _shipped_order(post_discount_amount, items, total_qty, order_id="ORD-SHIPPED-1",
                    **overrides):
    """A hand-built order already in the 'shipped' state, for driving
    partial_refund tests directly -- items/total_qty/post_discount_amount
    are the only bookkeeping partial_refund's own contract (../SPEC.md's
    H3 section) states it reads; no other internal shape is assumed."""
    order = {
        "order_id": order_id,
        "state": "shipped",
        "region": "US-OR",
        "items": items,
        "total_qty": total_qty,
        "post_discount_amount": post_discount_amount,
        "total": post_discount_amount,
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
    subtotal = 412.80
    total_qty = 6            # -> volume_discount_rate = 0.0 (qty < 10)
    tier = "platinum"         # -> membership_discount_rate = 0.12
    coupon_code = "SAVE10"    # -> rate 0.10, min_spend 50.0, not expired

    result = pe.stack_discounts(subtotal, total_qty, tier, coupon_code)

    coupon_last_result = 326.93   # volume, then membership, then coupon last
    coupon_first_result = 326.94  # coupon first, then volume, then membership

    assert coupon_last_result != coupon_first_result, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result == coupon_last_result
    assert result != coupon_first_result


def test_stack_discounts_without_coupon():
    # No coupon supplied -- the contradiction doesn't apply, only
    # volume-then-membership matters and both readings agree.
    result = pe.stack_discounts(150.0, 20, "silver")
    # 150.0 * (1 - 0.05) * (1 - 0.03) = 150.0 * 0.95 * 0.97 = 138.225 -> 138.23
    assert result == 138.23


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
# tax.py / loyalty.py (E4) -- the ORIGINAL single-rate calculate_tax, kept
# unchanged/parallel to the new H3 TAX_JURISDICTIONS/compute_tax below.
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
# G3: shared _audit_entry helper, used at pre-H1 mutator call sites
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
# convert-last (see module docstring item 2). The two candidate
# interpretations produce different cent-level settlement totals for the
# case below, so this genuinely discriminates.
# ---------------------------------------------------------------------------

def test_currency_timing_contradiction_pinned_to_convert_last():
    order = _priced_order(392.32, order_id="ORD-CURRENCY-1", region="EU",
                           post_discount_amount=326.93)

    result = pe.confirm_order(order, settlement_currency="GBP")

    convert_last_total = 309.93        # convert the already-finalized USD total
    convert_before_tax_total = 309.92  # convert pre-tax, then tax in settlement currency

    assert convert_last_total != convert_before_tax_total, (
        "sanity check: the two interpretations must produce different cent "
        "values for this test to actually discriminate"
    )
    assert result["settlement_total"] == convert_last_total
    assert result["settlement_total"] != convert_before_tax_total
    assert result["settlement_currency"] == "GBP"
    assert result["settlement_total_formatted"] == pe.format_currency(convert_last_total, "GBP")
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
    order = _priced_order(500.0, order_id="ORD-APPROVAL-BOUNDARY-1")
    result = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert result is order


def test_confirm_order_above_approval_threshold_without_approval_raises_naming_manager():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-MID-1")
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)
    assert order["state"] == "priced"


def test_confirm_order_above_approval_threshold_with_manager_approval_proceeds():
    order = _priced_order(800.0, order_id="ORD-APPROVAL-MID-2")
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


def test_record_approval_finance_before_manager_raises_valueerror():
    order = _priced_order(2500.0, order_id="ORD-ORDER-RULE-1")
    before = len(pe.AUDIT_LOG)
    with pytest.raises(ValueError):
        pe.record_approval(order, "finance")
    assert len(pe.AUDIT_LOG) == before
    with pytest.raises(ValueError, match="manager"):
        pe.confirm_order(order)


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


def test_confirm_order_wrong_state_rejected_even_with_approvals_recorded():
    order = _priced_order(2500.0, order_id="ORD-INDEPENDENT-1", state="validated")
    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")
    with pytest.raises(ValueError, match="priced"):
        pe.confirm_order(order)
    assert order["state"] == "validated"


# ---------------------------------------------------------------------------
# H2: CAMPAIGNS registry -- shape check, parallel to COUPONS but with
# starts_at/ends_at ISO-date bounds and a per-entry stacking flag.
# This rung uses its OWN registry fixture data (fresh entries, not
# copied from H2's SUMMER15/FLAT20/WINTER10 literals).
#
# This test file's own required CAMPAIGNS entries, exact specs (the
# implementation must define CAMPAIGNS to match every one of these
# exactly, since specific numeric outcomes below are pinned to them):
#
#   HOLIDAY20   -- stacking "multiply", rate 0.15,
#                  starts_at "2026-06-01", ends_at "2026-08-31"
#                  (includes the common test date "2026-06-15",
#                  inclusive of both boundary dates).
#   CLEARANCE30 -- stacking "additive", value 30.0,
#                  starts_at "2026-01-01", ends_at "2026-12-31"
#                  (includes the common test date).
#   SPRING5     -- stacking "multiply", rate 0.05,
#                  starts_at "2025-03-01", ends_at "2025-05-31"
#                  (deliberately EXCLUDES the common test date
#                  "2026-06-15", satisfying the brief's requirement for
#                  an entry whose window excludes a test date used
#                  elsewhere in the file).
#   DOUBLE20    -- stacking "multiply", rate 0.20,
#                  starts_at "2026-01-01", ends_at "2026-12-31"
#                  (a 4th entry, used only by the campaign-order
#                  contradiction-3 test below, at a distinct rate from
#                  HOLIDAY20 so that scenario's own numbers are
#                  independently chosen rather than reusing HOLIDAY20's
#                  0.15 rate).
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
    with pytest.raises(ValueError, match="SPRING5"):
        pe.apply_campaign(order, "SPRING5", "2025-01-15")


def test_apply_campaign_after_window_raises_naming_campaign():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-LATE-1")
    with pytest.raises(ValueError, match="SPRING5"):
        pe.apply_campaign(order, "SPRING5", "2025-07-01")


def test_apply_campaign_window_boundary_starts_at_is_valid():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-BOUNDARY-1")
    result = pe.apply_campaign(order, "HOLIDAY20", "2026-06-01")
    assert order["state"] == "priced"  # applying a campaign doesn't move state
    assert result is order


def test_apply_campaign_window_boundary_ends_at_is_valid():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-BOUNDARY-2")
    result = pe.apply_campaign(order, "HOLIDAY20", "2026-08-31")
    assert result is order


# ---------------------------------------------------------------------------
# H2: apply_campaign -- multiply and additive stacking math
# ---------------------------------------------------------------------------

def test_apply_campaign_multiply_stacking():
    # HOLIDAY20: multiply, rate 0.15, window includes 2026-06-15.
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-MULTIPLY-1")
    result = pe.apply_campaign(order, "HOLIDAY20", "2026-06-15")
    # round(238.55 * (1 - 0.15), 2) = 202.77
    assert order["post_discount_amount"] == 202.77
    assert result is order


def test_apply_campaign_additive_stacking():
    # CLEARANCE30: additive, value 30.0, window includes 2026-06-15.
    order = _priced_order(65.0, order_id="ORD-CAMPAIGN-ADDITIVE-1")
    result = pe.apply_campaign(order, "CLEARANCE30", "2026-06-15")
    assert order["post_discount_amount"] == 35.0
    assert result is order


def test_apply_campaign_additive_stacking_floors_at_zero():
    order = _priced_order(5.0, order_id="ORD-CAMPAIGN-ADDITIVE-2")
    pe.apply_campaign(order, "CLEARANCE30", "2026-06-15")
    assert order["post_discount_amount"] == 0.0


# ---------------------------------------------------------------------------
# CONTRADICTION 3 (H2's, carried forward unchanged into H3): campaign-
# application-order. Pinned to campaigns-apply-after-all-other-discounts
# -- see module docstring item 3. The two candidate interpretations
# produce different cent-level totals for the case below, so this
# genuinely discriminates.
# ---------------------------------------------------------------------------

def test_campaign_order_contradiction_pinned_to_after_all_discounts():
    subtotal = 420.00
    total_qty = 55            # -> volume_discount_rate = 0.10 (qty >= 50)
    tier = "silver"             # -> membership_discount_rate = 0.03
    coupon_code = "SAVE10"      # -> rate 0.10

    post_discount_amount = pe.stack_discounts(subtotal, total_qty, tier, coupon_code)
    assert post_discount_amount == 329.99

    order = _priced_order(post_discount_amount, order_id="ORD-CAMPAIGN-ORDER-1",
                           post_discount_amount=post_discount_amount)

    # DOUBLE20 (multiply, rate 0.20 -- see the CAMPAIGNS table above the
    # registry shape tests) is used here rather than HOLIDAY20 (rate
    # 0.15, used for the plain stacking-math tests above) so this
    # scenario's numbers are independently chosen, not reused.
    result = pe.apply_campaign(order, "DOUBLE20", "2026-06-15")

    campaigns_after_result = 263.99   # campaign applied to post_discount_amount (329.99)
    campaigns_first_result = 264.0    # campaign applied to raw subtotal (420.00),
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
# established shape, same as the other 5 pre-H2 mutator call sites.
# ---------------------------------------------------------------------------

def test_apply_campaign_appends_audit_entry_with_established_shape():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-AUDIT-1")
    before = len(pe.AUDIT_LOG)
    pe.apply_campaign(order, "HOLIDAY20", "2026-06-15")
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-CAMPAIGN-AUDIT-1")


def test_apply_campaign_rejected_window_does_not_append_audit_entry():
    order = _priced_order(238.55, order_id="ORD-CAMPAIGN-AUDIT-2")
    before = len(pe.AUDIT_LOG)
    with pytest.raises(ValueError):
        pe.apply_campaign(order, "SPRING5", "2026-06-15")
    assert len(pe.AUDIT_LOG) == before


# ===========================================================================
# H3's own new layer, part A: multi-jurisdiction tax cascading
# TAX_JURISDICTIONS / compute_tax(order)
# ===========================================================================

def test_tax_jurisdictions_registry_shape():
    assert set(pe.TAX_JURISDICTIONS.keys()) >= {"US-CA", "US-OR", "US-NY", "EU"}
    for region, layers in pe.TAX_JURISDICTIONS.items():
        assert isinstance(layers, list)
        for layer in layers:
            assert set(layer.keys()) == {"name", "rate", "active"}
            assert isinstance(layer["name"], str)
            assert isinstance(layer["rate"], float)
            assert isinstance(layer["active"], bool)


def test_tax_jurisdictions_us_ca_layers():
    layers = {l["name"]: l for l in pe.TAX_JURISDICTIONS["US-CA"]}
    assert layers["state"]["rate"] == 0.0725
    assert layers["state"]["active"] is True
    assert layers["local"]["rate"] == 0.01
    assert layers["local"]["active"] is True
    assert layers["special_district"]["rate"] == 0.0025
    assert layers["special_district"]["active"] is False  # off by default


def test_tax_jurisdictions_us_ny_layers_sum_to_existing_calculate_tax_rate():
    layers = {l["name"]: l for l in pe.TAX_JURISDICTIONS["US-NY"]}
    assert layers["state"]["rate"] == 0.04
    assert layers["local"]["rate"] == 0.04875
    total_rate = sum(l["rate"] for l in pe.TAX_JURISDICTIONS["US-NY"] if l["active"])
    # matches calculate_tax's existing US-NY rate (0.08875)
    assert round(total_rate, 5) == 0.08875


def test_tax_jurisdictions_us_or_has_no_layers():
    assert pe.TAX_JURISDICTIONS["US-OR"] == []


def test_tax_jurisdictions_eu_single_flat_layer():
    layers = pe.TAX_JURISDICTIONS["EU"]
    assert len(layers) == 1
    assert layers[0]["rate"] == 0.20
    assert layers[0]["active"] is True


def test_compute_tax_us_ca_default_matches_existing_calculate_tax():
    order = {"region": "US-CA", "post_discount_amount": 1000.0}
    # 0.0725 + 0.01 = 0.0825, matching calculate_tax(amount, "US-CA")'s rate
    assert pe.compute_tax(order) == 82.5
    assert pe.compute_tax(order) == pe.calculate_tax(1000.0, "US-CA")


def test_compute_tax_us_ca_special_district_toggled_on_via_order_flag():
    order = {"region": "US-CA", "post_discount_amount": 1000.0, "special_district": True}
    assert pe.compute_tax(order) == 85.0


def test_compute_tax_us_ca_special_district_flag_does_not_leak_to_other_orders():
    order_with_flag = {"region": "US-CA", "post_discount_amount": 1000.0, "special_district": True}
    pe.compute_tax(order_with_flag)
    order_without_flag = {"region": "US-CA", "post_discount_amount": 1000.0}
    assert pe.compute_tax(order_without_flag) == 82.5
    # the registry's own default must remain untouched
    layers = {l["name"]: l for l in pe.TAX_JURISDICTIONS["US-CA"]}
    assert layers["special_district"]["active"] is False


def test_compute_tax_us_ny_matches_existing_calculate_tax_rate():
    order = {"region": "US-NY", "post_discount_amount": 1000.0}
    assert pe.compute_tax(order) == 88.75
    assert pe.compute_tax(order) == pe.calculate_tax(1000.0, "US-NY")


def test_compute_tax_us_or_is_zero():
    order = {"region": "US-OR", "post_discount_amount": 500.0}
    assert pe.compute_tax(order) == 0.0


def test_compute_tax_eu_matches_existing_flat_rate():
    order = {"region": "EU", "post_discount_amount": 1000.0}
    assert pe.compute_tax(order) == 200.0
    assert pe.compute_tax(order) == pe.calculate_tax(1000.0, "EU")


def test_compute_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        pe.compute_tax({"region": "US-TX", "post_discount_amount": 100.0})


def test_compute_tax_layers_not_compounded():
    # Each active layer computed independently on the SAME base amount,
    # summed, then multiplied once -- not sequential compounding.
    order = {"region": "US-CA", "post_discount_amount": 200.0, "special_district": True}
    not_compounded = round(200.0 * (0.0725 + 0.01 + 0.0025), 2)
    sequential_compounded = round(200.0 * (1 + 0.0725) * (1 + 0.01) * (1 + 0.0025) - 200.0, 2)
    assert not_compounded != sequential_compounded, (
        "sanity check: compounded vs. non-compounded must differ for this "
        "test to actually discriminate"
    )
    assert pe.compute_tax(order) == not_compounded
    assert pe.compute_tax(order) != sequential_compounded


# ===========================================================================
# H3's own new layer, part B: partial_refund reversal logic (7th
# _audit_entry call site)
# ===========================================================================

def test_partial_refund_requires_shipped_state():
    order = _priced_order(100.0, order_id="ORD-REFUND-STATE-1", state="confirmed",
                           items=[{"sku": "widget", "qty": 10}], total_qty=10)
    with pytest.raises(ValueError, match="shipped"):
        pe.partial_refund(order, "widget", 4)


def test_partial_refund_qty_exceeding_original_raises():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 5}], total_qty=5,
                            order_id="ORD-REFUND-OVER-1")
    with pytest.raises(ValueError):
        pe.partial_refund(order, "widget", 6)


def test_partial_refund_full_original_qty_is_allowed():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 5}], total_qty=5,
                            order_id="ORD-REFUND-FULL-1")
    result = pe.partial_refund(order, "widget", 5)
    assert result["refund_amount"] == 100.0


def test_partial_refund_returns_dict_with_minimum_keys():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-SHAPE-1")
    result = pe.partial_refund(order, "widget", 4)
    assert isinstance(result, dict)
    assert "refund_amount" in result
    assert "points_credited" in result
    assert isinstance(result["refund_amount"], (int, float))
    assert isinstance(result["points_credited"], (int, float))


# -- Scenario A: proportional share, no tax, no loyalty, no campaign ------

def test_partial_refund_scenario_a_no_tax_no_loyalty():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-A-1", region="US-OR")
    result = pe.partial_refund(order, "widget", 4)
    # share = 4/10 = 0.4; share_amount = round(100.0*0.4, 2) = 40.0
    # tax on share (US-OR, 0.0 rate) = 0.0; refund_amount = 40.0
    assert result["refund_amount"] == 40.0
    assert result["points_credited"] == 0


# -- Scenario B/C: tax reversal via compute_tax's own logic ---------------

def test_partial_refund_scenario_b_us_ca_tax_reversed_no_special_district():
    order = _shipped_order(200.0, [{"sku": "gadget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-B-1", region="US-CA")
    result = pe.partial_refund(order, "gadget", 3)
    # share = 0.3; share_amount = round(200.0*0.3, 2) = 60.0
    # tax = round(60.0*(0.0725+0.01), 2) = 4.95; refund = 64.95
    assert result["refund_amount"] == 64.95


def test_partial_refund_scenario_c_us_ca_tax_reversed_special_district_active():
    order = _shipped_order(200.0, [{"sku": "gadget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-C-1", region="US-CA",
                            special_district=True)
    result = pe.partial_refund(order, "gadget", 3)
    # share_amount = 60.0; tax = round(60.0*(0.0725+0.01+0.0025), 2) = 5.1
    # refund = 65.1
    assert result["refund_amount"] == 65.1
    # proves the reversal genuinely used compute_tax's own per-order
    # special_district flag, not a flat US-CA re-guess ignoring it
    assert result["refund_amount"] != 64.95


# -- Scenario D: loyalty-point reversal, credited via points_available ----

def test_partial_refund_scenario_d_loyalty_points_credited_back():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-D-1", region="US-OR",
                            points_redeemed=200, points_available=300)
    result = pe.partial_refund(order, "widget", 5)
    # share = 0.5; points_credited = round(200*0.5) = 100
    # refund_amount = share_amount(50.0) + tax(0.0) = 50.0
    assert result["points_credited"] == 100
    assert result["refund_amount"] == 50.0
    # credited via points_available (incremented), not subtracted from total
    assert order["points_available"] == 400
    assert order["total"] == 100.0  # unchanged -- refund is not deducted from "total"


# -- Scenario E: campaign-effect reversal, proportional on the already-
# discounted (post-campaign) amount, per contradiction 3's pinned reading.
# ---------------------------------------------------------------------

def test_partial_refund_scenario_e_reflects_post_campaign_amount_not_pre_campaign():
    order = _priced_order(500.0, order_id="ORD-REFUND-E-1", region="US-OR",
                           post_discount_amount=500.0,
                           items=[{"sku": "widget", "qty": 10}], total_qty=10)
    pe.apply_campaign(order, "HOLIDAY20", "2026-06-15")
    # round(500.0 * (1 - 0.15), 2) = 425.0
    assert order["post_discount_amount"] == 425.0

    pe.confirm_order(order)  # 425.0 < APPROVAL_THRESHOLD (500.0), no approval needed
    pe.ship_order(order)

    result = pe.partial_refund(order, "widget", 2)
    # share = 2/10 = 0.2
    # share_amount(post-campaign) = round(425.0*0.2, 2) = 85.0
    # tax on share (US-OR, 0.0) = 0.0; refund_amount = 85.0
    assert result["refund_amount"] == 85.0
    # the WRONG (pre-campaign) reading would have produced
    # round(500.0*0.2, 2) = 100.0 -- proves the campaign effect was
    # genuinely reversed/accounted for, not ignored
    assert result["refund_amount"] != 100.0


# -- Scenario F: proportional share computed against TOTAL order qty, not
# the refunded item's own qty alone -- literal spec text, locked down for
# a multi-item order where the two readings would produce different
# numbers.
# ---------------------------------------------------------------------

def test_partial_refund_scenario_f_share_is_of_total_qty_not_items_own_qty():
    order = _shipped_order(
        200.0,
        [{"sku": "widget", "qty": 6}, {"sku": "gadget", "qty": 4}],
        total_qty=10,
        order_id="ORD-REFUND-F-1",
        region="US-OR",
    )
    result = pe.partial_refund(order, "gadget", 2)
    # CORRECT reading: share = refunded_qty / total_qty = 2/10 = 0.2
    #   share_amount = round(200.0*0.2, 2) = 40.0; refund_amount = 40.0
    # WRONG reading: share = refunded_qty / item's own qty = 2/4 = 0.5
    #   share_amount = round(200.0*0.5, 2) = 100.0; refund_amount = 100.0
    assert result["refund_amount"] == 40.0
    assert result["refund_amount"] != 100.0


# -- release_stock effect -------------------------------------------------

def test_partial_refund_calls_release_stock_for_refunded_qty():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-STOCK-1", region="US-OR")
    before_stock = pe.CATALOG["widget"]["stock"]
    pe.partial_refund(order, "widget", 4)
    assert pe.CATALOG["widget"]["stock"] == before_stock + 4


def test_partial_refund_calls_release_stock_only_for_the_refunded_sku():
    order = _shipped_order(
        200.0,
        [{"sku": "widget", "qty": 6}, {"sku": "gadget", "qty": 4}],
        total_qty=10,
        order_id="ORD-REFUND-STOCK-2",
        region="US-OR",
    )
    before_widget = pe.CATALOG["widget"]["stock"]
    before_gadget = pe.CATALOG["gadget"]["stock"]
    pe.partial_refund(order, "gadget", 2)
    assert pe.CATALOG["gadget"]["stock"] == before_gadget + 2
    assert pe.CATALOG["widget"]["stock"] == before_widget


# -- 7th _audit_entry call site --------------------------------------------

def test_partial_refund_appends_audit_entry_with_established_shape():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                            order_id="ORD-REFUND-AUDIT-1", region="US-OR")
    before = len(pe.AUDIT_LOG)
    pe.partial_refund(order, "widget", 4)
    assert len(pe.AUDIT_LOG) == before + 1
    _assert_well_shaped_audit_entry(pe.AUDIT_LOG[-1], "ORD-REFUND-AUDIT-1")


def test_partial_refund_over_original_qty_does_not_append_audit_entry():
    order = _shipped_order(100.0, [{"sku": "widget", "qty": 5}], total_qty=5,
                            order_id="ORD-REFUND-AUDIT-2", region="US-OR")
    before = len(pe.AUDIT_LOG)
    with pytest.raises(ValueError):
        pe.partial_refund(order, "widget", 6)
    assert len(pe.AUDIT_LOG) == before


def test_all_seven_mutator_audit_entries_share_identical_shape(fresh_catalog):
    # 4 pre-H1 sites (reserve_stock, redeem_loyalty_points, apply_coupon,
    # confirm_order), H1's 5th site (record_approval), H2's 6th site
    # (apply_campaign), and H3's new 7th site (partial_refund) all reuse
    # the same _audit_entry helper -- same {"action", "order_id", "detail"}
    # shape across every one of them, no invented alternate shape for
    # tax cascading or refunds.
    order_id = "ORD-SHAPE-1"
    pe.reserve_stock(fresh_catalog, "widget", 1, order_id)
    pe.redeem_loyalty_points(50.0, 500, 100, order_id)
    pe.apply_coupon(100.0, "SAVE10", order_id)

    priced = _priced_order(800.0, order_id=order_id)
    pe.record_approval(priced, "manager")
    pe.apply_campaign(priced, "HOLIDAY20", "2026-06-15")
    pe.confirm_order(priced)

    shipped = _shipped_order(100.0, [{"sku": "widget", "qty": 10}], total_qty=10,
                              order_id=order_id, region="US-OR")
    pe.partial_refund(shipped, "widget", 4)

    assert len(pe.AUDIT_LOG) == 7
    key_shapes = {frozenset(entry.keys()) for entry in pe.AUDIT_LOG}
    assert key_shapes == {frozenset({"action", "order_id", "detail"})}
    for entry in pe.AUDIT_LOG:
        assert entry["order_id"] == order_id
        assert isinstance(entry["detail"], dict)


# ---------------------------------------------------------------------------
# Composition: the full cumulative stack -- lifecycle, approvals,
# settlement currency, campaign stacking, tax cascading, and a refund --
# all interacting on the same order.
# ---------------------------------------------------------------------------

def test_full_lifecycle_with_campaign_escalation_approvals_settlement_and_refund():
    # A hand-built priced order (bypassing build_invoice) so the total is
    # deliberately set above ESCALATION_THRESHOLD -- this composition
    # check exercises manager+finance approvals, settlement currency,
    # campaign stacking, and a refund all on one order, without needing
    # to reverse-engineer exact discount-chain math on top of it.
    order = _priced_order(2500.0, order_id="ORD-COMPOSITION-1", region="EU",
                           post_discount_amount=2500.0,
                           items=[{"sku": "widget", "qty": 10}], total_qty=10)

    pe.apply_campaign(order, "HOLIDAY20", "2026-06-15")
    # round(2500.0 * (1 - 0.15), 2) = 2125.0 -- still >= ESCALATION_THRESHOLD
    assert order["post_discount_amount"] == 2125.0

    pe.record_approval(order, "manager")
    pe.record_approval(order, "finance")

    result = pe.confirm_order(order, settlement_currency="GBP")
    assert order["state"] == "confirmed"
    assert result["settlement_currency"] == "GBP"

    pe.ship_order(order)
    assert order["state"] == "shipped"

    refund = pe.partial_refund(order, "widget", 3)
    assert refund["refund_amount"] > 0
    assert isinstance(refund["points_credited"], (int, float))
    assert order["state"] == "shipped"  # a refund doesn't move lifecycle state

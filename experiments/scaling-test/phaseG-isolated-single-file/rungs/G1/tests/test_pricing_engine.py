"""Tests for src/pricing_engine.py — catalog + discounts + engine, merged
into a single module per leaf-G1's brief.

Canonical spec: ../../phaseE-leaf-ceiling-v2/MODULES.md lines 7-24
(catalog.py, discounts.py, engine.py sections).

Coupon-order tiebreaker: MODULES.md seeds a genuine contradiction —
discounts.py's own section says "coupon first, then volume, then
membership"; engine.py's section says the canonical order is "volume
discount, then membership discount, then coupon last" and instructs
implementers to "handle it exactly as the current /manager-mode process
expects." The precedent for that process, at
../../phaseE-leaf-ceiling-v2/rungs/E1/src/discounts.py, resolves this
identical contradiction as volume -> membership -> coupon-last, with an
in-file comment explaining the choice matches engine.py's orchestrator
framing. This test file pins that same resolution: volume -> membership ->
coupon-last. test_stack_discounts_order_is_volume_membership_coupon_last
below is a numeric case where the alternate order (coupon-first) produces
97.72 instead of the pinned order's 97.71 -- verified by hand under both
`amt * (1 - rate)` and `amt - amt * rate` arithmetic styles to land on the
same two values either way (no `.xx5` rounding-boundary dependence), so the
assertion actually discriminates between the orders rather than being
coincidentally satisfiable by both.
"""

import pytest

import pricing_engine as pe


# ---------------------------------------------------------------------------
# catalog.py surface: CATALOG, build_line_items
# ---------------------------------------------------------------------------


def test_catalog_contents():
    assert pe.CATALOG == {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }


def test_build_line_items_basic():
    line_items, subtotal, total_qty = pe.build_line_items(
        [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    )
    assert line_items == {"widget": 29.97, "gadget": 49.0}
    assert subtotal == 78.97
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        pe.build_line_items([{"sku": "nonexistent", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        pe.build_line_items([{"sku": "gadget", "qty": 6}])


def test_build_line_items_out_of_stock_sku_raises_valueerror():
    with pytest.raises(ValueError):
        pe.build_line_items([{"sku": "gizmo", "qty": 1}])


# ---------------------------------------------------------------------------
# discounts.py surface: volume_discount_rate, membership_discount_rate,
# COUPONS, apply_coupon, stack_discounts
# ---------------------------------------------------------------------------


def test_volume_discount_rate_boundaries():
    assert pe.volume_discount_rate(0) == 0.0
    assert pe.volume_discount_rate(9) == 0.0
    assert pe.volume_discount_rate(10) == 0.05
    assert pe.volume_discount_rate(49) == 0.05
    assert pe.volume_discount_rate(50) == 0.10
    assert pe.volume_discount_rate(1000) == 0.10


def test_membership_discount_rate_known_tiers():
    assert pe.membership_discount_rate("none") == 0.0
    assert pe.membership_discount_rate("silver") == 0.03
    assert pe.membership_discount_rate("gold") == 0.07
    assert pe.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        pe.membership_discount_rate("diamond")


def test_coupons_table():
    assert pe.COUPONS == {
        "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}
    }


def test_apply_coupon_success():
    assert pe.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_expired_raises():
    # SAVE10 is not expired per spec; simulate an expired coupon via the
    # module's own COUPONS table to prove apply_coupon actually reads
    # coupon["expired"] rather than hardcoding non-expiry.
    original = pe.COUPONS["SAVE10"]["expired"]
    pe.COUPONS["SAVE10"]["expired"] = True
    try:
        with pytest.raises(ValueError):
            pe.apply_coupon(100.0, "SAVE10")
    finally:
        pe.COUPONS["SAVE10"]["expired"] = original


def test_stack_discounts_no_coupon():
    # qty=12 -> volume 0.05; tier gold -> 0.07; no coupon.
    # 100 * 0.95 = 95.0 ; 95.0 * 0.93 = 88.35
    result = pe.stack_discounts(100.0, 12, "gold", coupon_code=None)
    assert result == 88.35


def test_stack_discounts_order_is_volume_membership_coupon_last():
    """Pins the tiebreaker: volume -> membership -> coupon-last.

    subtotal=129.87, total_qty=13 (volume rate 0.05), tier="platinum"
    (membership rate 0.12), coupon "SAVE10" (rate 0.10).

    Pinned order (volume, then membership, then coupon-last):
        129.87 * 0.95 = 123.3765 -> round -> 123.38
        123.38 * 0.88 = 108.5744 -> round -> 108.57
        108.57 * 0.90 = 97.713   -> round -> 97.71

    Alternate order (coupon-first, then volume, then membership) would give:
        129.87 * 0.90 = 116.883 -> round -> 116.88
        116.88 * 0.95 = 111.036 -> round -> 111.04
        111.04 * 0.88 = 97.7152 -> round -> 97.72

    97.71 != 97.72, discriminating the two orders. Unlike an earlier draft
    of this test (flagged by audit), this case does NOT land on an exact
    `.xx5` rounding boundary at any intermediate step, and both plausible
    per-step arithmetic expressions -- `amt * (1 - rate)` and the
    mathematically-equivalent `amt - amt * rate` -- were hand-verified in
    Python to produce identical intermediate values at every step for both
    orders (123.38/108.57/97.71 and 116.88/111.04/97.72 either way), so the
    result cannot flip due to float-precision choice in the implementation.
    Only the pinned (volume -> membership -> coupon-last) order satisfies
    this assertion, regardless of arithmetic style.
    """
    result = pe.stack_discounts(129.87, 13, "platinum", coupon_code="SAVE10")
    assert result == 97.71
    assert result != 97.72  # explicit rejection of the coupon-first order


# ---------------------------------------------------------------------------
# engine.py surface: build_invoice
#
# NOTE (test-author assumptions, not drawn from MODULES.md): the contract
# excerpt only specifies `build_invoice(order: dict) -> dict`; it does not
# state the order dict's key names or the behavior when a key is entirely
# absent. This file assumes/invents:
#   - keys "items", "membership_tier", "coupon_code"
#   - a missing "membership_tier" defaults to the "none" (0.0) rate
#   - a missing "coupon_code" applies no coupon
# A builder is free to deviate from these key names/defaults if stronger
# evidence surfaces elsewhere in scope; these tests pin one reasonable
# reading, not a spec requirement.
# ---------------------------------------------------------------------------


def test_build_invoice_shape_and_values_no_coupon():
    order = {
        "items": [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}],
        "membership_tier": "silver",
    }
    invoice = pe.build_invoice(order)

    assert invoice["line_items"] == {"widget": 29.97, "gadget": 49.0}
    assert invoice["subtotal"] == 78.97
    # total_qty=5 -> volume 0.0; tier silver -> 0.03; no coupon.
    # 78.97 * 1.0 = 78.97 ; 78.97 * 0.97 = 76.6009 -> round -> 76.6
    assert invoice["post_discount_amount"] == 76.6
    assert invoice["total"] == 76.6


def test_build_invoice_pins_coupon_order_end_to_end():
    """Same numeric case as test_stack_discounts_order_is_volume_membership_coupon_last,
    driven through build_invoice, to confirm build_invoice's own discount
    call resolves the contradiction the same way (volume -> membership ->
    coupon-last) rather than reimplementing stack_discounts differently."""
    order = {
        "items": [{"sku": "widget", "qty": 13}],
        "membership_tier": "platinum",
        "coupon_code": "SAVE10",
    }
    invoice = pe.build_invoice(order)
    assert invoice["subtotal"] == 129.87
    assert invoice["post_discount_amount"] == 97.71
    assert invoice["total"] == 97.71


def test_build_invoice_default_tier_and_no_coupon():
    order = {"items": [{"sku": "widget", "qty": 1}]}
    invoice = pe.build_invoice(order)
    assert invoice["subtotal"] == 9.99
    assert invoice["post_discount_amount"] == 9.99
    assert invoice["total"] == 9.99


def test_build_invoice_delegates_to_build_line_items_for_unknown_sku():
    order = {"items": [{"sku": "doesnotexist", "qty": 1}]}
    with pytest.raises(KeyError):
        pe.build_invoice(order)


def test_build_invoice_delegates_to_build_line_items_for_over_stock():
    order = {"items": [{"sku": "gadget", "qty": 999}]}
    with pytest.raises(ValueError):
        pe.build_invoice(order)


def test_build_invoice_delegates_to_stack_discounts_for_bad_tier():
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "membership_tier": "not_a_real_tier",
    }
    with pytest.raises(ValueError):
        pe.build_invoice(order)


def test_build_invoice_returns_required_keys():
    order = {"items": [{"sku": "widget", "qty": 1}]}
    invoice = pe.build_invoice(order)
    for key in ("line_items", "subtotal", "post_discount_amount", "total"):
        assert key in invoice

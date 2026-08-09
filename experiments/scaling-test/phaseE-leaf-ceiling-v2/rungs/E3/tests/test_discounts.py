# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-5
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.

CONTRADICTION NOTE — read before touching this file:
specs/order-pricing-e3.md's "Discount-order resolution" section resolves
the coupon-first-vs-coupon-last contradiction inherited from the bible
(MODULES.md): discounts.stack_discounts implements coupon-first (its own
AC-5 text), and engine.build_invoice (AC-9) must delegate to it and use its
return value verbatim rather than recomputing a coupon-last total itself.
This file encodes ONLY the coupon-first reading with an order-discriminating
proof case below — see test_stack_discounts_order_proof_coupon_before_rate_discounts.
"""
import pytest


def test_volume_discount_rate_thresholds():
    import discounts

    assert discounts.volume_discount_rate(5) == 0.0
    assert discounts.volume_discount_rate(10) == 0.05
    assert discounts.volume_discount_rate(49) == 0.05
    assert discounts.volume_discount_rate(50) == 0.10


def test_membership_discount_rate_tiers():
    import discounts

    assert discounts.membership_discount_rate("none") == 0.0
    assert discounts.membership_discount_rate("silver") == 0.03
    assert discounts.membership_discount_rate("gold") == 0.07
    assert discounts.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    import discounts

    with pytest.raises(ValueError):
        discounts.membership_discount_rate("bronze")


def test_apply_coupon_happy_path():
    import discounts

    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    import discounts

    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    import discounts

    with pytest.raises(ValueError):
        discounts.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_expired_raises(monkeypatch):
    import discounts

    monkeypatch.setitem(
        discounts.COUPONS, "EXPIRED5",
        {"rate": 0.05, "min_spend": 0.0, "expired": True},
    )
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "EXPIRED5")


def test_stack_discounts_no_coupon_applies_volume_then_membership():
    import discounts

    # subtotal=1000, qty=60 -> volume 0.10, tier gold -> membership 0.07,
    # no coupon: 1000 * 0.90 * 0.93 = 837.0
    result = discounts.stack_discounts(1000.0, 60, "gold", coupon_code=None)
    assert result == 837.0


def test_stack_discounts_order_proof_coupon_before_rate_discounts():
    """Order-discriminating case: subtotal is above SAVE10's $50 min-spend
    BEFORE any other discount, but would drop BELOW $50 if volume/membership
    were applied first. Coupon-first math (this spec's resolution) can
    always apply the coupon since it checks min-spend against the raw
    subtotal; coupon-last math would fail apply_coupon's min-spend check
    (or produce a different numeric result) because the pre-coupon amount
    would already be discounted below $50. This makes the two orderings
    numerically distinguishable, not just conceptually different.
    """
    import discounts

    # subtotal=60.0, qty=60 (volume 0.10), tier platinum (membership 0.12).
    # Coupon-first: apply_coupon(60.0, "SAVE10") = 54.0 (60 >= 50 min-spend
    # passes) -> 54.0 * 0.90 (volume) = 48.6 -> 48.6 * 0.88 (membership)
    # = 42.768 -> round = 42.77.
    # Coupon-last would instead apply the coupon to 60.0 * 0.90 * 0.88 =
    # 47.52, which is BELOW SAVE10's $50 min-spend -> apply_coupon would
    # raise ValueError on that path. Coupon-first never hits that raise.
    result = discounts.stack_discounts(60.0, 60, "platinum", coupon_code="SAVE10")
    assert result == 42.77


def test_stack_discounts_coupon_code_none_skips_coupon():
    import discounts

    result = discounts.stack_discounts(20.0, 1, "none", coupon_code=None)
    assert result == 20.0

# spec: /Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseE-leaf-ceiling-v2/MODULES.md::discounts.py::AC-2
import pytest

import discounts


def test_volume_discount_rate_tiers():
    assert discounts.volume_discount_rate(5) == 0.0
    assert discounts.volume_discount_rate(10) == 0.05
    assert discounts.volume_discount_rate(50) == 0.10


def test_membership_discount_rate_tiers():
    assert discounts.membership_discount_rate("none") == 0.0
    assert discounts.membership_discount_rate("silver") == 0.03
    assert discounts.membership_discount_rate("gold") == 0.07
    assert discounts.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_raises():
    with pytest.raises(ValueError):
        discounts.membership_discount_rate("bronze")


def test_apply_coupon_real_save10():
    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE")


def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(
        discounts.COUPONS, "EXPIREDC", {"rate": 0.10, "min_spend": 0.0, "expired": True}
    )
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "EXPIREDC")


def test_stack_discounts_order_proof_coupon_first():
    """Order-discriminating case: subtotal (52.0) clears SAVE10's min_spend
    (50.0) at the START of the pipeline, but the amount remaining after
    volume+membership discounts would fall BELOW min_spend (~43.13 after
    volume then membership, before any coupon). A coupon-LAST
    implementation that calls apply_coupon on that reduced amount raises
    ValueError; coupon-FIRST does not, and produces exactly 43.13. This
    pins the canonical resolution documented in
    leaf-E2.TESTWRITER-DECISION.md: coupon-first, per discounts.py's own
    stated order.
    """
    result = discounts.stack_discounts(52.0, 10, "silver", coupon_code="SAVE10")
    assert result == 43.13

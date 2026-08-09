# spec: specs/SPEC.md::AC-5/AC-6::AC-6
"""
Tests for discounts.py — AC-5 (rate primitives, coupon) and AC-6 (stacking
order). Written by the shard-test-writer role BEFORE any impl exists.

Ground-truth stacking order for this leaf (see .swarm/questions/leaf-D2-Q1.md
for the AC-6/AC-9 contradiction and the best-guess resolution): coupon
first, then volume, then membership — AC-6's literal definition, treated as
canonical because build_invoice must literally delegate to stack_discounts
(see test_engine.py's interaction assertion).
"""
import pytest

import discounts


def test_volume_discount_rate_tiers():
    assert discounts.volume_discount_rate(0) == 0.0
    assert discounts.volume_discount_rate(9) == 0.0
    assert discounts.volume_discount_rate(10) == 0.05
    assert discounts.volume_discount_rate(49) == 0.05
    assert discounts.volume_discount_rate(50) == 0.10
    assert discounts.volume_discount_rate(500) == 0.10


def test_membership_discount_rate_known_tiers():
    assert discounts.membership_discount_rate("none") == 0.0
    assert discounts.membership_discount_rate("silver") == 0.03
    assert discounts.membership_discount_rate("gold") == 0.07
    assert discounts.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        discounts.membership_discount_rate("diamond")


def test_coupons_table_shape():
    assert discounts.COUPONS["SAVE10"] == {
        "rate": 0.10, "min_spend": 50.0, "expired": False,
    }


def test_apply_coupon_success():
    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(10.0, "SAVE10")


def test_stack_discounts_no_discounts_applies_zero():
    # qty=5 -> 0.0 volume rate, tier=none -> 0.0 membership rate, no coupon
    assert discounts.stack_discounts(100.0, 5, "none") == 100.0


def test_stack_discounts_coupon_first_then_volume_then_membership():
    # subtotal=100, qty=20 (0.05 volume), tier=silver (0.03 membership),
    # coupon SAVE10 (0.10): 100 -> coupon -> 90.0 -> volume -> 85.5
    # -> membership -> 82.935 -> round(2) -> 82.94
    assert discounts.stack_discounts(100.0, 20, "silver", "SAVE10") == 82.94


def test_stack_discounts_no_coupon_gold_high_volume():
    # subtotal=200, qty=60 (0.10 volume), tier=gold (0.07 membership), no coupon
    # 200 -> volume -> 180.0 -> membership -> 167.4
    assert discounts.stack_discounts(200.0, 60, "gold") == 167.4

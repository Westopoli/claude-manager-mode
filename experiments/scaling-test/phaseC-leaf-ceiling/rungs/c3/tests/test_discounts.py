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


def test_coupons_table():
    assert discounts.COUPONS["SAVE10"] == {
        "rate": 0.10,
        "min_spend": 50.0,
        "expired": False,
    }
    assert discounts.COUPONS["OLDCODE"] == {
        "rate": 0.20,
        "min_spend": 0.0,
        "expired": True,
    }


def test_apply_coupon_valid():
    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE")


def test_apply_coupon_expired_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "OLDCODE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(10.0, "SAVE10")


def test_stack_discounts_no_coupon():
    # subtotal=100, qty=20 (volume 0.05), tier=silver (0.03), no coupon
    result = discounts.stack_discounts(100.0, 20, "silver", None)
    expected = round(100.0 * 0.95 * 0.97, 2)
    assert result == expected


def test_stack_discounts_with_coupon_coupon_first_order():
    # This file's canonical order: coupon first, then volume, then membership.
    # subtotal=100, coupon SAVE10 (0.10) -> 90.0
    # then volume for qty=20 (0.05) -> 90 * 0.95 = 85.5
    # then membership gold (0.07) -> 85.5 * 0.93 = 79.515 -> round 79.52
    result = discounts.stack_discounts(100.0, 20, "gold", "SAVE10")
    step1 = discounts.apply_coupon(100.0, "SAVE10")
    step2 = round(step1 * (1 - 0.05), 2)
    step3 = round(step2 * (1 - 0.07), 2)
    assert result == step3


def test_stack_discounts_unknown_tier_raises():
    with pytest.raises(ValueError):
        discounts.stack_discounts(100.0, 5, "unknown_tier", None)


def test_stack_discounts_invalid_coupon_raises():
    with pytest.raises(ValueError):
        discounts.stack_discounts(100.0, 5, "none", "BADCODE")

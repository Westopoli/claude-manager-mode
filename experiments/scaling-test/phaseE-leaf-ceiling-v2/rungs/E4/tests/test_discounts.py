# spec: MODULES.md::discounts.py::AC-1
import pytest

from discounts import (
    volume_discount_rate,
    membership_discount_rate,
    COUPONS,
    apply_coupon,
    stack_discounts,
)


def test_volume_discount_rate_tiers():
    assert volume_discount_rate(0) == 0.0
    assert volume_discount_rate(9) == 0.0
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05
    assert volume_discount_rate(50) == 0.10
    assert volume_discount_rate(500) == 0.10


def test_membership_discount_rate_tiers():
    assert membership_discount_rate("none") == 0.0
    assert membership_discount_rate("silver") == 0.03
    assert membership_discount_rate("gold") == 0.07
    assert membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        membership_discount_rate("bogus")


def test_coupons_table():
    assert COUPONS["SAVE10"] == {"rate": 0.10, "min_spend": 50.0, "expired": False}


def test_apply_coupon_happy_path():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        apply_coupon(10.0, "SAVE10")


def test_stack_discounts_coupon_first_then_volume_then_membership():
    # Canonical order per MODULES.md discounts.py section: coupon first,
    # then volume, then membership. subtotal=100, qty=10 (5% volume),
    # tier=gold (7% membership), coupon SAVE10 (10%, min_spend 50).
    subtotal = 100.0
    total_qty = 10
    tier = "gold"
    coupon_code = "SAVE10"
    expected = round(subtotal * (1 - 0.10), 2)  # coupon: 90.0
    expected = round(expected * (1 - 0.05), 2)  # volume: 85.5
    expected = round(expected * (1 - 0.07), 2)  # membership: 79.52 (rounded)
    result = stack_discounts(subtotal, total_qty, tier, coupon_code)
    assert result == expected


def test_stack_discounts_no_coupon():
    subtotal = 100.0
    total_qty = 60  # 10% volume
    tier = "silver"  # 3% membership
    expected = round(subtotal * (1 - 0.10), 2)
    expected = round(expected * (1 - 0.03), 2)
    result = stack_discounts(subtotal, total_qty, tier, None)
    assert result == expected

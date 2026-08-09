import pytest
from discounts import (
    volume_discount_rate,
    membership_discount_rate,
    COUPONS,
    apply_coupon,
    redeem_loyalty_points,
    stack_discounts,
)


def test_volume_discount_rate_tiers():
    assert volume_discount_rate(1) == 0.0
    assert volume_discount_rate(9) == 0.0
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05
    assert volume_discount_rate(50) == 0.10


def test_membership_discount_rate_tiers():
    assert membership_discount_rate("none") == 0.0
    assert membership_discount_rate("silver") == 0.03
    assert membership_discount_rate("gold") == 0.07
    assert membership_discount_rate("platinum") == 0.12


def test_coupons_table():
    assert COUPONS["SAVE10"] == {"rate": 0.10, "min_spend": 50.0, "expired": False}


def test_apply_coupon_success():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_raises():
    with pytest.raises(ValueError):
        apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        apply_coupon(10.0, "SAVE10")


def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(COUPONS, "EXPIRED5", {"rate": 0.05, "min_spend": 0.0, "expired": True})
    with pytest.raises(ValueError):
        apply_coupon(100.0, "EXPIRED5")


def test_redeem_loyalty_points_basic():
    assert redeem_loyalty_points(100.0, 500, 200) == 98.0


def test_redeem_loyalty_points_floored_at_zero():
    assert redeem_loyalty_points(1.0, 1000, 1000) == 0.0


def test_redeem_loyalty_points_too_many_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(100.0, 100, 200)


def test_redeem_loyalty_points_negative_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(100.0, 100, -1)


def test_stack_discounts_volume_and_membership_only():
    result = stack_discounts(100.0, 10, "silver")
    expected = 100.0 * (1 - 0.05) * (1 - 0.03)
    assert result == pytest.approx(expected)


def test_stack_discounts_with_coupon():
    result = stack_discounts(100.0, 10, "silver", coupon_code="SAVE10")
    # apply_coupon rounds to 2dp internally (see discounts.apply_coupon),
    # so the expected value must go through the same rounding step rather
    # than comparing against an unrounded product.
    running = 100.0 * (1 - 0.05) * (1 - 0.03)
    expected = round(running * (1 - 0.10), 2)
    assert result == pytest.approx(expected)


def test_stack_discounts_with_loyalty_points():
    result = stack_discounts(100.0, 1, "none", points_available=500, points_to_redeem=300)
    expected = 100.0 - 300 / 100
    assert result == pytest.approx(expected)


def test_stack_discounts_full_stack():
    result = stack_discounts(
        100.0, 50, "gold", coupon_code="SAVE10", points_available=1000, points_to_redeem=500
    )
    running = 100.0 * (1 - 0.10) * (1 - 0.07) * (1 - 0.10)
    expected = running - 500 / 100
    assert result == pytest.approx(expected)

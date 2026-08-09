# spec: MODULES.md::discounts.py::AC-2
import pytest

from discounts import (
    COUPONS,
    apply_coupon,
    membership_discount_rate,
    stack_discounts,
    volume_discount_rate,
)


def test_volume_discount_rate_bands():
    assert volume_discount_rate(0) == 0.0
    assert volume_discount_rate(9) == 0.0
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05
    assert volume_discount_rate(50) == 0.10


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


def test_stack_discounts_no_discounts():
    assert stack_discounts(1000.0, 1, "none") == 1000.0


def test_stack_discounts_volume_and_membership_only():
    # qty=50 -> volume 0.10; tier=gold -> membership 0.07; no coupon.
    # Canonical order for this system: volume, then membership, then
    # coupon last — this case has no coupon so it isolates the first two.
    assert stack_discounts(1000.0, 50, "gold") == 837.0


def test_stack_discounts_volume_membership_and_coupon_order():
    # qty=50 -> volume 0.10; tier=gold -> membership 0.07; coupon SAVE10 ->
    # 0.10 applied LAST, to the post-membership amount:
    # 1000 * 0.90 (volume) = 900.0
    # 900.0 * 0.93 (membership) = 837.0
    # 837.0 * 0.90 (coupon, applied last) = 753.3
    result = stack_discounts(1000.0, 50, "gold", coupon_code="SAVE10")
    assert result == 753.3

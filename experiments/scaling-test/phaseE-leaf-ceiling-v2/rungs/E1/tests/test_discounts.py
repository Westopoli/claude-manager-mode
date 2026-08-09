# spec: MODULES.md::discounts.py (all rungs)::AC-2
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from discounts import (
    COUPONS,
    apply_coupon,
    membership_discount_rate,
    stack_discounts,
    volume_discount_rate,
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


def test_membership_discount_rate_unknown_raises_value_error():
    with pytest.raises(ValueError):
        membership_discount_rate("bronze")


def test_coupons_table_shape():
    assert COUPONS["SAVE10"] == {"rate": 0.10, "min_spend": 50.0, "expired": False}


def test_apply_coupon_valid():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises_value_error():
    with pytest.raises(ValueError):
        apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises_value_error():
    with pytest.raises(ValueError):
        apply_coupon(10.0, "SAVE10")


def test_stack_discounts_no_coupon():
    # qty=10 -> volume 0.05, tier=gold -> membership 0.07, applied in that
    # order per the parent decision recorded in .swarm/answers/leaf-E1-Q1.md
    result = stack_discounts(100.0, 10, "gold", coupon_code=None)
    assert result == 88.35


def test_stack_discounts_with_coupon_applied_last():
    # coupon applied to the post-membership amount, per the recorded decision
    result = stack_discounts(100.0, 10, "gold", coupon_code="SAVE10")
    assert result == 79.52

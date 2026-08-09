import pytest

from discounts import bulk_discount_rate, apply_discount


def test_bulk_discount_rate_below_ten_is_zero():
    assert bulk_discount_rate(0) == 0.0
    assert bulk_discount_rate(9) == 0.0


def test_bulk_discount_rate_mid_tier():
    assert bulk_discount_rate(10) == 0.05
    assert bulk_discount_rate(49) == 0.05


def test_bulk_discount_rate_top_tier():
    assert bulk_discount_rate(50) == 0.10
    assert bulk_discount_rate(500) == 0.10


def test_apply_discount_rounds_to_two_decimals():
    assert apply_discount(100.0, 0.10) == 90.0


def test_apply_discount_raises_on_rate_out_of_range():
    with pytest.raises(ValueError):
        apply_discount(100.0, -0.1)
    with pytest.raises(ValueError):
        apply_discount(100.0, 1.1)

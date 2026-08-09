# spec: MODULES.md::loyalty.py::AC-9
import pytest

from loyalty import redeem_loyalty_points


def test_redeem_loyalty_points_happy_path():
    # 500 points = $5.00 off
    assert redeem_loyalty_points(50.0, 1000, 500) == 45.0


def test_redeem_loyalty_points_floors_at_zero():
    assert redeem_loyalty_points(2.0, 1000, 1000) == 0.0


def test_redeem_loyalty_points_zero_redeemed_is_noop():
    assert redeem_loyalty_points(50.0, 1000, 0) == 50.0


def test_redeem_loyalty_points_exceeds_available_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(50.0, 100, 200)


def test_redeem_loyalty_points_negative_redeem_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(50.0, 1000, -1)

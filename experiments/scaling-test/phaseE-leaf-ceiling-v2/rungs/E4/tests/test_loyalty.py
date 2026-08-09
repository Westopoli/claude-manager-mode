# spec: MODULES.md::loyalty.py::AC-1
import pytest

from loyalty import redeem_loyalty_points


def test_redeem_loyalty_points_happy_path():
    # 100 points = $1. 250 points => $2.50 off.
    assert redeem_loyalty_points(20.0, 500, 250) == 17.5


def test_redeem_loyalty_points_floors_at_zero():
    assert redeem_loyalty_points(1.0, 500, 500) == 0.0


def test_redeem_loyalty_points_over_available_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(20.0, 100, 200)


def test_redeem_loyalty_points_negative_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(20.0, 100, -1)

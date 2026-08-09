import pytest

from shipping import shipping_cost


def test_shipping_cost_basic():
    # 2.5 + 0.4*10 + 0.05*100 = 2.5 + 4.0 + 5.0 = 11.5
    assert shipping_cost(10, 100) == 11.5


def test_shipping_cost_rounds_to_2_decimals():
    # 2.5 + 0.4*1 + 0.05*1 = 2.5 + 0.4 + 0.05 = 2.95
    assert shipping_cost(1, 1) == 2.95


def test_shipping_cost_rounds_non_trivial_fraction():
    # 2.5 + 0.4*3.333 + 0.05*7.777 = 2.5 + 1.3332 + 0.38885 = 4.22205 -> 4.22
    assert shipping_cost(3.333, 7.777) == 4.22


def test_shipping_cost_small_positive_values():
    # 2.5 + 0.4*0.01 + 0.05*0.01 = 2.5 + 0.004 + 0.0005 = 2.5045 -> 2.5
    assert shipping_cost(0.01, 0.01) == 2.5


def test_shipping_cost_zero_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(0, 100)


def test_shipping_cost_zero_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10, 0)


def test_shipping_cost_negative_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(-5, 100)


def test_shipping_cost_negative_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10, -5)


def test_shipping_cost_returns_float():
    result = shipping_cost(10, 100)
    assert isinstance(result, float)

# spec: MODULES.md::shipping.py::AC-6
import pytest

from shipping import shipping_cost


def test_shipping_cost_standard():
    # base = 2.5 + 0.4*10 + 0.05*100 = 2.5 + 4.0 + 5.0 = 11.5
    assert shipping_cost(10.0, 100.0, express=False) == 11.5


def test_shipping_cost_express_multiplies_by_1_5():
    # base 11.5 * 1.5 = 17.25
    assert shipping_cost(10.0, 100.0, express=True) == 17.25


def test_shipping_cost_zero_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(0.0, 100.0, express=False)


def test_shipping_cost_negative_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(-1.0, 100.0, express=False)


def test_shipping_cost_zero_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10.0, 0.0, express=False)


def test_shipping_cost_negative_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10.0, -5.0, express=False)

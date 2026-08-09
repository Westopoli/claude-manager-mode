# spec: MODULES.md::shipping.py::AC-1
import pytest

from shipping import shipping_cost


def test_shipping_cost_standard():
    expected = round(2.5 + 0.4 * 2.0 + 0.05 * 10.0, 2)
    assert shipping_cost(2.0, 10.0, False) == expected


def test_shipping_cost_express_multiplies_by_1_5():
    base = round(2.5 + 0.4 * 2.0 + 0.05 * 10.0, 2)
    expected = round(base * 1.5, 2)
    assert shipping_cost(2.0, 10.0, True) == expected


def test_shipping_cost_non_positive_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(0.0, 10.0, False)


def test_shipping_cost_non_positive_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(2.0, -1.0, False)

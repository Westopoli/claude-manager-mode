# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-8
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.
State-check tests for shipping.py only.
"""
import pytest


def test_shipping_cost_standard():
    import shipping

    assert shipping.shipping_cost(2.0, 10.0, False) == 3.8


def test_shipping_cost_express_multiplies_by_1_5():
    import shipping

    # base = 2.5 + 0.4*2.0 + 0.05*10.0 = 3.8; express -> 3.8*1.5 = 5.7
    assert shipping.shipping_cost(2.0, 10.0, True) == 5.7


def test_shipping_cost_non_positive_weight_raises():
    import shipping

    with pytest.raises(ValueError):
        shipping.shipping_cost(0.0, 10.0, False)


def test_shipping_cost_non_positive_distance_raises():
    import shipping

    with pytest.raises(ValueError):
        shipping.shipping_cost(2.0, -1.0, False)

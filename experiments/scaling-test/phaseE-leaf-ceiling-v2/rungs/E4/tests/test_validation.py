# spec: MODULES.md::validation.py::AC-1
import pytest

from validation import validate_order


def base_order(**overrides):
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "US-CA",
        "membership_tier": "none",
        "currency": "USD",
    }
    order.update(overrides)
    return order


def test_validate_order_happy_path_returns_none():
    assert validate_order(base_order()) is None


def test_validate_order_missing_items_raises():
    order = base_order()
    del order["items"]
    with pytest.raises(ValueError, match="items"):
        validate_order(order)


def test_validate_order_empty_items_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items=[]))


def test_validate_order_missing_region_raises():
    order = base_order()
    del order["region"]
    with pytest.raises(ValueError, match="region"):
        validate_order(order)


def test_validate_order_missing_membership_tier_raises():
    order = base_order()
    del order["membership_tier"]
    with pytest.raises(ValueError, match="membership_tier"):
        validate_order(order)


def test_validate_order_missing_currency_raises():
    order = base_order()
    del order["currency"]
    with pytest.raises(ValueError, match="currency"):
        validate_order(order)


def test_validate_order_wrong_typed_items_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items="not-a-list"))

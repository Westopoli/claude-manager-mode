# spec: MODULES.md::validation.py::AC-4
import pytest

from validation import validate_order


def _base_order():
    return {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }


def test_validate_order_accepts_well_formed_order():
    assert validate_order(_base_order()) is None


def test_validate_order_missing_items_raises():
    order = _base_order()
    del order["items"]
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_empty_items_list_raises():
    order = _base_order()
    order["items"] = []
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_wrong_typed_items_raises():
    order = _base_order()
    order["items"] = "not-a-list"
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_missing_region_raises():
    order = _base_order()
    del order["region"]
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_missing_membership_tier_raises():
    order = _base_order()
    del order["membership_tier"]
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_missing_currency_raises():
    order = _base_order()
    del order["currency"]
    with pytest.raises(ValueError):
        validate_order(order)

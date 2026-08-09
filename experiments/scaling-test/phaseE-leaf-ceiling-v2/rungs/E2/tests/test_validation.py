# spec: /Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseE-leaf-ceiling-v2/MODULES.md::validation.py::AC-3
import pytest

import validation


VALID_ORDER = {
    "items": [{"sku": "widget", "qty": 1}],
    "region": "US-CA",
    "membership_tier": "gold",
    "currency": "USD",
}


def test_validate_order_accepts_valid_order():
    assert validation.validate_order(dict(VALID_ORDER)) is None


def test_validate_order_missing_items_raises():
    order = dict(VALID_ORDER)
    del order["items"]
    with pytest.raises(ValueError, match="items"):
        validation.validate_order(order)


def test_validate_order_empty_items_raises():
    order = dict(VALID_ORDER)
    order["items"] = []
    with pytest.raises(ValueError, match="items"):
        validation.validate_order(order)


def test_validate_order_missing_region_raises():
    order = dict(VALID_ORDER)
    del order["region"]
    with pytest.raises(ValueError, match="region"):
        validation.validate_order(order)


def test_validate_order_missing_membership_tier_raises():
    order = dict(VALID_ORDER)
    del order["membership_tier"]
    with pytest.raises(ValueError, match="membership_tier"):
        validation.validate_order(order)


def test_validate_order_missing_currency_raises():
    order = dict(VALID_ORDER)
    del order["currency"]
    with pytest.raises(ValueError, match="currency"):
        validation.validate_order(order)

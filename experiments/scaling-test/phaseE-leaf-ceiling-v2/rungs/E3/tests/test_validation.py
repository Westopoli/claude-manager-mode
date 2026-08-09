# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-6
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.
State-check tests for validation.py only.
"""
import pytest


VALID = {
    "items": [{"sku": "widget", "qty": 1}],
    "region": "US-CA",
    "membership_tier": "gold",
    "currency": "USD",
}


def test_validate_order_happy_path_returns_none():
    import validation

    assert validation.validate_order(dict(VALID)) is None


def test_validate_order_missing_items_raises():
    import validation

    order = dict(VALID)
    del order["items"]
    with pytest.raises(ValueError):
        validation.validate_order(order)


def test_validate_order_empty_items_raises():
    import validation

    order = dict(VALID)
    order["items"] = []
    with pytest.raises(ValueError):
        validation.validate_order(order)


def test_validate_order_wrong_type_items_raises():
    import validation

    order = dict(VALID)
    order["items"] = "not-a-list"
    with pytest.raises(ValueError):
        validation.validate_order(order)


def test_validate_order_missing_region_raises():
    import validation

    order = dict(VALID)
    del order["region"]
    with pytest.raises(ValueError):
        validation.validate_order(order)


def test_validate_order_missing_membership_tier_raises():
    import validation

    order = dict(VALID)
    del order["membership_tier"]
    with pytest.raises(ValueError):
        validation.validate_order(order)


def test_validate_order_missing_currency_raises():
    import validation

    order = dict(VALID)
    del order["currency"]
    with pytest.raises(ValueError):
        validation.validate_order(order)

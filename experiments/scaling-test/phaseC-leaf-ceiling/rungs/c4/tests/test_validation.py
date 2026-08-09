import pytest
from validation import validate_order


def base_order(**overrides):
    order = {
        "items": [{"sku": "widget", "qty": 2}],
        "region": "US-CA",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 5.0, "express": False},
        "currency": "USD",
    }
    order.update(overrides)
    return order


def test_valid_order_passes():
    assert validate_order(base_order()) is None


def test_missing_items_raises():
    order = base_order()
    del order["items"]
    with pytest.raises(ValueError, match="items"):
        validate_order(order)


def test_empty_items_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items=[]))


def test_item_missing_sku_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items=[{"qty": 1}]))


def test_item_qty_not_positive_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items=[{"sku": "widget", "qty": 0}]))


def test_item_qty_wrong_type_raises():
    with pytest.raises(ValueError, match="items"):
        validate_order(base_order(items=[{"sku": "widget", "qty": "2"}]))


def test_invalid_region_raises():
    with pytest.raises(ValueError, match="region"):
        validate_order(base_order(region="US-TX"))


def test_invalid_membership_tier_raises():
    with pytest.raises(ValueError, match="membership_tier"):
        validate_order(base_order(membership_tier="diamond"))


def test_missing_shipping_raises():
    order = base_order()
    del order["shipping"]
    with pytest.raises(ValueError, match="shipping"):
        validate_order(order)


def test_shipping_weight_not_positive_raises():
    with pytest.raises(ValueError, match="shipping"):
        validate_order(base_order(shipping={"weight_kg": 0, "distance_km": 5.0, "express": False}))


def test_shipping_distance_not_positive_raises():
    with pytest.raises(ValueError, match="shipping"):
        validate_order(base_order(shipping={"weight_kg": 1.0, "distance_km": -1.0, "express": False}))


def test_shipping_express_wrong_type_raises():
    with pytest.raises(ValueError, match="shipping"):
        validate_order(base_order(shipping={"weight_kg": 1.0, "distance_km": 5.0, "express": "no"}))


def test_invalid_currency_raises():
    with pytest.raises(ValueError, match="currency"):
        validate_order(base_order(currency="JPY"))


def test_coupon_code_wrong_type_raises():
    with pytest.raises(ValueError, match="coupon_code"):
        validate_order(base_order(coupon_code=123))


def test_loyalty_points_negative_raises():
    with pytest.raises(ValueError, match="loyalty_points_to_redeem"):
        validate_order(base_order(loyalty_points_to_redeem=-5))


def test_loyalty_points_wrong_type_raises():
    with pytest.raises(ValueError, match="loyalty_points_to_redeem"):
        validate_order(base_order(loyalty_points_to_redeem=5.5))


def test_optional_fields_valid():
    order = base_order(coupon_code="SAVE10", loyalty_points_to_redeem=100)
    assert validate_order(order) is None

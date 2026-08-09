import pytest

from pricing_engine import (
    validate_order,
    line_item_subtotal,
    volume_discount_rate,
    membership_discount_rate,
    calculate_tax,
    shipping_cost,
    build_invoice,
)


def make_order(**overrides):
    order = {
        "items": [{"sku": "A1", "unit_price": 10.0, "qty": 2}],
        "region": "US-CA",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 10.0, "express": False},
    }
    order.update(overrides)
    return order


# ---- validate_order ----

def test_validate_order_ok():
    validate_order(make_order())  # should not raise


def test_validate_order_missing_items():
    order = make_order()
    del order["items"]
    with pytest.raises(ValueError, match="items"):
        validate_order(order)


def test_validate_order_missing_region():
    order = make_order()
    del order["region"]
    with pytest.raises(ValueError, match="region"):
        validate_order(order)


def test_validate_order_missing_membership_tier():
    order = make_order()
    del order["membership_tier"]
    with pytest.raises(ValueError, match="membership_tier"):
        validate_order(order)


def test_validate_order_missing_shipping():
    order = make_order()
    del order["shipping"]
    with pytest.raises(ValueError, match="shipping"):
        validate_order(order)


def test_validate_order_empty_items():
    order = make_order(items=[])
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_nonpositive_unit_price():
    order = make_order(items=[{"sku": "A1", "unit_price": 0, "qty": 1}])
    with pytest.raises(ValueError):
        validate_order(order)


def test_validate_order_nonpositive_qty():
    order = make_order(items=[{"sku": "A1", "unit_price": 5.0, "qty": 0}])
    with pytest.raises(ValueError):
        validate_order(order)


# ---- line_item_subtotal ----

def test_line_item_subtotal_basic():
    items = [
        {"sku": "A1", "unit_price": 10.0, "qty": 2},
        {"sku": "B2", "unit_price": 3.5, "qty": 3},
    ]
    per_sku, subtotal, total_qty = line_item_subtotal(items)
    assert per_sku == {"A1": 20.0, "B2": 10.5}
    assert subtotal == 30.5
    assert total_qty == 5


def test_line_item_subtotal_rounding():
    items = [{"sku": "X", "unit_price": 0.1, "qty": 3}]
    per_sku, subtotal, total_qty = line_item_subtotal(items)
    assert per_sku == {"X": 0.3}
    assert subtotal == 0.3
    assert total_qty == 3


# ---- volume_discount_rate ----

def test_volume_discount_rate_none():
    assert volume_discount_rate(5) == 0.0
    assert volume_discount_rate(9) == 0.0


def test_volume_discount_rate_mid():
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05


def test_volume_discount_rate_high():
    assert volume_discount_rate(50) == 0.10
    assert volume_discount_rate(1000) == 0.10


# ---- membership_discount_rate ----

def test_membership_discount_rate_values():
    assert membership_discount_rate("none") == 0.0
    assert membership_discount_rate("silver") == 0.03
    assert membership_discount_rate("gold") == 0.07
    assert membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_invalid():
    with pytest.raises(ValueError):
        membership_discount_rate("bronze")


# ---- discount stacking: sequential-multiplicative, not additive ----

def test_discount_stacking_is_sequential_not_additive():
    subtotal = 1000.0
    volume_rate = 0.10  # qty >= 50
    membership_rate = 0.12  # platinum

    after_volume = subtotal * (1 - volume_rate)
    after_membership = after_volume * (1 - membership_rate)
    sequential_expected = round(after_membership, 2)

    additive_wrong = round(subtotal * (1 - (volume_rate + membership_rate)), 2)

    # sanity: the two approaches must actually differ for this input
    assert sequential_expected != additive_wrong

    order = make_order(
        items=[{"sku": "A1", "unit_price": 20.0, "qty": 50}],
        membership_tier="platinum",
    )
    invoice = build_invoice(order)
    assert invoice["post_discount_amount"] == sequential_expected
    assert invoice["post_discount_amount"] != additive_wrong


# ---- calculate_tax ----

def test_calculate_tax_known_regions():
    assert calculate_tax(100.0, "US-CA") == 8.25
    assert calculate_tax(100.0, "US-OR") == 0.0
    assert calculate_tax(100.0, "US-NY") == 8.88
    assert calculate_tax(100.0, "EU") == 20.0


def test_calculate_tax_unknown_region():
    with pytest.raises(ValueError):
        calculate_tax(100.0, "US-TX")


# ---- shipping_cost ----

def test_shipping_cost_standard():
    # base = 2.5 + 0.4*2 + 0.05*20 = 2.5 + 0.8 + 1.0 = 4.3
    assert shipping_cost(2.0, 20.0, False) == 4.3


def test_shipping_cost_express():
    # base = 4.3, express => 4.3 * 1.5 = 6.45
    assert shipping_cost(2.0, 20.0, True) == 6.45


def test_shipping_cost_invalid_weight():
    with pytest.raises(ValueError):
        shipping_cost(0, 10.0, False)


def test_shipping_cost_invalid_distance():
    with pytest.raises(ValueError):
        shipping_cost(1.0, 0, False)


# ---- build_invoice ----

def test_build_invoice_full_pipeline_no_discounts():
    order = make_order(
        items=[{"sku": "A1", "unit_price": 10.0, "qty": 2}],
        region="US-CA",
        membership_tier="none",
        shipping={"weight_kg": 1.0, "distance_km": 10.0, "express": False},
    )
    invoice = build_invoice(order)

    # subtotal = 20.0, total_qty=2 -> no volume discount, no membership discount
    assert invoice["line_items"] == {"A1": 20.0}
    assert invoice["subtotal"] == 20.0
    assert invoice["discount_amount"] == 0.0
    assert invoice["post_discount_amount"] == 20.0

    # shipping base = 2.5 + 0.4*1 + 0.05*10 = 2.5+0.4+0.5 = 3.4
    assert invoice["shipping"] == 3.4

    # tax = round(20.0 * 0.0825, 2) = 1.65
    assert invoice["tax"] == 1.65

    # total = 20.0 + 1.65 + 3.4 = 25.05
    assert invoice["total"] == 25.05


def test_build_invoice_with_discounts_and_tax():
    order = make_order(
        items=[{"sku": "A1", "unit_price": 20.0, "qty": 50}],
        region="EU",
        membership_tier="gold",
        shipping={"weight_kg": 5.0, "distance_km": 100.0, "express": True},
    )
    invoice = build_invoice(order)

    subtotal = 1000.0
    after_volume = subtotal * (1 - 0.10)  # 900.0
    after_membership = after_volume * (1 - 0.07)  # 837.0
    expected_post_discount = round(after_membership, 2)
    expected_discount_amount = round(subtotal - after_membership, 2)

    assert invoice["subtotal"] == 1000.0
    assert invoice["post_discount_amount"] == expected_post_discount
    assert invoice["discount_amount"] == expected_discount_amount

    expected_tax = round(after_membership * 0.20, 2)
    assert invoice["tax"] == expected_tax

    # shipping base = 2.5 + 0.4*5 + 0.05*100 = 2.5+2.0+5.0 = 9.5, express*1.5=14.25
    assert invoice["shipping"] == 14.25

    expected_total = round(after_membership + expected_tax + 14.25, 2)
    assert invoice["total"] == expected_total


def test_build_invoice_propagates_validation_error():
    order = make_order()
    del order["region"]
    with pytest.raises(ValueError):
        build_invoice(order)


def test_build_invoice_propagates_membership_error():
    order = make_order(membership_tier="bronze")
    with pytest.raises(ValueError):
        build_invoice(order)

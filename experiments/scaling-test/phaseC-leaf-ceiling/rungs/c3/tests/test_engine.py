import pytest

import catalog
import discounts
import engine


def test_calculate_tax_known_regions():
    assert engine.calculate_tax(100.0, "US-CA") == round(100.0 * 0.0825, 2)
    assert engine.calculate_tax(100.0, "US-OR") == 0.0
    assert engine.calculate_tax(100.0, "US-NY") == round(100.0 * 0.08875, 2)
    assert engine.calculate_tax(100.0, "EU") == round(100.0 * 0.20, 2)


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        engine.calculate_tax(100.0, "US-TX")


def test_shipping_cost_standard():
    result = engine.shipping_cost(2.0, 10.0, False)
    expected = round(2.5 + 0.4 * 2.0 + 0.05 * 10.0, 2)
    assert result == expected


def test_shipping_cost_express_multiplier():
    base = round(2.5 + 0.4 * 2.0 + 0.05 * 10.0, 2)
    expected = round(base * 1.5, 2)
    result = engine.shipping_cost(2.0, 10.0, True)
    assert result == expected


def test_shipping_cost_non_positive_weight_raises():
    with pytest.raises(ValueError):
        engine.shipping_cost(0.0, 10.0, False)


def test_shipping_cost_non_positive_distance_raises():
    with pytest.raises(ValueError):
        engine.shipping_cost(2.0, -1.0, False)


def test_audit_log_starts_and_appends():
    engine.AUDIT_LOG.clear()
    assert engine.AUDIT_LOG == []

    order = {
        "items": [{"sku": "widget", "qty": 3}],
        "region": "US-OR",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 5.0, "express": False},
    }
    engine.build_invoice(order)
    assert len(engine.AUDIT_LOG) == 1
    assert "order_total" in engine.AUDIT_LOG[0]


def test_build_invoice_no_discounts_no_coupon():
    engine.AUDIT_LOG.clear()
    order = {
        "items": [{"sku": "widget", "qty": 2}],
        "region": "US-OR",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 5.0, "express": False},
    }
    invoice = engine.build_invoice(order)

    line_items, subtotal, total_qty = catalog.build_line_items(order["items"])
    assert invoice["line_items"] == line_items
    assert invoice["subtotal"] == subtotal
    # qty=2 -> no volume discount, tier none -> no membership discount, no coupon
    assert invoice["post_discount_amount"] == subtotal

    tax = engine.calculate_tax(subtotal, "US-OR")
    shipping = engine.shipping_cost(1.0, 5.0, False)
    assert invoice["tax"] == tax
    assert invoice["shipping"] == shipping
    assert invoice["total"] == round(subtotal + tax + shipping, 2)


def test_build_invoice_orchestration_order_volume_then_membership_then_coupon():
    # engine.py's stated canonical order: volume, then membership, then
    # coupon last (applied to the post-membership amount).
    engine.AUDIT_LOG.clear()
    items = [{"sku": "widget", "qty": 10}, {"sku": "gadget", "qty": 5}]
    order = {
        "items": items,
        "region": "US-CA",
        "membership_tier": "gold",
        "coupon_code": "SAVE10",
        "shipping": {"weight_kg": 3.0, "distance_km": 20.0, "express": True},
    }
    invoice = engine.build_invoice(order)

    _, subtotal, total_qty = catalog.build_line_items(items)

    volume_rate = discounts.volume_discount_rate(total_qty)
    after_volume = round(subtotal * (1 - volume_rate), 2)

    membership_rate = discounts.membership_discount_rate("gold")
    after_membership = round(after_volume * (1 - membership_rate), 2)

    after_coupon = discounts.apply_coupon(after_membership, "SAVE10")

    assert invoice["post_discount_amount"] == after_coupon

    tax = engine.calculate_tax(after_coupon, "US-CA")
    shipping = engine.shipping_cost(3.0, 20.0, True)
    assert invoice["tax"] == tax
    assert invoice["shipping"] == shipping
    assert invoice["total"] == round(after_coupon + tax + shipping, 2)


def test_build_invoice_shipping_not_taxed():
    # shipping is added after tax, and is not itself included in the taxed
    # amount.
    engine.AUDIT_LOG.clear()
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "EU",
        "membership_tier": "none",
        "shipping": {"weight_kg": 50.0, "distance_km": 100.0, "express": False},
    }
    invoice = engine.build_invoice(order)
    expected_tax = engine.calculate_tax(invoice["post_discount_amount"], "EU")
    assert invoice["tax"] == expected_tax
    # sanity: shipping is large relative to subtotal, tax must not scale with it
    assert invoice["shipping"] > invoice["post_discount_amount"]


def test_build_invoice_missing_coupon_code_defaults_none():
    engine.AUDIT_LOG.clear()
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "US-OR",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 1.0, "express": False},
    }
    invoice = engine.build_invoice(order)
    assert invoice["post_discount_amount"] == invoice["subtotal"]


def test_build_invoice_unknown_region_raises():
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "MARS",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 1.0, "express": False},
    }
    with pytest.raises(ValueError):
        engine.build_invoice(order)


def test_build_invoice_insufficient_stock_raises():
    order = {
        "items": [{"sku": "gizmo", "qty": 1}],
        "region": "US-OR",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 1.0, "express": False},
    }
    with pytest.raises(ValueError):
        engine.build_invoice(order)

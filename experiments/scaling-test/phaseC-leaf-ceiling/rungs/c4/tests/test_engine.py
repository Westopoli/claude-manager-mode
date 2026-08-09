import pytest
import engine
from engine import shipping_cost, build_invoice, AUDIT_LOG


def make_order(**overrides):
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "region": "US-CA",
        "membership_tier": "none",
        "shipping": {"weight_kg": 1.0, "distance_km": 10.0, "express": False},
        "currency": "USD",
    }
    order.update(overrides)
    return order


def test_shipping_cost_basic():
    assert shipping_cost(1.0, 10.0, False) == 3.4


def test_shipping_cost_express_multiplier():
    assert shipping_cost(1.0, 10.0, True) == round(3.4 * 1.5, 2)


def test_shipping_cost_nonpositive_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(0.0, 10.0, False)


def test_shipping_cost_nonpositive_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(1.0, -1.0, False)


def test_build_invoice_basic_taxable_order():
    order = make_order()
    invoice = build_invoice(order)
    assert invoice["subtotal_usd"] == 9.99
    assert invoice["post_discount_usd"] == 9.99
    assert invoice["tax_usd"] == round(9.99 * 0.0825, 2)
    assert invoice["shipping_usd"] == 3.4
    expected_total = round(9.99 + round(9.99 * 0.0825, 2) + 3.4, 2)
    assert invoice["total_usd"] == expected_total
    assert invoice["total_display"] == f"${expected_total:.2f}"


def test_build_invoice_tax_exempt_item_has_zero_tax():
    order = make_order(items=[{"sku": "book", "qty": 1}])
    invoice = build_invoice(order)
    assert invoice["tax_usd"] == 0.0
    expected_total = round(14.00 + 0.0 + 3.4, 2)
    assert invoice["total_usd"] == expected_total


def test_build_invoice_eu_uses_canonical_020_rate_not_021():
    # Regression guard for the seeded 0.21-vs-0.20 EU rate contradiction:
    # the canonical tax table rate (0.20) must be used regardless of order value,
    # even for high-value EU orders that might tempt a "reduced 0.21 for luxury" rule.
    order = make_order(region="EU", items=[{"sku": "widget", "qty": 60}], currency="EUR")
    invoice = build_invoice(order)
    subtotal = round(9.99 * 60, 2)
    assert subtotal > 500
    # qty 60 also crosses the volume-discount threshold (>=50 -> 10% off),
    # so tax is computed on the post-discount amount, not the raw subtotal.
    post_discount = round(subtotal * (1 - 0.10), 2)
    expected_tax = round(post_discount * 0.20, 2)
    wrong_tax_if_021 = round(post_discount * 0.21, 2)
    assert invoice["tax_usd"] == expected_tax
    assert invoice["tax_usd"] != wrong_tax_if_021


def test_build_invoice_currency_conversion_and_display():
    order = make_order(region="EU", currency="EUR")
    invoice = build_invoice(order)
    tax = round(9.99 * 0.20, 2)
    total_usd = round(9.99 + tax + 3.4, 2)
    expected_eur = round(total_usd * 0.92, 2)
    assert invoice["total_usd"] == total_usd
    assert invoice["total_display"] == f"€{expected_eur:.2f}"


def test_build_invoice_invalid_order_raises():
    order = make_order(region="US-TX")
    with pytest.raises(ValueError):
        build_invoice(order)


def test_build_invoice_appends_audit_log():
    before = len(AUDIT_LOG)
    order = make_order()
    invoice = build_invoice(order)
    assert len(AUDIT_LOG) == before + 1
    assert AUDIT_LOG[-1] == {"order_total_usd": invoice["total_usd"]}


def test_build_invoice_applies_coupon_and_loyalty():
    order = make_order(
        items=[{"sku": "widget", "qty": 10}],
        coupon_code="SAVE10",
        loyalty_points_to_redeem=100,
    )
    invoice = build_invoice(order)
    subtotal = round(9.99 * 10, 2)
    vol = 0.05
    mem = 0.0
    running = subtotal * (1 - vol) * (1 - mem)
    running = running * (1 - 0.10)
    running = round(running - 100 / 100, 2)
    assert invoice["post_discount_usd"] == pytest.approx(running)

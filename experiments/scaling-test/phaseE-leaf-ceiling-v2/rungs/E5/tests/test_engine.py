# spec: MODULES.md::engine.py::AC-3
import copy

import pytest

import audit_log
import catalog
import currency
import discounts
import inventory
import shipping
import tax
from engine import build_invoice


@pytest.fixture(autouse=True)
def _restore_shared_state():
    # catalog.CATALOG and audit_log.AUDIT_LOG are module-level singletons
    # that build_invoice mutates as real side effects (stock reservation,
    # audit logging). Snapshot and restore around every test in this file
    # so one test's reservation/logging can't leak into another's
    # expectations.
    catalog_snapshot = copy.deepcopy(catalog.CATALOG)
    audit_snapshot = list(audit_log.AUDIT_LOG)
    yield
    catalog.CATALOG.clear()
    catalog.CATALOG.update(catalog_snapshot)
    audit_log.AUDIT_LOG.clear()
    audit_log.AUDIT_LOG.extend(audit_snapshot)


def _order(**overrides):
    order = {
        "order_id": "ORD-1",
        "items": [{"sku": "widget", "qty": 60}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "EUR",
        "weight_kg": 5.0,
        "distance_km": 50.0,
        "express": False,
    }
    order.update(overrides)
    return order


def test_build_invoice_full_pipeline_result():
    result = build_invoice(_order())
    assert result["line_items"] == {"widget": 599.4}
    assert result["subtotal"] == 599.4
    assert result["post_discount_amount"] == 501.7
    assert result["shipping_cost"] == 7.0
    assert result["tax"] == 41.97
    assert result["total_usd"] == 550.67
    assert result["total"] == 506.62
    assert result["total_formatted"] == "€506.62"


def test_build_invoice_reserves_stock_as_a_real_side_effect():
    before = catalog.CATALOG["widget"]["stock"]
    build_invoice(_order())
    after = catalog.CATALOG["widget"]["stock"]
    assert after == before - 60


def test_build_invoice_records_audit_log_entry_with_total_usd():
    audit_log.AUDIT_LOG.clear()
    result = build_invoice(_order(order_id="ORD-AUDIT"))
    assert audit_log.AUDIT_LOG == [
        {"order_id": "ORD-AUDIT", "total": result["total_usd"]}
    ]


def test_build_invoice_applies_loyalty_redemption_when_present():
    result = build_invoice(_order(points_available=100000, points_to_redeem=10000))
    # 10000 points = $100.00 off post_discount_amount (501.7 -> 401.7),
    # which flows through shipping/tax/total the same way the no-loyalty
    # pipeline does.
    assert result["post_discount_amount"] == 401.7


def test_build_invoice_skips_loyalty_when_absent():
    result = build_invoice(_order())
    assert result["post_discount_amount"] == 501.7


def test_build_invoice_rejects_invalid_order():
    with pytest.raises(ValueError):
        build_invoice(_order(region=None))


def test_build_invoice_calls_real_collaborators_not_reimplementations():
    """Composition rule (mockist): this leaf's impl_files has 12 entries,
    so this test asserts build_invoice actually CALLS its collaborator
    modules rather than only checking final output state. Each spy wraps
    the real implementation (so behavior/return values are unaffected) and
    records whether it was invoked."""
    calls = {
        "build_line_items": 0,
        "reserve_stock": 0,
        "stack_discounts": 0,
        "shipping_cost": 0,
        "tax": 0,
        "convert": 0,
        "record": 0,
    }

    real_build_line_items = catalog.build_line_items

    def spy_build_line_items(items):
        calls["build_line_items"] += 1
        return real_build_line_items(items)

    real_reserve_stock = inventory.reserve_stock

    def spy_reserve_stock(cat, sku, qty):
        calls["reserve_stock"] += 1
        return real_reserve_stock(cat, sku, qty)

    real_stack_discounts = discounts.stack_discounts

    def spy_stack_discounts(*args, **kwargs):
        calls["stack_discounts"] += 1
        return real_stack_discounts(*args, **kwargs)

    real_shipping_cost = shipping.shipping_cost

    def spy_shipping_cost(*args, **kwargs):
        calls["shipping_cost"] += 1
        return real_shipping_cost(*args, **kwargs)

    real_calculate_tax = tax.calculate_tax

    def spy_calculate_tax(*args, **kwargs):
        calls["tax"] += 1
        return real_calculate_tax(*args, **kwargs)

    real_convert = currency.convert

    def spy_convert(*args, **kwargs):
        calls["convert"] += 1
        return real_convert(*args, **kwargs)

    real_record = audit_log.record

    def spy_record(*args, **kwargs):
        calls["record"] += 1
        return real_record(*args, **kwargs)

    catalog.build_line_items = spy_build_line_items
    inventory.reserve_stock = spy_reserve_stock
    discounts.stack_discounts = spy_stack_discounts
    shipping.shipping_cost = spy_shipping_cost
    tax.calculate_tax = spy_calculate_tax
    currency.convert = spy_convert
    audit_log.record = spy_record
    try:
        build_invoice(_order(items=[{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}]))
    finally:
        catalog.build_line_items = real_build_line_items
        inventory.reserve_stock = real_reserve_stock
        discounts.stack_discounts = real_stack_discounts
        shipping.shipping_cost = real_shipping_cost
        tax.calculate_tax = real_calculate_tax
        currency.convert = real_convert
        audit_log.record = real_record

    assert calls["build_line_items"] == 1
    assert calls["reserve_stock"] == 2  # one call per distinct line item
    assert calls["stack_discounts"] == 1
    assert calls["shipping_cost"] == 1
    assert calls["tax"] == 1
    assert calls["convert"] == 1
    assert calls["record"] == 1

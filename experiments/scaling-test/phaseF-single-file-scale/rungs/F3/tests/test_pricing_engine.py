# spec: ../../SPEC.md::F3::AC-1
"""Full-scope test suite for src/pricing_engine.py (Phase F, rung F3).

Mirrors Phase E rung E5's per-module test files (tests/test_catalog.py,
test_discounts.py, test_engine.py, test_validation.py, test_currency.py,
test_shipping.py, test_notifications.py, test_tax.py, test_loyalty.py,
test_reporting.py, test_audit_log.py, test_inventory.py) collapsed into one
file, since pricing_engine.py collapses all 12 modules into one file. Same
expected values throughout — this is a scope-matched rung, not a new domain.
"""
import copy

import pytest

import pricing_engine
from pricing_engine import (
    AUDIT_LOG,
    CATALOG,
    COUPONS,
    EXCHANGE_RATES,
    apply_coupon,
    build_invoice,
    build_line_items,
    calculate_tax,
    convert,
    format_currency,
    low_stock_alert,
    membership_discount_rate,
    record,
    redeem_loyalty_points,
    release_stock,
    reserve_stock,
    shipping_cost,
    stack_discounts,
    summarize_orders,
    validate_order,
    volume_discount_rate,
)


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------

def test_catalog_contents():
    assert CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_build_line_items_happy_path():
    per_sku, subtotal, total_qty = build_line_items([
        {"sku": "widget", "qty": 2},
        {"sku": "gadget", "qty": 1},
    ])
    assert per_sku == {"widget": 19.98, "gadget": 24.50}
    assert subtotal == 44.48
    assert total_qty == 3


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        build_line_items([{"sku": "nonexistent", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gadget", "qty": 999}])


# ---------------------------------------------------------------------------
# discounts
# ---------------------------------------------------------------------------

def test_volume_discount_rate_bands():
    assert volume_discount_rate(0) == 0.0
    assert volume_discount_rate(9) == 0.0
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05
    assert volume_discount_rate(50) == 0.10


def test_membership_discount_rate_tiers():
    assert membership_discount_rate("none") == 0.0
    assert membership_discount_rate("silver") == 0.03
    assert membership_discount_rate("gold") == 0.07
    assert membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        membership_discount_rate("bogus")


def test_coupons_table():
    assert COUPONS["SAVE10"] == {"rate": 0.10, "min_spend": 50.0, "expired": False}


def test_apply_coupon_happy_path():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        apply_coupon(10.0, "SAVE10")


def test_stack_discounts_no_discounts():
    assert stack_discounts(1000.0, 1, "none") == 1000.0


def test_stack_discounts_volume_and_membership_only():
    # qty=50 -> volume 0.10; tier=gold -> membership 0.07; no coupon.
    assert stack_discounts(1000.0, 50, "gold") == 837.0


def test_stack_discounts_volume_membership_and_coupon_order():
    # Resolves the seeded coupon-order contradiction (see pricing_engine.py's
    # module docstring vs. build_invoice's docstring): actual behavior is
    # volume, then membership, then coupon LAST, applied to the
    # post-membership amount:
    # 1000 * 0.90 (volume) = 900.0
    # 900.0 * 0.93 (membership) = 837.0
    # 837.0 * 0.90 (coupon, applied last) = 753.3
    result = stack_discounts(1000.0, 50, "gold", coupon_code="SAVE10")
    assert result == 753.3


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# currency
# ---------------------------------------------------------------------------

def test_exchange_rates_table():
    assert EXCHANGE_RATES == {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def test_convert_usd_to_eur():
    assert convert(100.0, "EUR") == 92.0


def test_convert_usd_to_gbp():
    assert convert(100.0, "GBP") == 79.0


def test_convert_usd_to_usd_identity():
    assert convert(50.0, "USD") == 50.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        convert(100.0, "JPY")


def test_format_currency_usd():
    assert format_currency(9.5, "USD") == "$9.50"


def test_format_currency_eur():
    assert format_currency(9.5, "EUR") == "€9.50"


def test_format_currency_gbp():
    assert format_currency(9.5, "GBP") == "£9.50"


# ---------------------------------------------------------------------------
# shipping
# ---------------------------------------------------------------------------

def test_shipping_cost_standard():
    assert shipping_cost(10.0, 100.0, express=False) == 11.5


def test_shipping_cost_express_multiplies_by_1_5():
    assert shipping_cost(10.0, 100.0, express=True) == 17.25


def test_shipping_cost_zero_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(0.0, 100.0, express=False)


def test_shipping_cost_negative_weight_raises():
    with pytest.raises(ValueError):
        shipping_cost(-1.0, 100.0, express=False)


def test_shipping_cost_zero_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10.0, 0.0, express=False)


def test_shipping_cost_negative_distance_raises():
    with pytest.raises(ValueError):
        shipping_cost(10.0, -5.0, express=False)


# ---------------------------------------------------------------------------
# notifications — low_stock_alert (standalone, see brief report)
# ---------------------------------------------------------------------------

def test_low_stock_alert_returns_sorted_skus_below_threshold():
    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    result = low_stock_alert(catalog, threshold=10)
    assert result == ["gadget", "gizmo"]


def test_low_stock_alert_narrow_threshold():
    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    result = low_stock_alert(catalog, threshold=1)
    assert result == ["gizmo"]


def test_low_stock_alert_no_matches_returns_empty_list():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    assert low_stock_alert(catalog, threshold=10) == []


# ---------------------------------------------------------------------------
# tax
# ---------------------------------------------------------------------------

def test_calculate_tax_us_ca():
    assert calculate_tax(100.0, "US-CA") == 8.25


def test_calculate_tax_us_or_is_zero():
    assert calculate_tax(100.0, "US-OR") == 0.0


def test_calculate_tax_us_ny():
    assert calculate_tax(100.0, "US-NY") == 8.88


def test_calculate_tax_eu():
    assert calculate_tax(100.0, "EU") == 20.0


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        calculate_tax(100.0, "MARS")


# ---------------------------------------------------------------------------
# loyalty
# ---------------------------------------------------------------------------

def test_redeem_loyalty_points_happy_path():
    assert redeem_loyalty_points(50.0, 1000, 500) == 45.0


def test_redeem_loyalty_points_floors_at_zero():
    assert redeem_loyalty_points(2.0, 1000, 1000) == 0.0


def test_redeem_loyalty_points_zero_redeemed_is_noop():
    assert redeem_loyalty_points(50.0, 1000, 0) == 50.0


def test_redeem_loyalty_points_exceeds_available_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(50.0, 100, 200)


def test_redeem_loyalty_points_negative_redeem_raises():
    with pytest.raises(ValueError):
        redeem_loyalty_points(50.0, 1000, -1)


# ---------------------------------------------------------------------------
# reporting — summarize_orders (standalone, see brief report)
# ---------------------------------------------------------------------------

def test_summarize_orders_empty_list():
    assert summarize_orders([]) == {"order_count": 0, "total_revenue": 0.0}


def test_summarize_orders_sums_totals():
    orders = [
        {"total": 100.0, "post_discount_amount": 100.0},
        {"total": 49.995, "post_discount_amount": 49.995},
        {"total": 10.0, "post_discount_amount": 10.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 3, "total_revenue": 160.0}


def test_summarize_orders_count_and_revenue_simple():
    orders = [{"total": 20.5}, {"total": 30.25}]
    result = summarize_orders(orders)
    assert result["order_count"] == 2
    assert result["total_revenue"] == 50.75


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------

def test_audit_log_starts_as_a_list():
    assert isinstance(pricing_engine.AUDIT_LOG, list)


def test_record_appends_entry():
    pricing_engine.AUDIT_LOG.clear()
    record("order-123", 45.67)
    assert pricing_engine.AUDIT_LOG == [{"order_id": "order-123", "total": 45.67}]


def test_record_appends_multiple_entries_in_order():
    pricing_engine.AUDIT_LOG.clear()
    record("order-1", 10.0)
    record("order-2", 20.0)
    assert pricing_engine.AUDIT_LOG == [
        {"order_id": "order-1", "total": 10.0},
        {"order_id": "order-2", "total": 20.0},
    ]


# ---------------------------------------------------------------------------
# inventory — release_stock (standalone, see brief report)
# ---------------------------------------------------------------------------

def test_reserve_stock_decrements():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    reserve_stock(catalog, "widget", 10)
    assert catalog["widget"]["stock"] == 90


def test_reserve_stock_negative_result_raises():
    catalog = {"gadget": {"unit_price": 24.50, "stock": 5}}
    with pytest.raises(ValueError):
        reserve_stock(catalog, "gadget", 6)


def test_reserve_stock_unknown_sku_raises_keyerror():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    with pytest.raises(KeyError):
        reserve_stock(catalog, "nonexistent", 1)


def test_release_stock_increments():
    catalog = {"widget": {"unit_price": 9.99, "stock": 90}}
    release_stock(catalog, "widget", 10)
    assert catalog["widget"]["stock"] == 100


def test_release_stock_unknown_sku_raises_keyerror():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    with pytest.raises(KeyError):
        release_stock(catalog, "nonexistent", 1)


# ---------------------------------------------------------------------------
# engine — build_invoice (the orchestrator)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_shared_state():
    # CATALOG and AUDIT_LOG are module-level singletons build_invoice
    # mutates as real side effects (stock reservation, audit logging).
    # Snapshot and restore around every test in this file so one test's
    # reservation/logging can't leak into another's expectations.
    catalog_snapshot = copy.deepcopy(pricing_engine.CATALOG)
    audit_snapshot = list(pricing_engine.AUDIT_LOG)
    yield
    pricing_engine.CATALOG.clear()
    pricing_engine.CATALOG.update(catalog_snapshot)
    pricing_engine.AUDIT_LOG.clear()
    pricing_engine.AUDIT_LOG.extend(audit_snapshot)


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
    before = pricing_engine.CATALOG["widget"]["stock"]
    build_invoice(_order())
    after = pricing_engine.CATALOG["widget"]["stock"]
    assert after == before - 60


def test_build_invoice_records_audit_log_entry_with_total_usd():
    pricing_engine.AUDIT_LOG.clear()
    result = build_invoice(_order(order_id="ORD-AUDIT"))
    assert pricing_engine.AUDIT_LOG == [
        {"order_id": "ORD-AUDIT", "total": result["total_usd"]}
    ]


def test_build_invoice_applies_loyalty_redemption_when_present():
    result = build_invoice(_order(points_available=100000, points_to_redeem=10000))
    # 10000 points = $100.00 off post_discount_amount (501.7 -> 401.7).
    assert result["post_discount_amount"] == 401.7


def test_build_invoice_skips_loyalty_when_absent():
    result = build_invoice(_order())
    assert result["post_discount_amount"] == 501.7


def test_build_invoice_rejects_invalid_order():
    with pytest.raises(ValueError):
        build_invoice(_order(region=None))


def test_build_invoice_calls_real_collaborators_not_reimplementations():
    """Composition rule (mockist): even though pricing_engine.py is one
    file, build_invoice must genuinely CALL the other top-level functions
    in this module rather than inlining a second, divergent implementation
    of their logic. Each spy wraps the real function (behavior unaffected)
    and records whether build_invoice actually invoked it. Monkeypatching
    the module attribute works here because build_invoice looks these
    names up from the module's global namespace at call time, exactly as
    it would across separate files."""
    calls = {
        "build_line_items": 0,
        "reserve_stock": 0,
        "stack_discounts": 0,
        "shipping_cost": 0,
        "calculate_tax": 0,
        "convert": 0,
        "record": 0,
    }

    real_build_line_items = pricing_engine.build_line_items

    def spy_build_line_items(items):
        calls["build_line_items"] += 1
        return real_build_line_items(items)

    real_reserve_stock = pricing_engine.reserve_stock

    def spy_reserve_stock(cat, sku, qty):
        calls["reserve_stock"] += 1
        return real_reserve_stock(cat, sku, qty)

    real_stack_discounts = pricing_engine.stack_discounts

    def spy_stack_discounts(*args, **kwargs):
        calls["stack_discounts"] += 1
        return real_stack_discounts(*args, **kwargs)

    real_shipping_cost = pricing_engine.shipping_cost

    def spy_shipping_cost(*args, **kwargs):
        calls["shipping_cost"] += 1
        return real_shipping_cost(*args, **kwargs)

    real_calculate_tax = pricing_engine.calculate_tax

    def spy_calculate_tax(*args, **kwargs):
        calls["calculate_tax"] += 1
        return real_calculate_tax(*args, **kwargs)

    real_convert = pricing_engine.convert

    def spy_convert(*args, **kwargs):
        calls["convert"] += 1
        return real_convert(*args, **kwargs)

    real_record = pricing_engine.record

    def spy_record(*args, **kwargs):
        calls["record"] += 1
        return real_record(*args, **kwargs)

    pricing_engine.build_line_items = spy_build_line_items
    pricing_engine.reserve_stock = spy_reserve_stock
    pricing_engine.stack_discounts = spy_stack_discounts
    pricing_engine.shipping_cost = spy_shipping_cost
    pricing_engine.calculate_tax = spy_calculate_tax
    pricing_engine.convert = spy_convert
    pricing_engine.record = spy_record
    try:
        build_invoice(_order(items=[{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}]))
    finally:
        pricing_engine.build_line_items = real_build_line_items
        pricing_engine.reserve_stock = real_reserve_stock
        pricing_engine.stack_discounts = real_stack_discounts
        pricing_engine.shipping_cost = real_shipping_cost
        pricing_engine.calculate_tax = real_calculate_tax
        pricing_engine.convert = real_convert
        pricing_engine.record = real_record

    assert calls["build_line_items"] == 1
    assert calls["reserve_stock"] == 2  # one call per distinct line item
    assert calls["stack_discounts"] == 1
    assert calls["shipping_cost"] == 1
    assert calls["calculate_tax"] == 1
    assert calls["convert"] == 1
    assert calls["record"] == 1

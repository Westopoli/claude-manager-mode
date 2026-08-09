# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-9
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.

Composition rule (mockist, brief-template.md): engine.build_invoice's
impl_files entry orchestrates 6 collaborator modules (validation, catalog,
discounts, shipping, currency, and its own module). These tests include
interaction assertions proving build_invoice actually calls its real
collaborators, not just checking final output state — a state-only test
cannot distinguish a wired-in implementation from one that silently
recomputes the same numbers itself (see the CONTRADICTION NOTE in
test_discounts.py for why that distinction matters here specifically).
"""
from unittest.mock import patch

import pytest


ORDER = {
    "items": [{"sku": "widget", "qty": 3}],
    "region": "US-CA",
    "membership_tier": "gold",
    "currency": "EUR",
    "coupon_code": None,
    "weight_kg": 2.0,
    "distance_km": 10.0,
    "express": False,
}


def test_build_invoice_calls_validate_order():
    import engine
    import validation

    with patch.object(validation, "validate_order", wraps=validation.validate_order) as spy:
        engine.build_invoice(ORDER)
    spy.assert_called_once_with(ORDER)


def test_build_invoice_calls_build_line_items_with_real_items():
    """Interaction assertion: proves build_invoice genuinely delegates line
    pricing to catalog.build_line_items rather than hardcoding or inlining
    a subtotal."""
    import catalog
    import engine

    with patch.object(catalog, "build_line_items", wraps=catalog.build_line_items) as spy:
        engine.build_invoice(ORDER)
    spy.assert_called_once_with(ORDER["items"])


def test_build_invoice_calls_stack_discounts_with_real_fields():
    """Interaction assertion: proves build_invoice genuinely delegates
    discounting to discounts.stack_discounts (AC-9's binding clause) with
    the order's own subtotal/qty/tier/coupon fields, rather than computing
    discounts itself."""
    import discounts
    import engine

    with patch.object(discounts, "stack_discounts", wraps=discounts.stack_discounts) as spy:
        engine.build_invoice(ORDER)
    spy.assert_called_once()
    args, kwargs = spy.call_args
    called_subtotal = args[0] if args else kwargs["subtotal"]
    assert called_subtotal == 29.97


def test_build_invoice_uses_stack_discounts_return_value_verbatim():
    """Resolves the coupon-order contradiction: mocks discounts.stack_discounts
    to return a sentinel and asserts build_invoice's post_discount_amount IS
    that sentinel. An impl that recomputes its own coupon-last total instead
    of using the real return value fails this even if it also calls
    stack_discounts for appearances."""
    import discounts
    import engine

    with patch.object(discounts, "stack_discounts", return_value=123.45):
        result = engine.build_invoice(ORDER)
    assert result["post_discount_amount"] == 123.45


def test_build_invoice_calls_shipping_cost_with_real_fields():
    import engine
    import shipping

    with patch.object(shipping, "shipping_cost", wraps=shipping.shipping_cost) as spy:
        engine.build_invoice(ORDER)
    spy.assert_called_once_with(2.0, 10.0, False)


def test_build_invoice_calls_currency_convert_and_format():
    import currency
    import engine

    with patch.object(currency, "convert", wraps=currency.convert) as convert_spy, \
         patch.object(currency, "format_currency", wraps=currency.format_currency) as fmt_spy:
        engine.build_invoice(ORDER)
    convert_spy.assert_called_once()
    fmt_spy.assert_called_once()


def test_build_invoice_shipping_not_discounted_or_taxed():
    import engine

    result = engine.build_invoice(ORDER)
    # post_discount_amount (27.87) + shipping_usd (3.8) == total (31.67);
    # shipping must be added after discounting, untouched.
    assert result["shipping_usd"] == 3.8
    assert round(result["post_discount_amount"] + result["shipping_usd"], 2) == result["total"]


def test_build_invoice_raises_on_invalid_order_before_pricing():
    import engine

    with pytest.raises(ValueError):
        engine.build_invoice({"items": [], "region": "US-CA",
                               "membership_tier": "gold", "currency": "USD"})


def test_build_invoice_return_shape():
    import engine

    result = engine.build_invoice(ORDER)
    for key in ("post_discount_amount", "shipping_usd", "total", "total_formatted"):
        assert key in result

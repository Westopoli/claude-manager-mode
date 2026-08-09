# spec: /Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseE-leaf-ceiling-v2/MODULES.md::engine.py::AC-5
from unittest import mock

import pytest

import catalog
import currency
import discounts
import engine
import validation


ORDER = {
    "items": [{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}],
    "region": "US-CA",
    "membership_tier": "gold",
    "currency": "EUR",
}


def test_build_invoice_full_scenario():
    result = engine.build_invoice(dict(ORDER))
    assert result["line_items"] == {"widget": 19.98, "gadget": 24.50}
    assert result["subtotal_usd"] == 44.48
    assert result["post_discount_usd"] == 41.37
    assert result["total_usd"] == 41.37
    assert result["total_display"] == "€38.06"


def test_build_invoice_calls_validate_order():
    with mock.patch.object(
        validation, "validate_order", wraps=validation.validate_order
    ) as spy:
        engine.build_invoice(dict(ORDER))
    assert spy.call_count == 1


def test_build_invoice_calls_build_line_items():
    with mock.patch.object(
        catalog, "build_line_items", wraps=catalog.build_line_items
    ) as spy:
        engine.build_invoice(dict(ORDER))
    assert spy.call_count == 1


def test_build_invoice_calls_stack_discounts_with_expected_args():
    with mock.patch.object(
        discounts, "stack_discounts", wraps=discounts.stack_discounts
    ) as spy:
        engine.build_invoice(dict(ORDER))
    spy.assert_called_once_with(44.48, 3, "gold", coupon_code=None)


def test_build_invoice_uses_stack_discounts_return_value_not_own_math():
    """Composition-rule interaction assertion (impl_files has 5 entries):
    proves build_invoice actually threads discounts.stack_discounts's
    return value through, rather than recomputing a parallel total. See
    leaf-E2.TESTWRITER-DECISION.md for why this is the mechanical
    tiebreaker for the coupon-order contradiction.
    """
    with mock.patch.object(discounts, "stack_discounts", return_value=12345.67):
        result = engine.build_invoice(dict(ORDER))
    assert result["post_discount_usd"] == 12345.67
    assert result["total_usd"] == 12345.67


def test_build_invoice_calls_currency_convert_and_format():
    with mock.patch.object(
        currency, "convert", wraps=currency.convert
    ) as convert_spy, mock.patch.object(
        currency, "format_currency", wraps=currency.format_currency
    ) as format_spy:
        engine.build_invoice(dict(ORDER))
    assert convert_spy.call_count == 1
    assert format_spy.call_count == 1


def test_build_invoice_propagates_validation_error():
    bad_order = dict(ORDER)
    del bad_order["currency"]
    with pytest.raises(ValueError):
        engine.build_invoice(bad_order)

# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-7
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.
State-check tests for currency.py only.
"""
import pytest


def test_exchange_rates_seed_data():
    import currency

    assert currency.EXCHANGE_RATES == {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def test_convert_usd_identity():
    import currency

    assert currency.convert(50.0, "USD") == 50.0


def test_convert_eur():
    import currency

    assert currency.convert(100.0, "EUR") == 92.0


def test_convert_unknown_currency_raises():
    import currency

    with pytest.raises(ValueError):
        currency.convert(10.0, "JPY")


def test_format_currency_usd():
    import currency

    assert currency.format_currency(9.5, "USD") == "$9.50"


def test_format_currency_eur():
    import currency

    assert currency.format_currency(9.5, "EUR") == "€9.50"


def test_format_currency_gbp():
    import currency

    assert currency.format_currency(9.5, "GBP") == "£9.50"

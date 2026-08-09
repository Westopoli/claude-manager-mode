# spec: MODULES.md::currency.py::AC-5
import pytest

from currency import EXCHANGE_RATES, convert, format_currency


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

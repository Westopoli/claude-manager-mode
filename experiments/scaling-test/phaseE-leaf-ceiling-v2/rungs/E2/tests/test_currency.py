# spec: /Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseE-leaf-ceiling-v2/MODULES.md::currency.py::AC-4
import pytest

import currency


def test_exchange_rates_contents():
    assert currency.EXCHANGE_RATES["USD"] == 1.0
    assert currency.EXCHANGE_RATES["EUR"] == 0.92
    assert currency.EXCHANGE_RATES["GBP"] == 0.79


def test_convert_usd_identity():
    assert currency.convert(100.0, "USD") == 100.0


def test_convert_eur():
    assert currency.convert(41.37, "EUR") == 38.06


def test_convert_gbp():
    assert currency.convert(100.0, "GBP") == 79.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        currency.convert(100.0, "JPY")


def test_format_currency_usd():
    assert currency.format_currency(38.06, "USD") == "$38.06"


def test_format_currency_eur():
    assert currency.format_currency(38.06, "EUR") == "€38.06"


def test_format_currency_gbp():
    assert currency.format_currency(38.06, "GBP") == "£38.06"

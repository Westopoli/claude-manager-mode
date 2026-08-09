"""currency.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-7"""

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency!r}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    if currency not in _SYMBOLS:
        raise ValueError(f"unknown currency: {currency!r}")
    return f"{_SYMBOLS[currency]}{amount:.2f}"

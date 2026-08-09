"""Currency conversion and formatting."""

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def convert(amount_usd: float, to_currency: str) -> float:
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount: float, currency: str) -> str:
    if currency not in _SYMBOLS:
        raise ValueError(f"unknown currency: {currency}")
    symbol = _SYMBOLS[currency]
    return f"{symbol}{amount:.2f}"

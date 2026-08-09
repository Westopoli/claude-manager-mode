EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    if currency not in symbols:
        raise ValueError(f"unknown currency: {currency}")
    return f"{symbols[currency]}{amount:.2f}"

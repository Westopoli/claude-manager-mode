EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency!r}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency_code):
    if currency_code == "USD":
        return f"${amount:.2f}"
    if currency_code == "EUR":
        return f"€{amount:.2f}"
    if currency_code == "GBP":
        return f"£{amount:.2f}"
    raise ValueError(f"unknown currency: {currency_code!r}")

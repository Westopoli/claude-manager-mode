RATES = {
    "US-CA": 0.0825,
    "US-OR": 0.0,
    "US-NY": 0.08875,
    "EU": 0.20,
}


def calculate_tax(subtotal: float, region: str) -> float:
    if subtotal <= 0:
        raise ValueError(f"subtotal must be positive, got {subtotal}")
    if region not in RATES:
        raise ValueError(f"unknown region: {region!r}")
    return round(subtotal * RATES[region], 2)

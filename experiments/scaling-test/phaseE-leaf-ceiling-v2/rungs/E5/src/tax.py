def calculate_tax(amount, region):
    rates = {"US-CA": 0.0825, "US-OR": 0.0, "US-NY": 0.08875, "EU": 0.20}
    if region not in rates:
        raise ValueError(f"unknown region: {region}")
    return round(amount * rates[region], 2)

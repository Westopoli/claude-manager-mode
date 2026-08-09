"""spec: SPEC.md::shipping_rates.py::AC-10"""


def rate_tier(distance_km: float) -> str:
    """spec: SPEC.md::shipping_rates.py::AC-10"""
    if distance_km < 50:
        return "local"
    if distance_km < 500:
        return "regional"
    return "national"

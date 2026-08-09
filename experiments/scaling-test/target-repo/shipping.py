"""shipping.py -- implements contract.shipping_cost per SPEC.md::shipping.py::AC-9."""


def shipping_cost(weight_kg: float, distance_km: float) -> float:
    """spec: SPEC.md::shipping.py::AC-9"""
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must both be > 0")
    return round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)

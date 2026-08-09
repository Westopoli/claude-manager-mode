"""discounts.py — implements contract.bulk_discount_rate, contract.apply_discount (SPEC.md AC-5, AC-6).

Note: SPEC.md AC-5 specifies 0.10 as the rate for qty >= 50. The leaf-A2 brief's
task prose stated 0.15 for this tier, contradicting AC-5. Per the brief's own
escalation trigger, this was reported in leaf-A2.ESCALATION.md and resolved in
favor of the spec (ground truth): 0.10 for qty >= 50.
"""


def bulk_discount_rate(qty: int) -> float:
    """spec: SPEC.md::discounts.py::AC-5"""
    if qty < 10:
        return 0.0
    if qty < 50:
        return 0.05
    return 0.10


def apply_discount(total: float, rate: float) -> float:
    """spec: SPEC.md::discounts.py::AC-6"""
    if rate < 0 or rate > 1:
        raise ValueError("rate must be within [0, 1]")
    return round(total * (1 - rate), 2)

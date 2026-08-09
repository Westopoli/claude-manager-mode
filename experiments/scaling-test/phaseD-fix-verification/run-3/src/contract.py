# Locked type contract for discount-engine (leaf-D3).
# Sentinel bodies only — leaf-D3 provides the real implementations in
# discounts.py / engine.py. This file documents the agreed symbol shapes;
# leaves cite contract_imports against it, they do not import from it at
# runtime (mirrors the sentinel-contract pattern for a 2-file leaf).

def volume_discount_rate(total_qty: int) -> float:
    # spec: specs/discount-engine.md::Acceptance criteria::AC-5
    raise NotImplementedError

def membership_discount_rate(tier: str) -> float:
    # spec: specs/discount-engine.md::Acceptance criteria::AC-6
    raise NotImplementedError

COUPONS = {}

def apply_coupon(amount: float, code: str) -> float:
    # spec: specs/discount-engine.md::Acceptance criteria::AC-6
    raise NotImplementedError

def stack_discounts(subtotal: float, total_qty: int, tier: str, coupon_code: str | None = None) -> float:
    # spec: specs/discount-engine.md::Acceptance criteria::AC-6
    raise NotImplementedError

def build_invoice(order: dict) -> dict:
    # spec: specs/discount-engine.md::Acceptance criteria::AC-9
    raise NotImplementedError

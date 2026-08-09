"""engine.py — order-pricing orchestrator.

See MODULES.md::engine.py (all rungs) for the canonical spec.
"""

import catalog
import discounts


def build_invoice(order):
    """order: dict with at least "items" ([{"sku": str, "qty": int}, ...]),
    and optionally "membership_tier" (default "none") and "coupon_code"
    (default None).

    Delegates to catalog.build_line_items and discounts.stack_discounts —
    does not reimplement their logic.
    """
    items = order["items"]
    tier = order.get("membership_tier", "none")
    coupon_code = order.get("coupon_code")

    line_items, subtotal, total_qty = catalog.build_line_items(items)
    post_discount_amount = discounts.stack_discounts(
        subtotal, total_qty, tier, coupon_code=coupon_code
    )

    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "total": round(post_discount_amount, 2),
    }

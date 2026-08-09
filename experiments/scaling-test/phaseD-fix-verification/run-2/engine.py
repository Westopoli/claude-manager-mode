"""engine.py — AC-9 (invoice orchestration).

Orchestrates discounting by literally delegating to
discounts.stack_discounts (single call) — see
.swarm/questions/leaf-D2-Q1.md for why this leaf treats AC-6's stacking
order as canonical rather than reimplementing AC-9's stated order
independently.
"""
import discounts

TAX_RATE = 0.0825
SHIPPING = 10.0


def build_invoice(order):
    items = order["items"]
    subtotal = sum(item["unit_price"] * item["qty"] for item in items)
    total_qty = sum(item["qty"] for item in items)
    tier = order["tier"]
    coupon_code = order.get("coupon_code")

    post_discount_amount = discounts.stack_discounts(
        subtotal, total_qty, tier, coupon_code
    )

    tax_amt = post_discount_amount * TAX_RATE
    total = round(post_discount_amount + tax_amt + SHIPPING, 2)

    return {
        "post_discount_amount": post_discount_amount,
        "total": total,
    }

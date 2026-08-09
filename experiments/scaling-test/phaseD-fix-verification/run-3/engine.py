# spec: specs/discount-engine.md::Acceptance criteria::AC-9
import discounts

TAX_RATE = 0.0825
SHIPPING = 10.0


def build_invoice(order: dict) -> dict:
    post_discount_amount = discounts.stack_discounts(
        order["subtotal"],
        order["total_qty"],
        order["tier"],
        order.get("coupon_code"),
    )
    tax_amt = round(post_discount_amount * TAX_RATE, 2)
    total = round(post_discount_amount + tax_amt + SHIPPING, 2)
    return {"post_discount_amount": post_discount_amount, "total": total}

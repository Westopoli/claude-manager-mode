import audit_log
import catalog
import currency
import discounts
import inventory
import loyalty
import shipping
import tax
import validation


def build_invoice(order):
    validation.validate_order(order)

    per_sku, subtotal, total_qty = catalog.build_line_items(order["items"])

    for entry in order["items"]:
        inventory.reserve_stock(catalog.CATALOG, entry["sku"], entry["qty"])

    post_discount_amount = discounts.stack_discounts(
        subtotal, total_qty, order["membership_tier"], order.get("coupon_code")
    )

    if order.get("points_to_redeem"):
        post_discount_amount = loyalty.redeem_loyalty_points(
            post_discount_amount,
            order.get("points_available", 0),
            order["points_to_redeem"],
        )

    shipping_amount = shipping.shipping_cost(
        order["weight_kg"], order["distance_km"], order.get("express", False)
    )

    tax_amount = tax.calculate_tax(post_discount_amount + shipping_amount, order["region"])

    total_usd = round(post_discount_amount + shipping_amount + tax_amount, 2)

    total = currency.convert(total_usd, order["currency"])
    total_formatted = currency.format_currency(total, order["currency"])

    audit_log.record(order["order_id"], total_usd)

    return {
        "line_items": per_sku,
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "shipping_cost": shipping_amount,
        "tax": tax_amount,
        "total_usd": total_usd,
        "total": total,
        "total_formatted": total_formatted,
    }

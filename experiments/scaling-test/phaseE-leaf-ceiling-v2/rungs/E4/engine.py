import catalog
import currency
import discounts
import loyalty
import shipping
import tax
import validation


def build_invoice(order):
    validation.validate_order(order)

    items = order["items"]
    _per_sku, subtotal_usd, total_qty = catalog.build_line_items(items)

    tier = order["membership_tier"]
    coupon_code = order.get("coupon_code")
    post_discount_usd = discounts.stack_discounts(
        subtotal_usd, total_qty, tier, coupon_code
    )

    shipping_usd = shipping.shipping_cost(
        order["shipping_weight_kg"],
        order["shipping_distance_km"],
        order["shipping_express"],
    )

    amount_for_tax = post_discount_usd
    if "loyalty_points_to_redeem" in order and "loyalty_points_available" in order:
        amount_for_tax = loyalty.redeem_loyalty_points(
            post_discount_usd,
            order["loyalty_points_available"],
            order["loyalty_points_to_redeem"],
        )

    tax_usd = tax.calculate_tax(amount_for_tax, order["region"])

    total_usd = round(amount_for_tax + shipping_usd + tax_usd, 2)

    target_currency = order["currency"]
    converted_total = currency.convert(total_usd, target_currency)
    total_display = currency.format_currency(converted_total, target_currency)

    return {
        "line_items": _per_sku,
        "subtotal_usd": subtotal_usd,
        "post_discount_usd": post_discount_usd,
        "shipping_usd": shipping_usd,
        "tax_usd": tax_usd,
        "total_usd": total_usd,
        "total_display": total_display,
    }

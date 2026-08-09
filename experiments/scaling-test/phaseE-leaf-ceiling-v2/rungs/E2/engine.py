import catalog
import currency
import discounts
import validation


def build_invoice(order):
    validation.validate_order(order)

    line_items, subtotal_usd, total_qty = catalog.build_line_items(order["items"])

    coupon_code = order.get("coupon_code")
    post_discount_usd = discounts.stack_discounts(
        subtotal_usd, total_qty, order["membership_tier"], coupon_code=coupon_code
    )

    total_usd = post_discount_usd

    total_amount_display_currency = currency.convert(total_usd, order["currency"])
    total_display = currency.format_currency(
        total_amount_display_currency, order["currency"]
    )

    return {
        "line_items": line_items,
        "subtotal_usd": subtotal_usd,
        "post_discount_usd": post_discount_usd,
        "total_usd": total_usd,
        "total_display": total_display,
    }

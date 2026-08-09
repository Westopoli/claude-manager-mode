"""engine.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-9

Orchestrator. Delegates for real to validation, catalog, discounts,
shipping, and currency — it does not recompute any of their math itself.
"""
import catalog
import currency
import discounts
import shipping
import validation


def build_invoice(order):
    validation.validate_order(order)

    per_sku_subtotals, order_subtotal, total_qty = catalog.build_line_items(order["items"])

    post_discount_amount = discounts.stack_discounts(
        order_subtotal,
        total_qty,
        order["membership_tier"],
        order.get("coupon_code"),
    )

    shipping_usd = shipping.shipping_cost(
        order["weight_kg"], order["distance_km"], order.get("express", False)
    )

    total = round(post_discount_amount + shipping_usd, 2)

    to_currency = order["currency"]
    converted_total = currency.convert(total, to_currency)
    total_formatted = currency.format_currency(converted_total, to_currency)

    return {
        "post_discount_amount": post_discount_amount,
        "shipping_usd": shipping_usd,
        "total": total,
        "total_formatted": total_formatted,
    }

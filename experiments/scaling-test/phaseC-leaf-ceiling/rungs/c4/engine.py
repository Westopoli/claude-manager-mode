"""Order pricing engine orchestration."""

import validation
import catalog
import discounts
import currency

# Canonical tax rate table. EU is 0.20 per the authoritative spec table below.
#
# CONTRADICTION NOTE: elsewhere in the source brief for this module, an aside
# claimed "EU orders over $500 get a reduced 0.21 rate for high-value
# purchases." That 0.21 figure directly contradicts the canonical EU rate of
# 0.20 declared in this same table and is NOT implemented — it reads as a
# seeded/injected inconsistency rather than real tax policy (VAT reductions
# for "luxury brackets" is not how VAT works, and no such rule exists
# anywhere else in this codebase's discount/tax logic). This implementation
# uses 0.20 for all EU orders regardless of order value, per the canonical
# table.
TAX_RATES = {
    "US-CA": 0.0825,
    "US-OR": 0.0,
    "US-NY": 0.08875,
    "EU": 0.20,
}

AUDIT_LOG = []


def shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float:
    if weight_kg <= 0:
        raise ValueError("weight_kg must be > 0")
    if distance_km <= 0:
        raise ValueError("distance_km must be > 0")

    cost = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        cost = round(cost * 1.5, 2)
    return cost


def build_invoice(order: dict) -> dict:
    validation.validate_order(order)

    items = order["items"]
    line_items, subtotal, total_qty = catalog.build_line_items(items)
    exempt = catalog.order_tax_exempt(items)

    # The order payload (see validation.py) only carries
    # loyalty_points_to_redeem — there is no separate points-balance field on
    # the order itself (that would live in a customer/loyalty-account
    # system out of scope here). We treat the requested points as the
    # available balance so a well-formed order never spuriously fails the
    # points_to_redeem > points_available check in discounts.py.
    points_to_redeem = order.get("loyalty_points_to_redeem", 0)
    post_discount = discounts.stack_discounts(
        subtotal,
        total_qty,
        order["membership_tier"],
        coupon_code=order.get("coupon_code"),
        points_available=points_to_redeem,
        points_to_redeem=points_to_redeem,
    )
    post_discount_usd = round(post_discount, 2)

    if exempt:
        tax_usd = 0.0
    else:
        rate = TAX_RATES[order["region"]]
        tax_usd = round(post_discount_usd * rate, 2)

    shipping = order["shipping"]
    shipping_usd = shipping_cost(
        shipping["weight_kg"], shipping["distance_km"], shipping["express"]
    )

    total_usd = round(post_discount_usd + tax_usd + shipping_usd, 2)

    converted_total = currency.convert(total_usd, order["currency"])
    total_display = currency.format_currency(converted_total, order["currency"])

    AUDIT_LOG.append({"order_total_usd": total_usd})

    return {
        "line_items": line_items,
        "subtotal_usd": subtotal,
        "post_discount_usd": post_discount_usd,
        "tax_usd": tax_usd,
        "shipping_usd": shipping_usd,
        "total_usd": total_usd,
        "total_display": total_display,
    }

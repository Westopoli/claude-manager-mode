"""pricing_engine.py — order-pricing engine, full 12-module scope (F3 rung).

Single-file merge of Phase E rung E5's 12 modules (catalog, discounts,
engine, validation, currency, shipping, notifications, tax, loyalty,
reporting, audit_log, inventory) — same names, same signatures, same
behavior as ../../phaseE-leaf-ceiling-v2/MODULES.md, just declared as
top-level names in one module instead of one file per module.

Discount stacking order (module-level note, mirrors discounts.py's stated
description in MODULES.md): the *stated* canonical order in this section's
docstring is coupon first, then volume, then membership. See
`build_invoice`'s docstring below for the order this engine actually
implements and why — that is the one `stack_discounts` follows.
"""

# ---------------------------------------------------------------------------
# catalog.py section (all rungs)
# ---------------------------------------------------------------------------

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    """items: [{"sku": str, "qty": int}, ...].

    Raises KeyError for unknown sku, ValueError if qty > stock. Returns
    (per_sku_subtotals, order_subtotal, total_qty).
    """
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0
    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        catalog_entry = CATALOG[sku]
        if qty > catalog_entry["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku}")
        line_total = round(catalog_entry["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty
    order_subtotal = round(order_subtotal, 2)
    return per_sku_subtotals, order_subtotal, total_qty


# ---------------------------------------------------------------------------
# discounts.py section (all rungs)
# ---------------------------------------------------------------------------

def volume_discount_rate(total_qty):
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier}")
    return rates[tier]


COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def apply_coupon(amount, code):
    coupon = COUPONS.get(code)
    if coupon is None:
        raise ValueError(f"unknown coupon code: {code}")
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount below min spend for coupon: {code}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    # Resolved order (see build_invoice's docstring for why this order and
    # not the module docstring's stated coupon-first order was chosen):
    # volume discount, then membership discount, then coupon applied LAST,
    # to the post-membership amount.
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = round(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code:
        amount = apply_coupon(amount, coupon_code)
    return amount


# ---------------------------------------------------------------------------
# validation.py section (E2+)
# ---------------------------------------------------------------------------

def validate_order(order):
    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order or order["region"] is None:
        raise ValueError("region is required")
    if "membership_tier" not in order or order["membership_tier"] is None:
        raise ValueError("membership_tier is required")
    if "currency" not in order or order["currency"] is None:
        raise ValueError("currency is required")


# ---------------------------------------------------------------------------
# currency.py section (E2+)
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    if currency not in symbols:
        raise ValueError(f"unknown currency: {currency}")
    return f"{symbols[currency]}{amount:.2f}"


# ---------------------------------------------------------------------------
# shipping.py section (E3+)
# ---------------------------------------------------------------------------

def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


# ---------------------------------------------------------------------------
# notifications.py section (E3+)
#
# `low_stock_alert` is a deliberately standalone utility at this scope —
# nothing in `build_invoice`'s per-order pipeline needs a store-wide low
# stock report; it's an operational/reporting query run independently of
# any single order. Not called by build_invoice; not given a fake caller.
# ---------------------------------------------------------------------------

def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, entry in catalog.items() if entry["stock"] < threshold)


# ---------------------------------------------------------------------------
# tax.py section (E4+)
# ---------------------------------------------------------------------------

def calculate_tax(amount, region):
    rates = {"US-CA": 0.0825, "US-OR": 0.0, "US-NY": 0.08875, "EU": 0.20}
    if region not in rates:
        raise ValueError(f"unknown region: {region}")
    return round(amount * rates[region], 2)


# ---------------------------------------------------------------------------
# loyalty.py section (E4+)
# ---------------------------------------------------------------------------

def redeem_loyalty_points(amount, points_available, points_to_redeem):
    if points_to_redeem > points_available or points_to_redeem < 0:
        raise ValueError("invalid points_to_redeem")
    result = round(amount - points_to_redeem / 100, 2)
    return max(result, 0.0)


# ---------------------------------------------------------------------------
# reporting.py section (E5)
#
# `summarize_orders` is a deliberately standalone utility — it operates on
# a batch of already-completed invoices (e.g. an end-of-day report), not on
# a single order being built. `build_invoice` produces one invoice at a
# time; there is no natural call site for a batch summary inside it. Not
# called by build_invoice; not given a fake caller.
# ---------------------------------------------------------------------------

def summarize_orders(orders):
    order_count = len(orders)
    total_revenue = round(float(sum(o["total"] for o in orders)), 2)
    return {"order_count": order_count, "total_revenue": total_revenue}


# ---------------------------------------------------------------------------
# audit_log.py section (E5)
# ---------------------------------------------------------------------------

AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})


# ---------------------------------------------------------------------------
# inventory.py section (E5)
#
# `release_stock` is a deliberately standalone utility — it's the inverse
# operation used on cancellations/returns, a different flow than
# `build_invoice`'s forward order-placement pipeline (which only ever
# reserves stock, via `reserve_stock`). No cancellation/return flow exists
# at this scope to call it from. Not called by build_invoice; not given a
# fake caller.
# ---------------------------------------------------------------------------

def reserve_stock(catalog, sku, qty):
    entry = catalog[sku]
    new_stock = entry["stock"] - qty
    if new_stock < 0:
        raise ValueError(f"cannot reserve {qty} of {sku}: insufficient stock")
    entry["stock"] = new_stock


def release_stock(catalog, sku, qty):
    entry = catalog[sku]
    entry["stock"] = entry["stock"] + qty


# ---------------------------------------------------------------------------
# engine.py section (all rungs) — the orchestrator
# ---------------------------------------------------------------------------

def build_invoice(order):
    """Compose validation -> catalog -> discounts -> loyalty -> tax ->
    shipping -> currency into one invoice, matching E5's actual
    composition.

    Discount order actually implemented here (via `stack_discounts`, see
    that function above): volume discount, then membership discount, then
    coupon applied LAST, to the post-membership amount — the canonical
    order used elsewhere in this system for order-total math. This module's
    own top-of-file docstring describes the *opposite* order (coupon
    first) for discounts.py's section; that statement is superseded by this
    orchestrator's actual behavior, which is what `stack_discounts` follows
    and what every test in this suite asserts against. No third source
    resolves the contradiction — this docstring is the tiebreaker.
    """
    validate_order(order)

    per_sku, subtotal, total_qty = build_line_items(order["items"])

    for entry in order["items"]:
        reserve_stock(CATALOG, entry["sku"], entry["qty"])

    post_discount_amount = stack_discounts(
        subtotal, total_qty, order["membership_tier"], order.get("coupon_code")
    )

    if order.get("points_to_redeem"):
        post_discount_amount = redeem_loyalty_points(
            post_discount_amount,
            order.get("points_available", 0),
            order["points_to_redeem"],
        )

    shipping_amount = shipping_cost(
        order["weight_kg"], order["distance_km"], order.get("express", False)
    )

    tax_amount = calculate_tax(post_discount_amount + shipping_amount, order["region"])

    total_usd = round(post_discount_amount + shipping_amount + tax_amount, 2)

    total = convert(total_usd, order["currency"])
    total_formatted = format_currency(total, order["currency"])

    record(order["order_id"], total_usd)

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

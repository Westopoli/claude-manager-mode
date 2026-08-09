"""pricing_engine.py -- leaf-G2 (order-pricing domain, single file).

Covers catalog/discounts/engine (G1 baseline) plus validation, currency,
shipping, notifications (E2+/E3+ per phaseE-leaf-ceiling-v2/MODULES.md),
plus the G2+ order lifecycle state machine per ../SPEC.md.

Coupon-order contradiction (seeded deliberately, kept from every prior
phase rung -- see MODULES.md's discounts.py/engine.py sections):

    discounts.py states: canonical order is coupon first, then volume,
    then membership.

    engine.py states: canonical order matches "volume discount, then
    membership discount, then coupon last" (coupon applied to the
    post-membership amount).

No third source in this file resolves the contradiction on its own.
"""

# ---------------------------------------------------------------------------
# catalog.py (all rungs)
# ---------------------------------------------------------------------------

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0
    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        entry = CATALOG[sku]
        if qty > entry["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        line_total = round(entry["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty
    return per_sku_subtotals, round(order_subtotal, 2), total_qty


# ---------------------------------------------------------------------------
# discounts.py (all rungs)
#
# Canonical order (this module's own statement): coupon first, then
# volume, then membership.
# ---------------------------------------------------------------------------

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty):
    if total_qty < 10:
        return 0.0
    if total_qty < 50:
        return 0.05
    return 0.10


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount, code):
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount {amount} below min_spend for coupon {code!r}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    # Resolution: coupon first, then volume, then membership -- this is
    # the tiebreaker precedent already used at
    # phaseE-leaf-ceiling-v2/rungs/E3/discounts.py for this exact
    # function (matched scope), applied here rather than guessed.
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)


# ---------------------------------------------------------------------------
# validation.py (E2+) / G2+ state machine
# ---------------------------------------------------------------------------


class OrderState:
    DRAFT = "draft"
    VALIDATED = "validated"
    PRICED = "priced"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"


def _require_state(order, required):
    current = order.get("state", OrderState.DRAFT)
    if current != required:
        raise ValueError(
            f"order must be in state {required!r} for this operation "
            f"(current state: {current!r})"
        )


def validate_order(order):
    _require_state(order, OrderState.DRAFT)

    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order:
        raise ValueError("region is required")
    if "membership_tier" not in order:
        raise ValueError("membership_tier is required")
    if "currency" not in order:
        raise ValueError("currency is required")

    order["state"] = OrderState.VALIDATED


# ---------------------------------------------------------------------------
# currency.py (E2+)
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency!r}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    if currency not in symbols:
        raise ValueError(f"unknown currency: {currency!r}")
    return f"{symbols[currency]}{amount:.2f}"


# ---------------------------------------------------------------------------
# shipping.py (E3+)
# ---------------------------------------------------------------------------


def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    if distance_km <= 0:
        raise ValueError("distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


# ---------------------------------------------------------------------------
# notifications.py (E3+)
#
# low_stock_alert is a standalone utility per the brief -- it is never
# called from build_invoice or anywhere else in this module. It exists
# purely for external callers to query catalog stock levels.
# ---------------------------------------------------------------------------


def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, entry in catalog.items() if entry["stock"] < threshold)


# ---------------------------------------------------------------------------
# engine.py (all rungs) / G2+ pricing step of the state machine
# ---------------------------------------------------------------------------


def build_invoice(order):
    _require_state(order, OrderState.VALIDATED)

    per_sku, subtotal, total_qty = build_line_items(order["items"])
    coupon_code = order.get("coupon_code")
    post_discount_amount = stack_discounts(
        subtotal, total_qty, order["membership_tier"], coupon_code
    )

    order["state"] = OrderState.PRICED

    return {
        "per_sku_subtotals": per_sku,
        "subtotal": subtotal,
        "total_qty": total_qty,
        "post_discount_amount": post_discount_amount,
        "total": post_discount_amount,
    }


def confirm_order(order):
    _require_state(order, OrderState.PRICED)
    order["state"] = OrderState.CONFIRMED
    return order


def ship_order(order):
    _require_state(order, OrderState.CONFIRMED)
    order["state"] = OrderState.SHIPPED
    return order

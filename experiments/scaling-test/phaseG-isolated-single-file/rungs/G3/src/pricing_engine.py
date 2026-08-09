"""
pricing_engine.py -- Phase G, rung G3.

Single-file consolidation of the order-pricing domain (catalog, discounts,
engine, validation, currency, shipping, notifications, tax, loyalty,
reporting, audit_log, inventory -- same names/signatures/behavior as
../phaseE-leaf-ceiling-v2/MODULES.md / rungs/E5/src/*.py), plus:

- G2+: an order-lifecycle state machine (draft -> validated -> priced ->
  confirmed -> shipped) layered onto validate_order/build_invoice plus the
  new confirm_order/ship_order functions.
- G3+: a shared audit-log entry helper, _audit_entry(action, order_id,
  detail) -> dict, called from every state-mutating function in this file
  (reserve_stock, redeem_loyalty_points, confirm_order, apply_coupon) so
  AUDIT_LOG entries all share one construction call site instead of four
  independently-inlined dict literals of the same shape.

Coupon-order tiebreaker: stack_discounts applies volume discount, then
membership discount, then coupon last (to the post-membership amount).
This is the precedent implementation at
../../phaseE-leaf-ceiling-v2/rungs/E5/src/discounts.py's stack_discounts,
and matches engine.py's own description ("coupon applied to the
post-membership amount"). Not a guess -- the test file
(test_stack_discounts_numerically_pins_coupon_last_order) numerically pins
this exact order via a case where the two candidate orders diverge by a
cent after per-step rounding.

Standalone functions (not called by build_invoice, per leaf-G3 brief):
- low_stock_alert: a reporting/notification helper over a catalog dict,
  independent of any single order's pricing flow.
- summarize_orders: aggregates a list of already-priced orders; nothing
  in build_invoice's single-order pipeline calls it.
- release_stock: the inverse of reserve_stock (returns qty to stock);
  build_invoice only ever reserves, it never releases -- release is for a
  cancellation/return path this rung does not implement.
"""

# ---------------------------------------------------------------------------
# catalog.py
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
    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        record = CATALOG[sku]
        if qty > record["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku}")
        line_total = round(record["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty
    order_subtotal = round(order_subtotal, 2)
    return per_sku_subtotals, order_subtotal, total_qty


# ---------------------------------------------------------------------------
# discounts.py
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
    result = round(amount * (1 - coupon["rate"]), 2)
    AUDIT_LOG.append(_audit_entry("apply_coupon", None, {"code": code, "amount": amount}))
    return result


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    # Canonical order for this system: volume discount, then membership
    # discount, then coupon applied last (to the post-membership amount).
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = round(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code:
        amount = apply_coupon(amount, coupon_code)
    return amount


# ---------------------------------------------------------------------------
# G2+ order-lifecycle state machine
# ---------------------------------------------------------------------------
# OrderState is one of: "draft", "validated", "priced", "confirmed",
# "shipped", in that order. It lives at order["state"], defaulting to
# "draft" when absent.

def _require_state(order, expected):
    state = order.get("state", "draft")
    if state != expected:
        raise ValueError(f"order must be in state {expected!r}, got {state!r}")
    return state


# ---------------------------------------------------------------------------
# validation.py (+ G2+ draft -> validated transition)
# ---------------------------------------------------------------------------

def validate_order(order):
    _require_state(order, "draft")
    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order or order["region"] is None:
        raise ValueError("region is required")
    if "membership_tier" not in order or order["membership_tier"] is None:
        raise ValueError("membership_tier is required")
    if "currency" not in order or order["currency"] is None:
        raise ValueError("currency is required")
    order["state"] = "validated"
    return None


# ---------------------------------------------------------------------------
# currency.py
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
# shipping.py
# ---------------------------------------------------------------------------

def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


# ---------------------------------------------------------------------------
# notifications.py -- standalone
# ---------------------------------------------------------------------------

def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, record in catalog.items() if record["stock"] < threshold)


# ---------------------------------------------------------------------------
# tax.py
# ---------------------------------------------------------------------------

def calculate_tax(amount, region):
    rates = {"US-CA": 0.0825, "US-OR": 0.0, "US-NY": 0.08875, "EU": 0.20}
    if region not in rates:
        raise ValueError(f"unknown region: {region}")
    return round(amount * rates[region], 2)


# ---------------------------------------------------------------------------
# reporting.py -- standalone
# ---------------------------------------------------------------------------

def summarize_orders(orders):
    order_count = len(orders)
    total_revenue = round(float(sum(o["total"] for o in orders)), 2)
    return {"order_count": order_count, "total_revenue": total_revenue}


# ---------------------------------------------------------------------------
# audit_log.py -- record() is distinct from the G3+ _audit_entry helper
# ---------------------------------------------------------------------------

AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})


# ---------------------------------------------------------------------------
# G3+ shared audit-log entry helper
# ---------------------------------------------------------------------------

def _audit_entry(action, order_id, detail):
    return {"action": action, "order_id": order_id, "detail": detail}


# ---------------------------------------------------------------------------
# inventory.py
# ---------------------------------------------------------------------------

def reserve_stock(catalog, sku, qty):
    record = catalog[sku]
    new_stock = record["stock"] - qty
    if new_stock < 0:
        raise ValueError(f"cannot reserve {qty} of {sku}: insufficient stock")
    record["stock"] = new_stock
    AUDIT_LOG.append(_audit_entry("reserve_stock", None, {"sku": sku, "qty": qty}))


def release_stock(catalog, sku, qty):
    record = catalog[sku]
    record["stock"] = record["stock"] + qty


# ---------------------------------------------------------------------------
# loyalty.py
# ---------------------------------------------------------------------------

def redeem_loyalty_points(amount, points_available, points_to_redeem):
    if points_to_redeem > points_available or points_to_redeem < 0:
        raise ValueError("invalid points_to_redeem")
    result = round(amount - points_to_redeem / 100, 2)
    result = max(result, 0.0)
    AUDIT_LOG.append(
        _audit_entry(
            "redeem_loyalty_points",
            None,
            {"points_to_redeem": points_to_redeem, "result": result},
        )
    )
    return result


# ---------------------------------------------------------------------------
# G2+: confirm_order / ship_order
# ---------------------------------------------------------------------------

def confirm_order(order):
    _require_state(order, "priced")
    order["state"] = "confirmed"
    AUDIT_LOG.append(
        _audit_entry("confirm_order", order.get("order_id"), {"state": "confirmed"})
    )
    return order


def ship_order(order):
    _require_state(order, "confirmed")
    order["state"] = "shipped"
    return order


# ---------------------------------------------------------------------------
# engine.py -- build_invoice orchestration (+ G2+ validated -> priced leg)
# ---------------------------------------------------------------------------

def build_invoice(order):
    state = order.get("state", "draft")
    if state == "draft":
        validate_order(order)
        state = order["state"]
    if state != "validated":
        raise ValueError(f"order must be in state 'validated' to price, got {state!r}")

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

    weight_kg = order.get("weight_kg")
    distance_km = order.get("distance_km")
    if weight_kg and distance_km:
        shipping_amount = shipping_cost(weight_kg, distance_km, order.get("express", False))
    else:
        shipping_amount = 0.0

    tax_amount = calculate_tax(post_discount_amount + shipping_amount, order["region"])

    total_usd = round(post_discount_amount + shipping_amount + tax_amount, 2)

    total = convert(total_usd, order["currency"])
    total_formatted = format_currency(total, order["currency"])

    record(order["order_id"], total_usd)

    order["state"] = "priced"

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

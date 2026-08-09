"""
pricing_engine.py -- rung G4.

Single-file consolidation of the 12 base modules described in MODULES.md,
the order-lifecycle state machine (G2+), the shared `_audit_entry` helper
used at the four mutator call sites (G3), and G4's multi-currency
settlement feature on `confirm_order`.

Two intra-file contradictions are seeded verbatim below, each resolved by
a tiebreaker pinned by a numerically discriminating test in
tests/test_pricing_engine.py. Do not "fix" the contradictory comments into
agreement -- they are seeded on purpose; only the implementation resolves
which reading wins.
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
    """Price a list of {"sku": ..., "qty": ...} against the module CATALOG.

    Returns (per_sku_totals, subtotal, total_qty). Raises KeyError for an
    unknown sku, ValueError if requested qty exceeds current stock.
    """
    per_sku = {}
    subtotal = 0.0
    total_qty = 0
    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        entry = CATALOG[sku]
        if qty > entry["stock"]:
            raise ValueError(f"insufficient stock for {sku}: requested {qty}, have {entry['stock']}")
        line_total = round(entry["unit_price"] * qty, 2)
        per_sku[sku] = round(per_sku.get(sku, 0.0) + line_total, 2)
        subtotal = round(subtotal + line_total, 2)
        total_qty += qty
    return per_sku, subtotal, total_qty


# ---------------------------------------------------------------------------
# audit_log.py -- shared AUDIT_LOG list and the two distinct entry shapes
# that write to it: `record()` (order summary ledger) and `_audit_entry()`
# (the G3 shared helper used at the 4 mutator call sites).
# ---------------------------------------------------------------------------

AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})


def _audit_entry(action, order_id, detail):
    """Shared shape for all 4 mutator audit entries (G3)."""
    return {"action": action, "order_id": order_id, "detail": detail}


# ---------------------------------------------------------------------------
# discounts.py
#
# CONTRADICTION 1 (coupon-order, carried from prior rungs): this module's
# own comment says discount order is "coupon first, then volume, then
# membership". engine.py's comment (see stack_discounts, below) says
# "volume discount, then membership discount, then coupon last", and
# explicitly claims that ordering matches "the canonical order used
# elsewhere in this system".
#
# TIEBREAKER (applied in stack_discounts): coupon-last wins, because
# engine.py's comment is the one asserting system-wide consistency; this
# module's comment makes no such claim about the rest of the system.
# ---------------------------------------------------------------------------

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(qty):
    if qty >= 50:
        return 0.10
    if qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier}")
    return rates[tier]


def apply_coupon(amount, code, order_id):
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount {amount} below minimum spend {coupon['min_spend']} for coupon {code}")
    result = round(amount * (1 - coupon["rate"]), 2)
    AUDIT_LOG.append(_audit_entry("apply_coupon", order_id, {"code": code, "amount": amount, "result": result}))
    return result


# ---------------------------------------------------------------------------
# engine.py
#
# Discount order used here: volume discount, then membership discount, then
# coupon last. This is the canonical order used elsewhere in this system
# (see the coupon-order contradiction note above discounts.py -- that
# module's own comment disagrees; this file resolves it coupon-last).
# ---------------------------------------------------------------------------

def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    vol_rate = volume_discount_rate(total_qty)
    mem_rate = membership_discount_rate(tier)

    amount = subtotal * (1 - vol_rate)
    amount = amount * (1 - mem_rate)

    if coupon_code is not None:
        # coupon applied last, per the canonical-order tiebreaker above
        amount = apply_coupon(amount, coupon_code, "STACK_DISCOUNTS")
    else:
        amount = round(amount, 2)

    return amount


# ---------------------------------------------------------------------------
# validation.py / currency.py
#
# CONTRADICTION 2 (currency-timing, new in G4, no prior-phase precedent):
# conversion here happens as the very last step, after total is finalized
# -- confirm_order converts the already-finalized USD total, it does not
# recompute tax in the settlement currency. (Contrast with the comment on
# confirm_order below, which claims the opposite. See that function for
# the tiebreaker reasoning; convert-last wins.)
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def convert(amount, currency):
    if currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {currency}")
    return round(amount * EXCHANGE_RATES[currency], 2)


def format_currency(amount, currency):
    if currency not in CURRENCY_SYMBOLS:
        raise ValueError(f"unknown currency: {currency}")
    return f"{CURRENCY_SYMBOLS[currency]}{amount:.2f}"


# ---------------------------------------------------------------------------
# shipping.py
# ---------------------------------------------------------------------------

def shipping_cost(weight, distance, express):
    if weight <= 0:
        raise ValueError("weight must be positive")
    if distance <= 0:
        raise ValueError("distance must be positive")
    cost = weight * 0.5 + distance * 0.29
    if express:
        cost *= 1.5
    return round(cost, 2)


# ---------------------------------------------------------------------------
# inventory.py -- reserve_stock/release_stock operate on a caller-supplied
# catalog (as opposed to catalog.py's module-level CATALOG used only for
# line-item pricing). reserve_stock is one of the 4 audited mutators;
# release_stock is not.
# ---------------------------------------------------------------------------

def reserve_stock(catalog, sku, qty, order_id):
    entry = catalog[sku]
    if qty > entry["stock"]:
        raise ValueError(f"insufficient stock for {sku}: requested {qty}, have {entry['stock']}")
    entry["stock"] -= qty
    AUDIT_LOG.append(_audit_entry("reserve_stock", order_id, {"sku": sku, "qty": qty}))


def release_stock(catalog, sku, qty):
    catalog[sku]["stock"] += qty


def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, info in catalog.items() if info["stock"] <= threshold)


# ---------------------------------------------------------------------------
# tax.py
# ---------------------------------------------------------------------------

TAX_RATES = {"US-CA": 0.0825, "US-OR": 0.0, "US-NY": 0.0888, "EU": 0.20}


def calculate_tax(amount, region):
    if region not in TAX_RATES:
        raise ValueError(f"unknown tax region: {region}")
    return round(amount * TAX_RATES[region], 2)


# ---------------------------------------------------------------------------
# loyalty.py -- redeem_loyalty_points is one of the 4 audited mutators.
# ---------------------------------------------------------------------------

POINT_VALUE = 0.01  # $ value of a single loyalty point


def redeem_loyalty_points(amount, points_available, points_to_redeem, order_id):
    if points_to_redeem < 0:
        raise ValueError("points_to_redeem must not be negative")
    if points_to_redeem > points_available:
        raise ValueError("cannot redeem more points than are available")
    discount = points_to_redeem * POINT_VALUE
    result = max(0.0, round(amount - discount, 2))
    AUDIT_LOG.append(
        _audit_entry(
            "redeem_loyalty_points",
            order_id,
            {"amount": amount, "points_to_redeem": points_to_redeem, "result": result},
        )
    )
    return result


# ---------------------------------------------------------------------------
# reporting.py
# ---------------------------------------------------------------------------

def summarize_orders(orders):
    return {
        "order_count": len(orders),
        "total_revenue": round(sum(o["total"] for o in orders), 2),
    }


# ---------------------------------------------------------------------------
# engine.py -- order-lifecycle state machine.
#
# States: draft -> validated -> priced -> confirmed -> shipped.
# Order state lives at order["state"].
# ---------------------------------------------------------------------------

def validate_order(order):
    state = order.get("state", "draft")
    if state != "draft":
        raise ValueError(f"order must be in draft state to validate, got {state!r}")
    for field in ("items", "region", "membership_tier", "currency"):
        if field not in order:
            raise ValueError(f"missing required field: {field}")
    order["state"] = "validated"
    return order


def build_invoice(order):
    if order.get("state") != "validated":
        raise ValueError(f"order must be in validated state to price, got {order.get('state')!r}")

    _per_sku, subtotal, total_qty = build_line_items(order["items"])
    coupon_code = order.get("coupon_code")
    post_discount_amount = round(
        stack_discounts(subtotal, total_qty, order["membership_tier"], coupon_code), 2
    )
    tax = calculate_tax(post_discount_amount, order["region"])
    total = round(post_discount_amount + tax, 2)

    order["state"] = "priced"
    order["post_discount_amount"] = post_discount_amount
    order["total"] = total

    return {
        "order_id": order.get("order_id"),
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "tax": tax,
        "total": total,
    }


# confirm_order: currency conversion happens before tax is applied, so tax
# is computed in the settlement currency rather than in USD. (Contrast with
# the comment above convert()/format_currency(), which claims conversion is
# the very last step after total is finalized -- that comment disagrees
# with this one.)
#
# TIEBREAKER: convert-last wins. The order-lifecycle state machine requires
# state "priced" before confirm_order can run at all, and pricing (the part
# of build_invoice that computes total, including tax) already ran and
# transitioned the order out of "validated" by the time confirm_order
# executes. Tax is therefore already finalized, in USD, at the pricing
# stage -- a stage that has already completed and that confirm_order has no
# state-machine-sanctioned way to re-enter without duplicating tax logic
# across two call sites. Converting the already-finalized order["total"] is
# the reading consistent with the lifecycle contract this file enforces
# everywhere else; the "before tax" comment above would require
# confirm_order to reach backward into a stage it isn't chartered to redo.
# confirm_order is one of the 4 audited mutators.
def confirm_order(order, settlement_currency=None):
    if order.get("state") != "priced":
        raise ValueError(f"order must be in priced state to confirm, got {order.get('state')!r}")

    settlement_total = None
    if settlement_currency is not None:
        # convert-last: order["total"] is already fully finalized (tax
        # included) by build_invoice; confirm_order only converts it.
        settlement_total = convert(order["total"], settlement_currency)

    order["state"] = "confirmed"
    AUDIT_LOG.append(_audit_entry("confirm_order", order.get("order_id"), {"total": order.get("total")}))

    if settlement_currency is not None:
        order["settlement_currency"] = settlement_currency
        order["settlement_total"] = settlement_total
        order["settlement_total_formatted"] = format_currency(settlement_total, settlement_currency)

    return order


def ship_order(order):
    if order.get("state") != "confirmed":
        raise ValueError(f"order must be in confirmed state to ship, got {order.get('state')!r}")
    order["state"] = "shipped"
    return order

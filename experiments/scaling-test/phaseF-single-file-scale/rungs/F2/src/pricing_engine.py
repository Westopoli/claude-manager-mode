"""pricing_engine.py — spec: ../../SPEC.md::Rungs::AC-1

Single-file merge of the catalog, discounts, engine, validation, currency,
shipping, and notifications sections of
../../phaseE-leaf-ceiling-v2/MODULES.md, scoped to rung F2 (matches Phase
E's rung E3). All names are top-level in this one module instead of split
across files — see SPEC.md for why (Phase F's file-count axis).
"""

# --- catalog -----------------------------------------------------------

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    per_sku_subtotals = {}
    total_qty = 0
    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        product = CATALOG[sku]  # raises KeyError for unknown sku
        if qty > product["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        per_sku_subtotals[sku] = round(product["unit_price"] * qty, 2)
        total_qty += qty
    order_subtotal = round(sum(per_sku_subtotals.values()), 2)
    return per_sku_subtotals, order_subtotal, total_qty


# --- discounts ---------------------------------------------------------
#
# CONTRADICTION NOTE (seeded, deliberate — see SPEC.md "The contradiction,
# restated for single-file form"): this comment block, placed near the
# discount functions, states the canonical stacking order is COUPON FIRST,
# then volume, then membership. build_invoice's own docstring (below, in
# the engine section of this same file) states a DIFFERENT order: volume,
# then membership, then coupon LAST. No third source in this file resolves
# it — same unresolved-contradiction shape MODULES.md seeds across
# discounts.py/engine.py, just moved inside one file.
#
# RESOLUTION (mechanical tiebreaker — the same one taken at
# phaseE-leaf-ceiling-v2 rung E3 for the cross-file version of this exact
# contradiction, see that rung's discounts.py/engine.py): the function that
# actually IMPLEMENTS the stacking order is authoritative for it.
# stack_discounts, below, applies coupon first. build_invoice must call
# stack_discounts and use its return value verbatim rather than
# recomputing or re-deriving its own order — so no matter what
# build_invoice's own docstring says, the order that actually executes is
# this one: coupon, then volume, then membership.

COUPONS = {"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}


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
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)


# --- validation (E2+) -------------------------------------------------------

def validate_order(order):
    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order or not isinstance(order["region"], str):
        raise ValueError("region is missing or wrong-typed")
    if "membership_tier" not in order or not isinstance(order["membership_tier"], str):
        raise ValueError("membership_tier is missing or wrong-typed")
    if "currency" not in order or not isinstance(order["currency"], str):
        raise ValueError("currency is missing or wrong-typed")


# --- currency (E2+) ----------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}
_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency!r}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    if currency not in _CURRENCY_SYMBOLS:
        raise ValueError(f"unknown currency: {currency!r}")
    return f"{_CURRENCY_SYMBOLS[currency]}{amount:.2f}"


# --- shipping (E3+) ----------------------------------------------------------

def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


# --- notifications (E3+) ------------------------------------------------
#
# Deliberately standalone: `low_stock_alert` is a real, independently useful
# inventory-monitoring query over CATALOG-shaped dicts. It is bundled into
# this file because F2 holds impl_files at exactly 1 (Phase F's file-count
# axis, see SPEC.md), not because it belongs to build_invoice's composition
# chain. build_invoice never calls it, and no fake caller was added here or
# in the test file just to give it one — see leaf-F2.ASSUMPTIONS.md for the
# reasoning.

def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, entry in catalog.items() if entry["stock"] < threshold)


# --- engine (orchestrator) ---------------------------------------------

def build_invoice(order):
    """Orchestrator. Delegates for real to validate_order, build_line_items,
    stack_discounts, shipping_cost, convert, and format_currency — it does
    not recompute any of their math itself.

    CONTRADICTION NOTE (seeded, deliberate — see the note above
    stack_discounts): this docstring states the discount order as VOLUME,
    then MEMBERSHIP, then COUPON LAST — the opposite of the coupon-first
    order documented near the discount functions above. This is the
    losing half of the intra-file contradiction: the code below calls
    stack_discounts and uses its return value verbatim, so the order that
    actually executes is stack_discounts's own (coupon-first), not the
    order this paragraph describes.
    """
    validate_order(order)

    per_sku_subtotals, order_subtotal, total_qty = build_line_items(order["items"])

    post_discount_amount = stack_discounts(
        order_subtotal,
        total_qty,
        order["membership_tier"],
        order.get("coupon_code"),
    )

    shipping_usd = shipping_cost(
        order["weight_kg"], order["distance_km"], order.get("express", False)
    )

    total = round(post_discount_amount + shipping_usd, 2)

    to_currency = order["currency"]
    converted_total = convert(total, to_currency)
    total_formatted = format_currency(converted_total, to_currency)

    return {
        "line_items": per_sku_subtotals,
        "subtotal": order_subtotal,
        "post_discount_amount": post_discount_amount,
        "shipping_usd": shipping_usd,
        "total": total,
        "total_formatted": total_formatted,
    }

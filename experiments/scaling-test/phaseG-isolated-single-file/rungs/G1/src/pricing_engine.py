"""pricing_engine.py

Single-file merge of the phaseE catalog.py / discounts.py / engine.py
surface (see ../../phaseE-leaf-ceiling-v2/MODULES.md lines 7-24), as
required by leaf-G1's brief. Same top-level names, same signatures, same
behavior as the three original modules would have had, just flattened into
one file.
"""

# ---------------------------------------------------------------------------
# catalog.py surface
# ---------------------------------------------------------------------------

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    """Build {sku: line_total} from a list of {"sku": ..., "qty": ...}.

    Returns (line_items, subtotal, total_qty).
    Raises KeyError for an unknown sku, ValueError for a qty exceeding
    (or equal to, when stock is 0) available stock.
    """
    line_items = {}
    total_qty = 0

    for item in items:
        sku = item["sku"]
        qty = item["qty"]

        catalog_entry = CATALOG[sku]  # KeyError propagates for unknown sku

        if qty > catalog_entry["stock"]:
            raise ValueError(
                f"requested qty {qty} for {sku!r} exceeds stock "
                f"{catalog_entry['stock']}"
            )

        line_total = round(catalog_entry["unit_price"] * qty, 2)
        line_items[sku] = round(line_items.get(sku, 0.0) + line_total, 2)
        total_qty += qty

    subtotal = round(sum(line_items.values()), 2)
    return line_items, subtotal, total_qty


# ---------------------------------------------------------------------------
# discounts.py surface
#
# NOTE (seeded contradiction, per leaf-G1's brief): this comment block
# states one order of operations for stacking discounts: apply the coupon
# FIRST, then volume, then membership. See the contradictory statement on
# build_invoice below, which states the opposite order. No external file in
# scope says which one is authoritative on its own.
# ---------------------------------------------------------------------------

_VOLUME_TIERS = (
    (50, 0.10),
    (10, 0.05),
    (0, 0.0),
)

_MEMBERSHIP_RATES = {
    "none": 0.0,
    "silver": 0.03,
    "gold": 0.07,
    "platinum": 0.12,
}

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty):
    for threshold, rate in _VOLUME_TIERS:
        if total_qty >= threshold:
            return rate
    return 0.0  # unreachable given the 0-floor tier, kept for safety


def membership_discount_rate(tier):
    if tier not in _MEMBERSHIP_RATES:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return _MEMBERSHIP_RATES[tier]


def apply_coupon(amount, code):
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")

    coupon = COUPONS[code]

    if coupon["expired"]:
        raise ValueError(f"coupon {code!r} is expired")

    if amount < coupon["min_spend"]:
        raise ValueError(
            f"amount {amount} is below min_spend {coupon['min_spend']} "
            f"for coupon {code!r}"
        )

    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    """Stack volume, membership, and (optionally) a coupon discount.

    Tiebreaker: this file's two comment blocks state opposing orders (see
    the note above this section vs. the note on build_invoice below). This
    resolves it as volume -> membership -> coupon-last, matching the
    precedent set at ../../phaseE-leaf-ceiling-v2/rungs/E1/src/discounts.py
    for the identical contradiction, on the reasoning that build_invoice
    (the orchestrator) is the canonical caller and its stated order governs.
    """
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)

    membership_rate = membership_discount_rate(tier)  # validates tier
    amount = round(amount * (1 - membership_rate), 2)

    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)

    return amount


# ---------------------------------------------------------------------------
# engine.py surface
#
# NOTE (seeded contradiction, continued): this comment states the canonical
# order of operations is volume discount, then membership discount, then
# coupon LAST -- the opposite of the note above stack_discounts. Per the
# same precedent cited in stack_discounts' docstring, this order (volume ->
# membership -> coupon-last) is the one actually implemented.
# ---------------------------------------------------------------------------


def build_invoice(order):
    """Orchestrate a full invoice from an order dict.

    Order keys (not pinned by the contract excerpt, assumed per the test
    file's own documented assumptions): "items", "membership_tier"
    (defaults to "none"), "coupon_code" (defaults to no coupon).
    """
    items = order["items"]
    line_items, subtotal, total_qty = build_line_items(items)

    tier = order.get("membership_tier", "none")
    coupon_code = order.get("coupon_code")

    post_discount_amount = stack_discounts(
        subtotal, total_qty, tier, coupon_code=coupon_code
    )

    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "total": post_discount_amount,
    }

"""pricing_engine.py — order-pricing engine (catalog + discounts + engine,
merged into a single module).

See ../../phaseE-leaf-ceiling-v2/MODULES.md lines 7-24 for the canonical
spec (catalog.py, discounts.py, engine.py sections). This file declares the
same names/signatures/behavior as top-level names in one module instead of
three files, per the phaseF-single-file-scale/rungs/F1 brief.

The file is organized into three clearly delimited sections below, mirroring
the three modules it replaces: CATALOG SECTION, DISCOUNTS SECTION, ENGINE
SECTION.
"""

# ---------------------------------------------------------------------------
# CATALOG SECTION (was catalog.py)
# ---------------------------------------------------------------------------

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    """items: [{"sku": str, "qty": int}, ...]

    Returns (per_sku_subtotals, order_subtotal, total_qty).
    Raises KeyError for an unknown sku, ValueError if qty exceeds stock.
    """
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0

    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        product = CATALOG[sku]  # KeyError propagates for unknown sku
        if qty > product["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        line_total = round(product["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty

    return per_sku_subtotals, round(order_subtotal, 2), total_qty


# ---------------------------------------------------------------------------
# DISCOUNTS SECTION (was discounts.py)
#
# CONTRADICTION SEED (intra-file, deliberately unresolved by the spec):
# The canonical order for stack_discounts, as this section's own spec
# (MODULES.md::discounts.py) states it, is:
#
#     coupon applied first, then volume, then membership.
#
# See the ENGINE SECTION below (build_invoice's docstring) for the SECOND,
# CONTRADICTING statement of this order. No third source in this file (or
# anywhere else) resolves which statement is correct — this is the same
# deliberately unresolved contradiction used across phaseD/phaseE, moved
# inside a single file for phaseF. See "CONTRADICTION RESOLUTION" below for
# how it was handled here.
#
# CONTRADICTION RESOLUTION (recorded before implementation, not silently
# inferred): resolved as volume, then membership, then coupon-last. This
# matches the resolution used at phaseE-leaf-ceiling-v2/rungs/E1 (same
# domain, same contradiction, matched scope) via that leaf's question
# ledger (.swarm/answers/leaf-E1-Q1.md), and matches the phrasing in
# MODULES.md::engine.py which explicitly calls its own order "the canonical
# order used elsewhere in this system." This leaf ran solo (test-author +
# builder + gate-runner, no separate parent to escalate to mid-task), so
# per the brief's escalation guidance the documented-tiebreaker path was
# taken instead of opening a question ledger entry: pick the
# mechanically-defensible choice (consistency with the established E1
# precedent for this exact contradiction) and document it here and in
# .swarm/briefs/leaf-F1.ASSUMPTIONS.md. Decided BEFORE writing
# stack_discounts/build_invoice below, not discovered by test failure.
# ---------------------------------------------------------------------------

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty):
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount, code):
    coupon = COUPONS.get(code)
    if coupon is None:
        raise ValueError(f"unknown coupon code: {code!r}")
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(
            f"amount {amount} is below min_spend {coupon['min_spend']} "
            f"for coupon {code!r}"
        )
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    """Resolved order (see CONTRADICTION RESOLUTION above): volume, then
    membership, then coupon-last. Coupon's min_spend check therefore
    applies to the post-volume-and-membership amount, not the raw
    subtotal."""
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = round(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    return amount


# ---------------------------------------------------------------------------
# ENGINE SECTION (was engine.py)
# ---------------------------------------------------------------------------


def build_invoice(order):
    """order: dict with at least "items" ([{"sku": str, "qty": int}, ...]),
    and optionally "membership_tier" (default "none") and "coupon_code"
    (default None).

    Delegates to build_line_items and stack_discounts (CATALOG/DISCOUNTS
    sections above) — does not reimplement their logic inline.

    Discount order (this section's own statement, per MODULES.md::engine.py):
    volume discount, then membership discount, then coupon last (coupon
    applied to the post-membership amount). This AGREES with the resolution
    recorded in the DISCOUNTS SECTION above but DISAGREES with that same
    section's first statement of its own canonical order (coupon-first) —
    that is the seeded intra-file contradiction; see the CONTRADICTION
    RESOLUTION note above stack_discounts for how it was settled.
    """
    items = order["items"]
    tier = order.get("membership_tier", "none")
    coupon_code = order.get("coupon_code")

    line_items, subtotal, total_qty = build_line_items(items)
    post_discount_amount = stack_discounts(
        subtotal, total_qty, tier, coupon_code=coupon_code
    )

    return {
        "line_items": line_items,
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "total": round(post_discount_amount, 2),
    }

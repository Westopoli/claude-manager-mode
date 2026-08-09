"""
pricing_engine.py -- rung H3 (phaseH ceiling search).

Single-file implementation of the full cumulative order-pricing domain
contract:

  * All 12 base modules (../../phaseE-leaf-ceiling-v2/MODULES.md):
    catalog, discounts, engine, validation, currency, shipping,
    notifications, tax, loyalty, reporting, audit_log, inventory.
  * Order-lifecycle state machine (phaseG SPEC.md, G2+):
    draft -> validated -> priced -> confirmed -> shipped.
  * Shared `_audit_entry` helper (phaseG SPEC.md, G3+), called from
    SEVEN mutator sites: reserve_stock, redeem_loyalty_points,
    apply_coupon, confirm_order, record_approval (H1), apply_campaign
    (H2), partial_refund (H3).
  * Multi-currency settlement on confirm_order (phaseG SPEC.md, G4).
  * H1's OrderApproval concern (manager/finance approval gating).
  * H2's CAMPAIGNS registry + apply_campaign (time-windowed stacking).
  * H3's own new layer: TAX_JURISDICTIONS / compute_tax (multi-
    jurisdiction cascading tax) and partial_refund (proportional
    reversal of tax/campaign/loyalty effects on a shipped order).

Seeded contradictions (kept intra-file per every prior rung's pattern --
NOT a bug, this is the cross-rung measurement constant):

  1. Coupon-order: discounts.py's own comment below says "coupon first,
     then volume, then membership." engine.py's comment (in
     build_invoice) says "volume discount, then membership discount,
     then coupon last", and explicitly claims this matches "the
     canonical order used elsewhere in this system." RESOLVED: coupon
     last -- the comment that asserts system-wide consistency is the
     one this implementation follows; discounts.py's own comment makes
     no such consistency claim.

  2. Currency-timing: a comment near convert()/format_currency() says
     conversion happens "as the very last step, after total is
     finalized." A comment on confirm_order says conversion happens
     "before tax is applied, so tax is computed in the settlement
     currency." RESOLVED: convert-last -- the order-lifecycle state
     machine requires state "priced" (tax already finalized in USD)
     before confirm_order can run at all; confirm_order has no
     state-machine permission to re-enter pricing, so settlement
     conversion is a presentation step applied to the already-finalized
     USD total, not a re-derivation of tax.

  3. Campaign-order (H2's own): one passage says "campaigns apply after
     all other discounts, to the final discounted total." Another says
     "campaigns apply first, before any other discount logic runs,
     since promotional pricing supersedes standing discounts."
     RESOLVED: campaigns apply after all other discounts --
     apply_campaign is a standalone call operating on an order that
     already carries a computed post_discount_amount, the same shape as
     coupon-last and record_approval; partial_refund's own reliance on
     post_discount_amount as the authoritative already-composed value
     is consistent only with this reading.
"""

from decimal import Decimal, ROUND_HALF_UP


def _round2(value, ndigits=2):
    """round(value, ndigits) using round-half-up on the decimal value of
    `value`'s shortest string representation, rather than Python's
    built-in round() (round-half-to-even, applied to the binary float's
    exact value -- e.g. round(138.225, 2) == 138.22 because 138.225 is
    not exactly representable in binary float and the nearest
    representable value is fractionally below .225). Every rounding call
    in this file goes through this helper for consistency."""
    quantum = Decimal(1).scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


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
    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        info = CATALOG[sku]
        if qty > info["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        line_total = _round2(info["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty
    order_subtotal = _round2(order_subtotal, 2)
    return per_sku_subtotals, order_subtotal, total_qty


# ---------------------------------------------------------------------------
# discounts.py
#
# NOTE (seeded contradiction 1): this comment states the order is
# "coupon first, then volume, then membership." engine.py's build_invoice
# below states a different order and claims system-wide authority --
# see the module docstring above for the resolution. stack_discounts
# below implements coupon-LAST (volume, then membership, then coupon).
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
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def apply_coupon(amount, code, order_id=None):
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon {code!r} is expired")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount {amount} is below min_spend for coupon {code!r}")
    result = _round2(amount * (1 - coupon["rate"]), 2)
    if order_id is not None:
        AUDIT_LOG.append(_audit_entry("apply_coupon", order_id, {"code": code, "amount": amount}))
    return result


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    # RESOLVED per seeded contradiction 1 (see module docstring):
    # volume, then membership, then coupon LAST.
    amount = _round2(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = _round2(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code is not None:
        coupon = COUPONS[coupon_code]
        if coupon["expired"]:
            raise ValueError(f"coupon {coupon_code!r} is expired")
        if amount < coupon["min_spend"]:
            raise ValueError(f"amount {amount} is below min_spend for coupon {coupon_code!r}")
        amount = _round2(amount * (1 - coupon["rate"]), 2)
    return amount


# ---------------------------------------------------------------------------
# validation.py / engine.py -- order-lifecycle state machine (G2+)
# ---------------------------------------------------------------------------

_STATE_ORDER = ["draft", "validated", "priced", "confirmed", "shipped"]


def _require_state(order, required):
    current = order.get("state", "draft")
    if current != required:
        raise ValueError(f"order must be in {required!r} state (was {current!r})")


def validate_order(order):
    _require_state(order, "draft")
    if not isinstance(order.get("items"), list) or len(order.get("items", [])) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order or not isinstance(order["region"], str):
        raise ValueError("region is required")
    if "membership_tier" not in order or not isinstance(order["membership_tier"], str):
        raise ValueError("membership_tier is required")
    if "currency" not in order or not isinstance(order["currency"], str):
        raise ValueError("currency is required")
    order["state"] = "validated"


def build_invoice(order):
    # engine.py orchestrator.
    # NOTE (seeded contradiction 1): this comment states the canonical
    # order is "volume discount, then membership discount, then coupon
    # last", matching "the canonical order used elsewhere in this
    # system." See discounts.py's stack_discounts above and the module
    # docstring for the resolution actually implemented (coupon-last).
    _require_state(order, "validated")

    per_sku, subtotal, total_qty = build_line_items(order["items"])
    order["total_qty"] = total_qty

    coupon_code = order.get("coupon_code")
    post_discount_amount = stack_discounts(
        subtotal, total_qty, order["membership_tier"], coupon_code
    )
    order["post_discount_amount"] = post_discount_amount

    tax = compute_tax({"region": order["region"], "post_discount_amount": post_discount_amount,
                        "special_district": order.get("special_district", False)})
    total = _round2(post_discount_amount + tax, 2)
    order["total"] = total
    order["state"] = "priced"

    return {"post_discount_amount": post_discount_amount, "total": total}


def confirm_order(order, settlement_currency=None):
    _require_state(order, "priced")

    total = order.get("total", order.get("post_discount_amount", 0.0))
    _check_approvals(order, total)

    order["state"] = "confirmed"

    if settlement_currency is not None:
        # NOTE (seeded contradiction 2): this comment states conversion
        # happens "before tax is applied, so tax is computed in the
        # settlement currency." See the comment near convert()/
        # format_currency() below, which states the opposite (convert
        # as the very last step). RESOLVED per the module docstring:
        # convert-LAST -- the already-finalized USD total is converted
        # here, as confirm_order's final step.
        settlement_total = convert(total, settlement_currency)
        order["settlement_total"] = settlement_total
        order["settlement_currency"] = settlement_currency
        order["settlement_total_formatted"] = format_currency(settlement_total, settlement_currency)

    AUDIT_LOG.append(_audit_entry("confirm_order", order.get("order_id"), {"total": total}))

    return order


def ship_order(order):
    _require_state(order, "confirmed")
    order["state"] = "shipped"
    return order


# ---------------------------------------------------------------------------
# currency.py
#
# NOTE (seeded contradiction 2): this comment states currency conversion
# happens "as the very last step, after total is finalized." See
# confirm_order above for the contradictory comment and the resolution
# actually implemented (convert-last).
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency!r}")
    return _round2(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    if currency not in symbols:
        raise ValueError(f"unknown currency: {currency!r}")
    return f"{symbols[currency]}{amount:.2f}"


# ---------------------------------------------------------------------------
# shipping.py
# ---------------------------------------------------------------------------

def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = _round2(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = _round2(base * 1.5, 2)
    return base


# ---------------------------------------------------------------------------
# notifications.py
# ---------------------------------------------------------------------------

def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, info in catalog.items() if info["stock"] < threshold)


# ---------------------------------------------------------------------------
# tax.py -- original single-rate calculate_tax, kept unchanged.
# ---------------------------------------------------------------------------

_TAX_RATES = {"US-CA": 0.0825, "US-OR": 0.0, "US-NY": 0.08875, "EU": 0.20}


def calculate_tax(amount, region):
    if region not in _TAX_RATES:
        raise ValueError(f"unknown region: {region!r}")
    return _round2(amount * _TAX_RATES[region], 2)


# ---------------------------------------------------------------------------
# loyalty.py
# ---------------------------------------------------------------------------

def redeem_loyalty_points(amount, points_available, points_to_redeem, order_id=None):
    if points_to_redeem > points_available or points_to_redeem < 0:
        raise ValueError("invalid points_to_redeem")
    result = _round2(amount - points_to_redeem / 100, 2)
    result = max(result, 0.0)
    if order_id is not None:
        AUDIT_LOG.append(_audit_entry(
            "redeem_loyalty_points", order_id,
            {"points_to_redeem": points_to_redeem, "amount": amount},
        ))
    return result


# ---------------------------------------------------------------------------
# reporting.py
# ---------------------------------------------------------------------------

def summarize_orders(orders):
    if not orders:
        return {"order_count": 0, "total_revenue": 0.0}
    return {
        "order_count": len(orders),
        "total_revenue": _round2(sum(o["total"] for o in orders), 2),
    }


# ---------------------------------------------------------------------------
# audit_log.py + shared _audit_entry helper (phaseG G3+)
# ---------------------------------------------------------------------------

AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})


def _audit_entry(action, order_id, detail):
    return {"action": action, "order_id": order_id, "detail": detail}


# ---------------------------------------------------------------------------
# inventory.py
# ---------------------------------------------------------------------------

def reserve_stock(catalog, sku, qty, order_id=None):
    if sku not in catalog:
        raise KeyError(f"unknown sku: {sku!r}")
    new_stock = catalog[sku]["stock"] - qty
    if new_stock < 0:
        raise ValueError(f"insufficient stock for sku {sku!r}")
    catalog[sku]["stock"] = new_stock
    if order_id is not None:
        AUDIT_LOG.append(_audit_entry("reserve_stock", order_id, {"sku": sku, "qty": qty}))


def release_stock(catalog, sku, qty):
    if sku not in catalog:
        raise KeyError(f"unknown sku: {sku!r}")
    catalog[sku]["stock"] += qty


# ---------------------------------------------------------------------------
# H1: OrderApproval concern -- multi-tier manager/finance approval workflow
# ---------------------------------------------------------------------------

APPROVAL_THRESHOLD = 500.0
ESCALATION_THRESHOLD = 2000.0


def record_approval(order, role):
    if role == "finance" and "manager" not in order.get("approvals", []):
        raise ValueError("finance approval requires manager approval first")
    order.setdefault("approvals", [])
    order["approvals"].append(role)
    entry = _audit_entry("record_approval", order.get("order_id"), {"role": role})
    AUDIT_LOG.append(entry)
    return entry


def _check_approvals(order, total):
    approvals = order.get("approvals", [])
    if total >= ESCALATION_THRESHOLD:
        if "manager" not in approvals:
            raise ValueError("missing required approval: manager")
        if "finance" not in approvals:
            raise ValueError("missing required approval: finance")
    elif total > APPROVAL_THRESHOLD:
        if "manager" not in approvals:
            raise ValueError("missing required approval: manager")
    # totals <= APPROVAL_THRESHOLD need no approval at all.


# ---------------------------------------------------------------------------
# H2: CAMPAIGNS registry + apply_campaign -- time-windowed promotional
# campaign stacking.
#
# NOTE (seeded contradiction 3): one reading of this file's own spec text
# says campaigns apply after all other discounts, to the final discounted
# total. Another reading says campaigns apply first, before any other
# discount logic runs, since promotional pricing supersedes standing
# discounts. RESOLVED per the module docstring: campaigns apply AFTER all
# other discounts -- apply_campaign operates on order["post_discount_amount"]
# as the already-composed, authoritative value.
# ---------------------------------------------------------------------------

CAMPAIGNS = {
    "HOLIDAY20": {"stacking": "multiply", "rate": 0.15, "starts_at": "2026-06-01", "ends_at": "2026-08-31"},
    "CLEARANCE30": {"stacking": "additive", "value": 30.0, "starts_at": "2026-01-01", "ends_at": "2026-12-31"},
    "SPRING5": {"stacking": "multiply", "rate": 0.05, "starts_at": "2025-03-01", "ends_at": "2025-05-31"},
    "DOUBLE20": {"stacking": "multiply", "rate": 0.20, "starts_at": "2026-01-01", "ends_at": "2026-12-31"},
}


def apply_campaign(order, campaign_id, as_of):
    if campaign_id not in CAMPAIGNS:
        raise ValueError(f"unknown campaign: {campaign_id!r}")
    campaign = CAMPAIGNS[campaign_id]
    if not (campaign["starts_at"] <= as_of <= campaign["ends_at"]):
        raise ValueError(f"campaign {campaign_id!r} is not active on {as_of!r}")

    amount = order["post_discount_amount"]
    if campaign["stacking"] == "multiply":
        new_amount = _round2(amount * (1 - campaign["rate"]), 2)
    else:  # "additive"
        new_amount = max(_round2(amount - campaign["value"], 2), 0.0)

    order["post_discount_amount"] = new_amount

    AUDIT_LOG.append(_audit_entry(
        "apply_campaign", order.get("order_id"),
        {"campaign_id": campaign_id, "as_of": as_of, "amount_before": amount, "amount_after": new_amount},
    ))

    return order


# ---------------------------------------------------------------------------
# H3, part A: multi-jurisdiction tax cascading
# ---------------------------------------------------------------------------

TAX_JURISDICTIONS = {
    "US-CA": [
        {"name": "state", "rate": 0.0725, "active": True},
        {"name": "local", "rate": 0.01, "active": True},
        {"name": "special_district", "rate": 0.0025, "active": False},
    ],
    "US-OR": [],
    "US-NY": [
        {"name": "state", "rate": 0.04, "active": True},
        {"name": "local", "rate": 0.04875, "active": True},
    ],
    "EU": [
        {"name": "flat", "rate": 0.20, "active": True},
    ],
}


def compute_tax(order):
    region = order["region"]
    if region not in TAX_JURISDICTIONS:
        raise ValueError(f"unknown region: {region!r}")
    amount = order["post_discount_amount"]
    special_district_override = order.get("special_district")

    total_rate = 0.0
    for layer in TAX_JURISDICTIONS[region]:
        active = layer["active"]
        if layer["name"] == "special_district" and special_district_override is not None:
            active = special_district_override
        if active:
            total_rate += layer["rate"]

    return _round2(amount * total_rate, 2)


# ---------------------------------------------------------------------------
# H3, part B: partial_refund -- refund/partial-cancellation reversal logic
# (7th _audit_entry call site).
# ---------------------------------------------------------------------------

def partial_refund(order, item_id, qty):
    _require_state(order, "shipped")

    original_qty = None
    for item in order.get("items", []):
        if item["sku"] == item_id:
            original_qty = item["qty"]
            break
    if original_qty is None:
        raise ValueError(f"item {item_id!r} not found on order")
    if qty > original_qty:
        raise ValueError(f"refund qty {qty} exceeds original ordered qty {original_qty} for {item_id!r}")

    total_qty = order["total_qty"]
    share = qty / total_qty

    share_amount = _round2(order["post_discount_amount"] * share, 2)
    tax_on_share = compute_tax({
        "region": order["region"],
        "post_discount_amount": share_amount,
        "special_district": order.get("special_district"),
    })
    refund_amount = _round2(share_amount + tax_on_share, 2)

    points_redeemed = order.get("points_redeemed", 0)
    points_credited = _round2(points_redeemed * share)
    if points_credited:
        order["points_available"] = order.get("points_available", 0) + points_credited

    release_stock(CATALOG, item_id, qty)

    entry = _audit_entry(
        "partial_refund", order.get("order_id"),
        {"item_id": item_id, "qty": qty, "refund_amount": refund_amount, "points_credited": points_credited},
    )
    AUDIT_LOG.append(entry)

    return {"refund_amount": refund_amount, "points_credited": points_credited}

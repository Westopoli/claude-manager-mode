"""
pricing_engine.py -- rung H2 cumulative single-file implementation.

Covers the FULL cumulative contract for this experiment lineage:

  * All 12 base modules from phaseE-leaf-ceiling-v2/MODULES.md
    (catalog, discounts, engine, validation, currency, shipping,
    notifications, tax, loyalty, reporting, audit_log, inventory).
  * The order-lifecycle state machine from phaseG SPEC.md (G2+):
    draft -> validated -> priced -> confirmed -> shipped.
  * The shared `_audit_entry` helper (phaseG G3), called from every
    state-mutating function.
  * Multi-currency settlement on confirm_order (phaseG G4).
  * H1's OrderApproval concern -- multi-tier manager/finance approval
    gating on confirm_order, carried forward unchanged.
  * H2's own new layer: the CAMPAIGNS registry and apply_campaign(),
    time-windowed promotional-campaign stacking.

Three seeded/pinned intra-file ambiguities are carried in this module.
All three are resolved in the actual implementation below per the
tiebreakers this rung's test suite pins; the contradictory comments are
kept intentionally, as the measurement artifact this experiment lineage
tracks.

CONTRADICTION 1 (coupon-order, carried from every prior rung E1-H2):
  discounts.py's own convention says "coupon first, then volume, then
  membership". engine.py's convention says "volume discount, then
  membership discount, then coupon last", and claims this matches "the
  canonical order used elsewhere in this system". RESOLVED HERE as
  coupon-last (the tiebreaker precedent carried from Phase G / H1).

CONTRADICTION 2 (currency-conversion timing, carried from phaseG G4):
  one convention says currency conversion happens "as the very last
  step, after total is finalized". A separate convention (attached to
  confirm_order) says conversion happens "before tax is applied, so tax
  is computed in the settlement currency". RESOLVED HERE as
  convert-last: confirm_order converts the already-finalized USD total
  (which already includes tax, computed back in build_invoice while the
  order was in the "validated" -> "priced" transition) as its own final
  step, treating currency conversion as a presentation/settlement layer
  on top of an already-completed pricing pipeline.

CONTRADICTION 3 (campaign-application-order, H2's own, new): one
  convention (attached to apply_campaign) says campaigns apply after all
  other discounts, to the final discounted total -- i.e. apply_campaign
  runs on stack_discounts's output (order["post_discount_amount"]).
  Another convention (attached to the CAMPAIGNS registry) says campaigns
  apply first, before any other discount logic runs, since promotional
  pricing supersedes standing discounts -- i.e. apply_campaign would run
  on the raw pre-discount subtotal, with stack_discounts then running on
  ITS output. RESOLVED HERE as campaigns-after-all-other-discounts:
  apply_campaign is a standalone call operating on an order that already
  carries a computed post_discount_amount from the ordinary discount
  chain, the same shape as coupon-last and record_approval, neither of
  which reaches back to re-run earlier pipeline stages.
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
    """items: [{"sku": str, "qty": int}, ...] -> (per_sku_subtotals, order_subtotal, total_qty)."""
    per_sku = {}
    subtotal = 0.0
    total_qty = 0
    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        if sku not in CATALOG:
            raise KeyError(f"unknown sku: {sku}")
        stock = CATALOG[sku]["stock"]
        if qty > stock:
            raise ValueError(f"requested qty {qty} exceeds stock for {sku}")
        price = CATALOG[sku]["unit_price"]
        line_total = round(price * qty, 2)
        per_sku[sku] = round(per_sku.get(sku, 0.0) + line_total, 2)
        subtotal += line_total
        total_qty += qty
    subtotal = round(subtotal, 2)
    return per_sku, subtotal, total_qty


# ---------------------------------------------------------------------------
# discounts.py
#
# NOTE (seeded contradiction 1, coupon-order): this module's own
# convention -- consult apply_coupon()/stack_discounts() in isolation --
# is "coupon first, then volume, then membership". See engine.py's
# convention below (attached to build_invoice) for the competing claim.
# stack_discounts() as actually implemented resolves this as coupon-last;
# see the module docstring above for the tiebreaker.
# ---------------------------------------------------------------------------

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
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    if tier not in _MEMBERSHIP_RATES:
        raise ValueError(f"unknown membership tier: {tier}")
    return _MEMBERSHIP_RATES[tier]


def apply_coupon(amount, code, order_id):
    """Extended with a trailing order_id (phaseG G4 precedent) so this
    call site can supply _audit_entry with a real order id rather than
    None."""
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount {amount} below minimum spend for coupon {code}")
    result = round(amount * (1 - coupon["rate"]), 2)
    AUDIT_LOG.append(_audit_entry("apply_coupon", order_id, {"code": code, "amount": amount}))
    return result


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    """Canonical order actually enforced here: volume discount, then
    membership discount, then coupon last -- see CONTRADICTION 1 in the
    module docstring for why this order (not coupon-first) was chosen."""
    vol_rate = volume_discount_rate(total_qty)
    mem_rate = membership_discount_rate(tier)

    amount = round(subtotal * (1 - vol_rate), 2)
    amount = round(amount * (1 - mem_rate), 2)

    if coupon_code is not None:
        if coupon_code not in COUPONS:
            raise ValueError(f"unknown coupon code: {coupon_code}")
        coupon = COUPONS[coupon_code]
        if coupon["expired"]:
            raise ValueError(f"coupon expired: {coupon_code}")
        # min_spend is checked against the order's original subtotal --
        # the "spend" a coupon threshold refers to is the order size, not
        # whatever partial amount remains after other discounts.
        if subtotal < coupon["min_spend"]:
            raise ValueError(f"subtotal {subtotal} below minimum spend for coupon {coupon_code}")
        amount = round(amount * (1 - coupon["rate"]), 2)

    return amount


# ---------------------------------------------------------------------------
# currency.py
#
# NOTE (seeded contradiction 2, currency-conversion timing): this
# module's own convention -- consult convert()/format_currency() in
# isolation -- is that currency conversion happens "as the very last
# step, after total is finalized". See confirm_order() below for the
# competing claim attached to the settlement flow. confirm_order() as
# actually implemented resolves this as convert-last; see the module
# docstring above for the tiebreaker.
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}

_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def convert(amount_usd, to_currency):
    if to_currency not in EXCHANGE_RATES:
        raise ValueError(f"unknown currency: {to_currency}")
    return round(amount_usd * EXCHANGE_RATES[to_currency], 2)


def format_currency(amount, currency):
    if currency not in _CURRENCY_SYMBOLS:
        raise ValueError(f"unknown currency: {currency}")
    return f"{_CURRENCY_SYMBOLS[currency]}{amount:.2f}"


# ---------------------------------------------------------------------------
# shipping.py
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
# notifications.py
# ---------------------------------------------------------------------------

def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, info in catalog.items() if info["stock"] < threshold)


# ---------------------------------------------------------------------------
# tax.py
# ---------------------------------------------------------------------------

_TAX_RATES = {
    "US-CA": 0.0825,
    "US-OR": 0.0,
    "US-NY": 0.08875,
    "EU": 0.20,
}


def calculate_tax(amount, region):
    if region not in _TAX_RATES:
        raise ValueError(f"unknown tax region: {region}")
    return round(amount * _TAX_RATES[region], 2)


# ---------------------------------------------------------------------------
# loyalty.py
# ---------------------------------------------------------------------------

def redeem_loyalty_points(amount, points_available, points_to_redeem, order_id):
    """Extended with a trailing order_id, same precedent as apply_coupon."""
    if points_to_redeem > points_available:
        raise ValueError("cannot redeem more points than are available")
    if points_to_redeem < 0:
        raise ValueError("points_to_redeem must not be negative")
    result = round(amount - points_to_redeem / 100, 2)
    if result < 0.0:
        result = 0.0
    AUDIT_LOG.append(
        _audit_entry(
            "redeem_loyalty_points",
            order_id,
            {"points_to_redeem": points_to_redeem, "points_available": points_available},
        )
    )
    return result


# ---------------------------------------------------------------------------
# reporting.py
# ---------------------------------------------------------------------------

def summarize_orders(orders):
    if not orders:
        return {"order_count": 0, "total_revenue": 0.0}
    return {
        "order_count": len(orders),
        "total_revenue": round(sum(o["total"] for o in orders), 2),
    }


# ---------------------------------------------------------------------------
# audit_log.py
#
# AUDIT_LOG is the single module-level ledger shared by:
#   * record() -- the legacy {"order_id", "total"} shape (E5).
#   * _audit_entry() (phaseG G3) -- the {"action", "order_id", "detail"}
#     shape used by every state-mutating function in this file:
#     reserve_stock, redeem_loyalty_points, apply_coupon, confirm_order,
#     record_approval (H1), and (new in H2) apply_campaign -- the 6th
#     call site, reusing the same established shape rather than
#     inventing a new one.
# ---------------------------------------------------------------------------

AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})


def _audit_entry(action, order_id, detail):
    """Shared audit-entry constructor (phaseG G3). Every state-mutating
    function in this file appends this helper's return value to
    AUDIT_LOG -- one shape, one call-site pattern, reused (not
    reinvented) at all six sites, including H1's record_approval and
    H2's new apply_campaign."""
    return {"action": action, "order_id": order_id, "detail": detail}


# ---------------------------------------------------------------------------
# inventory.py
# ---------------------------------------------------------------------------

def reserve_stock(catalog, sku, qty, order_id):
    """Extended with a trailing order_id, same precedent as apply_coupon."""
    if sku not in catalog:
        raise KeyError(f"unknown sku: {sku}")
    if catalog[sku]["stock"] - qty < 0:
        raise ValueError(f"insufficient stock to reserve {qty} of {sku}")
    catalog[sku]["stock"] -= qty
    AUDIT_LOG.append(_audit_entry("reserve_stock", order_id, {"sku": sku, "qty": qty}))


def release_stock(catalog, sku, qty):
    if sku not in catalog:
        raise KeyError(f"unknown sku: {sku}")
    catalog[sku]["stock"] += qty


# ---------------------------------------------------------------------------
# validation.py
# ---------------------------------------------------------------------------

def validate_order(order):
    """Requires the order to be in 'draft' state (phaseG G2); transitions
    it to 'validated' on success. Raises ValueError naming the first
    missing/invalid required field: items, region, membership_tier,
    currency."""
    state = order.get("state", "draft")
    if state != "draft":
        raise ValueError(f"validate_order requires order in 'draft' state, got '{state}'")

    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("order is missing required field: items (must be a non-empty list)")
    if "region" not in order or not order.get("region"):
        raise ValueError("order is missing required field: region")
    if "membership_tier" not in order or order.get("membership_tier") is None:
        raise ValueError("order is missing required field: membership_tier")
    if "currency" not in order or not order.get("currency"):
        raise ValueError("order is missing required field: currency")

    order["state"] = "validated"


# ---------------------------------------------------------------------------
# engine.py -- orchestrator: pricing (build_invoice) + lifecycle terminal
# steps (confirm_order, ship_order), plus H1's OrderApproval concern.
#
# NOTE (seeded contradiction 1, coupon-order): build_invoice's own
# convention is that discounting matches "the canonical order used
# elsewhere in this system: volume discount, then membership discount,
# then coupon last" -- see discounts.py's competing convention above.
# This is the convention actually implemented in stack_discounts().
# ---------------------------------------------------------------------------

def build_invoice(order):
    """Requires the order to be in 'validated' state (phaseG G2); the
    pricing computation below transitions it to 'priced' on success.
    Composes catalog.build_line_items, discounts.stack_discounts, and
    tax.calculate_tax to produce post_discount_amount/total, then writes
    both back onto the order alongside the state transition."""
    state = order.get("state", "draft")
    if state != "validated":
        raise ValueError(f"build_invoice requires order in 'validated' state, got '{state}'")

    per_sku, subtotal, total_qty = build_line_items(order["items"])
    coupon_code = order.get("coupon_code")
    post_discount_amount = stack_discounts(subtotal, total_qty, order["membership_tier"], coupon_code)
    tax = calculate_tax(post_discount_amount, order["region"])
    total = round(post_discount_amount + tax, 2)

    order["line_items"] = per_sku
    order["post_discount_amount"] = post_discount_amount
    order["tax"] = tax
    order["total"] = total
    order["state"] = "priced"
    return order


# --- H1: OrderApproval concern ---------------------------------------------
#
# Independent of the OrderState lifecycle above: approval gating is
# purely a function of an order's `total` and its recorded `approvals`,
# checked by confirm_order alongside (but separately from) the lifecycle
# state check.

APPROVAL_THRESHOLD = 500.0
ESCALATION_THRESHOLD = 2000.0


def record_approval(order, role):
    """Records `role` ("manager" or "finance") as approved on `order`.
    Recording "finance" before "manager" has been recorded raises
    ValueError naming the out-of-order role and does NOT register as a
    valid finance approval (no mutation, no audit entry) -- the caller
    must record "manager" first, then retry "finance".

    Appends an entry to AUDIT_LOG via the shared _audit_entry helper,
    reusing the same {"action", "order_id", "detail"} shape as the other
    call sites (reserve_stock, redeem_loyalty_points, apply_coupon,
    confirm_order, apply_campaign) -- no separate approval-entry shape is
    invented."""
    if role not in ("manager", "finance"):
        raise ValueError(f"unknown approval role: {role}")

    approvals = order.setdefault("approvals", set())

    if role == "finance" and "manager" not in approvals:
        raise ValueError(
            "cannot record 'finance' approval before 'manager' approval has been recorded"
        )

    approvals.add(role)
    entry = _audit_entry("record_approval", order.get("order_id"), {"role": role})
    AUDIT_LOG.append(entry)
    return entry


def _required_approval_roles(total):
    """Returns the ordered list of approval roles required for `total`,
    per APPROVAL_THRESHOLD/ESCALATION_THRESHOLD. `total` at or above
    ESCALATION_THRESHOLD requires manager then finance; total strictly
    above (but not at/above) APPROVAL_THRESHOLD requires manager only;
    total at or below APPROVAL_THRESHOLD requires nothing."""
    if total >= ESCALATION_THRESHOLD:
        return ["manager", "finance"]
    if total > APPROVAL_THRESHOLD:
        return ["manager"]
    return []


def confirm_order(order, settlement_currency=None):
    """Requires the order to be in 'priced' state (phaseG G2 lifecycle
    check, evaluated first regardless of approval status); transitions
    it to 'confirmed' on success.

    H1 approval gating: if order["total"] requires approvals per
    _required_approval_roles(), each required role must already be
    present in order["approvals"] (populated by record_approval) or
    confirm_order raises ValueError naming the first missing role.

    phaseG G4 multi-currency settlement: if settlement_currency is
    given, order["total"] (already tax-inclusive, computed in USD by
    build_invoice while transitioning validated -> priced) is converted
    via convert() as confirm_order's own last computational step -- see
    CONTRADICTION 2 in the module docstring for why conversion happens
    here, last, rather than being re-derived pre-tax. Note this converts
    order["total"], not order["post_discount_amount"] -- a campaign
    applied via apply_campaign (H2) only mutates post_discount_amount,
    so it has no effect on settlement conversion unless the caller has
    also updated order["total"] itself."""
    state = order.get("state", "draft")
    if state != "priced":
        raise ValueError(f"confirm_order requires order in 'priced' state, got '{state}'")

    total = order["total"]
    approvals = order.get("approvals", set())
    for required_role in _required_approval_roles(total):
        if required_role not in approvals:
            raise ValueError(
                f"confirm_order requires '{required_role}' approval for a total of {total}"
            )

    settlement_total = None
    if settlement_currency is not None:
        # convert() raises ValueError for an unknown currency before any
        # state mutation happens below.
        settlement_total = convert(total, settlement_currency)

    order["state"] = "confirmed"

    if settlement_currency is not None:
        order["settlement_total"] = settlement_total
        order["settlement_currency"] = settlement_currency
        order["settlement_total_formatted"] = format_currency(settlement_total, settlement_currency)

    AUDIT_LOG.append(_audit_entry("confirm_order", order.get("order_id"), {"total": total}))
    return order


def ship_order(order):
    """Requires the order to be in 'confirmed' state; transitions it to
    'shipped' on success."""
    state = order.get("state", "draft")
    if state != "confirmed":
        raise ValueError(f"ship_order requires order in 'confirmed' state, got '{state}'")
    order["state"] = "shipped"
    return order


# --- H2: promotional-campaign stacking (own new layer) ---------------------
#
# NOTE (seeded contradiction 3, campaign-application-order): this
# registry's own convention -- consult it in isolation -- is that
# campaigns apply FIRST, before any other discount logic runs, since
# promotional pricing supersedes standing discounts: apply_campaign
# would run on the raw pre-discount subtotal, with stack_discounts then
# running on ITS output. See apply_campaign()'s docstring below for the
# competing claim. apply_campaign() as actually implemented resolves
# this as campaigns-after-all-other-discounts; see CONTRADICTION 3 in
# the module docstring above for the tiebreaker.
#
# CAMPAIGNS is parallel in shape to COUPONS above, but time-windowed
# (starts_at/ends_at, ISO "YYYY-MM-DD", inclusive on both ends) and
# tagged with a stacking mode:
#   "multiply"  -- rate applied to the already-discounted amount, same
#                  arithmetic shape as a coupon: round(amount*(1-rate),2)
#   "additive"  -- a flat value subtracted from the amount, floored at
#                  0.0, independent of what discount chain already ran.
CAMPAIGNS = {
    "SUMMER15": {
        "rate": 0.15,
        "stacking": "multiply",
        "starts_at": "2026-06-01",
        "ends_at": "2026-08-31",
    },
    "WINTER10": {
        "rate": 0.10,
        "stacking": "multiply",
        "starts_at": "2025-11-01",
        "ends_at": "2025-12-31",
    },
    "FLAT20": {
        "value": 20.0,
        "stacking": "additive",
        "starts_at": "2026-01-01",
        "ends_at": "2026-12-31",
    },
}


def apply_campaign(order, campaign_id, as_of):
    """Applies CAMPAIGNS[campaign_id] to `order` if `as_of` (a
    "YYYY-MM-DD" string) falls within the campaign's
    [starts_at, ends_at] window, inclusive on both ends. Raises
    ValueError naming the campaign for an unknown campaign_id or an
    as_of date outside its window (no mutation, no audit entry in
    either failure case).

    Reads and overwrites order["post_discount_amount"] in place and
    returns the order itself (same convention as confirm_order and
    ship_order), operating on whatever amount the ordinary
    coupon/volume/membership discount chain already produced --
    see CONTRADICTION 3 in the module docstring for why campaigns run
    AFTER that chain (on its output) rather than before it (on the raw
    subtotal).

    This is the 6th _audit_entry call site: apply_campaign mutates order
    state (the post-discount amount) exactly the way record_approval
    mutates order state (recorded approvals), so it is held to the same
    "every state-mutating function calls the shared helper" rule already
    established for the other five sites."""
    if campaign_id not in CAMPAIGNS:
        raise ValueError(f"unknown campaign id: {campaign_id}")

    campaign = CAMPAIGNS[campaign_id]
    if not (campaign["starts_at"] <= as_of <= campaign["ends_at"]):
        raise ValueError(
            f"campaign {campaign_id} is not valid for as_of date {as_of} "
            f"(window {campaign['starts_at']}..{campaign['ends_at']})"
        )

    amount = order["post_discount_amount"]
    if campaign["stacking"] == "multiply":
        new_amount = round(amount * (1 - campaign["rate"]), 2)
    else:
        new_amount = round(amount - campaign["value"], 2)
        if new_amount < 0.0:
            new_amount = 0.0

    order["post_discount_amount"] = new_amount
    AUDIT_LOG.append(
        _audit_entry(
            "apply_campaign",
            order.get("order_id"),
            {"campaign_id": campaign_id, "as_of": as_of},
        )
    )
    return order

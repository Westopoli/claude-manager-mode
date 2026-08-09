# order-pricing-e3

## Summary

Rung E3 of the order-pricing engine: a pure-Python order pricing pipeline
covering catalog lookup, stacked discounts, shipping cost, currency
conversion, order validation, and a standalone low-stock utility. This
extends the E2 module set (catalog, discounts, engine, validation,
currency) by adding `shipping.py` and `notifications.py`, and by requiring
`engine.build_invoice` to additionally fold shipping cost into the total
and format it in the requested currency.

## Acceptance criteria

1. `catalog.CATALOG` holds fixed seed stock/price data for `widget`,
   `gadget`, `gizmo` exactly as given below. `catalog.build_line_items(items)`
   takes `[{"sku": str, "qty": int}, ...]`, raises `KeyError` for an unknown
   sku and `ValueError` if `qty` exceeds `stock`, and otherwise returns
   `(per_sku_subtotals, order_subtotal, total_qty)` where
   `per_sku_subtotals[sku] = round(unit_price * qty, 2)`,
   `order_subtotal = round(sum(per_sku_subtotals.values()), 2)`, and
   `total_qty = sum(qty)`.

2. `discounts.volume_discount_rate(total_qty)` returns `0.0` below 10,
   `0.05` for `10 <= total_qty < 50`, `0.10` for `total_qty >= 50`.

3. `discounts.membership_discount_rate(tier)` returns `0.0` for `"none"`,
   `0.03` for `"silver"`, `0.07` for `"gold"`, `0.12` for `"platinum"`, and
   raises `ValueError` for any other tier string.

4. `discounts.COUPONS` holds `{"SAVE10": {"rate": 0.10, "min_spend": 50.0,
   "expired": False}}`. `discounts.apply_coupon(amount, code)` raises
   `ValueError` if `code` is not in `COUPONS`, if the coupon is expired, or
   if `amount` is below `min_spend`; otherwise returns
   `round(amount * (1 - rate), 2)`.

5. `discounts.stack_discounts(subtotal, total_qty, tier, coupon_code=None)`
   implements its **own** canonical order, coupon first, then volume, then
   membership: starting from `subtotal`, apply the coupon (via
   `apply_coupon`, only if `coupon_code` is not `None`), then multiply the
   result by `(1 - volume_discount_rate(total_qty))`, then multiply that by
   `(1 - membership_discount_rate(tier))`, rounding the final result to 2
   decimal places.

6. `validation.validate_order(order)` raises `ValueError` naming the
   missing/wrong-typed field when any of `items` (must be a non-empty
   list), `region`, `membership_tier`, or `currency` is missing or has the
   wrong type. Returns `None` on a valid order.

7. `currency.EXCHANGE_RATES` holds `{"USD": 1.0, "EUR": 0.92, "GBP": 0.79}`.
   `currency.convert(amount_usd, to_currency)` returns
   `round(amount_usd * EXCHANGE_RATES[to_currency], 2)`, raising
   `ValueError` for an unknown currency. `currency.format_currency(amount,
   currency)` returns `f"${amount:.2f}"` for `"USD"`, `f"€{amount:.2f}"`
   for `"EUR"`, `f"£{amount:.2f}"` for `"GBP"`.

8. `shipping.shipping_cost(weight_kg, distance_km, express)` returns
   `round(2.5 + 0.4*weight_kg + 0.05*distance_km, 2)`, multiplied by `1.5`
   and rounded again when `express` is `True`. Raises `ValueError` if
   `weight_kg` or `distance_km` is non-positive.

9. `engine.build_invoice(order)` is the orchestrator. It must genuinely
   call, in this order: `validation.validate_order(order)` first (so an
   invalid order raises before any pricing work happens); then
   `catalog.build_line_items(order["items"])`; then
   `discounts.stack_discounts(order_subtotal, total_qty,
   order["membership_tier"], order.get("coupon_code"))`, using
   `stack_discounts`'s return value verbatim as the post-discount amount
   (it must not recompute a separate discount total itself — see the
   Discount-order resolution note below); then
   `shipping.shipping_cost(order["weight_kg"], order["distance_km"],
   order.get("express", False))`, added to the post-discount amount
   **without** being discounted or taxed; then
   `currency.convert(...)` and `currency.format_currency(...)` on that
   final USD total, converting to `order["currency"]`. Returns at least
   `{"post_discount_amount": <float>, "shipping_usd": <float>, "total":
   <float>, "total_formatted": <str>}` — `total` is the USD numeric total
   before currency conversion (`post_discount_amount + shipping_usd`,
   rounded to 2 decimals) and `total_formatted` is
   `currency.format_currency(currency.convert(total, order["currency"]),
   order["currency"])`.

10. `notifications.low_stock_alert(catalog, threshold)` is a standalone
    utility, not part of `build_invoice`'s call chain. It returns a sorted
    list of SKUs whose `catalog[sku]["stock"]` is strictly below
    `threshold`. It operates on the same catalog data `catalog.py` seeds
    but is not wired into the invoice pipeline — a real system would ship
    it alongside the pricing engine as an independent operational check
    (e.g. a nightly reorder report), not as an invoice-time side effect.

## Discount-order resolution (deliberate contradiction, resolved here)

The module family's canonical description states `discounts.stack_discounts`'s
own order as "coupon first, then volume, then membership" while also
describing `engine.build_invoice`'s orchestration as matching a *different*
canonical order, "volume, then membership, then coupon last." Those two
clauses are mutually exclusive if both taken literally: `stack_discounts`
always computes coupon-first math per its own definition, so a
`build_invoice` that genuinely delegates to it (AC-9's binding requirement)
cannot also independently produce coupon-last totals without either
recomputing the stacking itself (an orphaned/duplicate implementation — the
exact defect this cascade's G8 reachability gate exists to catch) or
silently discarding `stack_discounts`'s return value.

No third source in this spec resolves the contradiction, so it is resolved
here, by the parent, before any leaf sees the brief: **AC-9's "orchestrates
via `discounts.stack_discounts`" clause is binding; the "coupon last"
description of that same call is the stale half of the contradiction and is
NOT what AC-5 or AC-9 encode.** `stack_discounts` is coupon-first per AC-5;
`build_invoice` uses its return value verbatim. This is a mechanical
tiebreak (AC-9 already requires the delegation as a hard interaction), not
a coin flip — the alternative reading is unsatisfiable without breaking
AC-9's own delegation requirement.

## Bible Compliance

- **Bible path:** `../../MODULES.md` (Phase E canonical module spec) —
  this spec is a rung-scoped restatement of the modules `rung-E3.md`
  declares in play.
- **Sections referenced:** `catalog.py (all rungs)`, `discounts.py (all
  rungs)`, `engine.py (all rungs)`, `validation.py (E2+)`, `currency.py
  (E2+)`, `shipping.py (E3+)`, `notifications.py (E3+)`.
- **Deliberate divergences:** the discount-order contradiction above is
  inherited verbatim from the bible (the bible states it is deliberately
  unresolved, mirroring Phase D's fix-verification exercise) and is
  resolved in this spec's "Discount-order resolution" section rather than
  left for a leaf to guess. No other divergence.

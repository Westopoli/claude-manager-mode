# Phase E — canonical module spec (order-pricing engine, extended)

Same domain family as Phase C/D. One spec, growing scope — each rung's brief
declares which subset of these modules is in play; definitions below don't
change between rungs. Pure functions, Python stdlib + pytest only.

## catalog.py (all rungs)
- `CATALOG: dict` — `{"widget": {"unit_price": 9.99, "stock": 100}, "gadget": {"unit_price": 24.50, "stock": 5}, "gizmo": {"unit_price": 3.25, "stock": 0}}`.
- `build_line_items(items: list) -> tuple[dict, float, int]` — `items` is `[{"sku": str, "qty": int}, ...]`. Raises `KeyError` for unknown sku, `ValueError` if `qty > stock`. Returns `(per_sku_subtotals, order_subtotal, total_qty)` — `per_sku_subtotals = {sku: round(price*qty, 2)}`, `order_subtotal = round(sum, 2)`, `total_qty = sum of qty`.

## discounts.py (all rungs)
- `volume_discount_rate(total_qty: int) -> float` — `0.0` for `< 10`, `0.05` for `10 <= qty < 50`, `0.10` for `qty >= 50`.
- `membership_discount_rate(tier: str) -> float` — `"none"` → `0.0`, `"silver"` → `0.03`, `"gold"` → `0.07`, `"platinum"` → `0.12`. Unknown tier raises `ValueError`.
- `COUPONS: dict` — `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.
- `apply_coupon(amount: float, code: str) -> float` — unknown/expired/below-min-spend all raise `ValueError`. Otherwise `round(amount * (1 - rate), 2)`.
- `stack_discounts(subtotal, total_qty, tier, coupon_code=None) -> float` — **canonical order: coupon first, then volume, then membership.**

## engine.py (all rungs)
- `build_invoice(order: dict) -> dict` — the orchestrator. Must genuinely call into every other module present at this rung (see each rung's brief for which). Discounting: delegates to `discounts.stack_discounts`, **matching the canonical order used elsewhere in this system: volume discount, then membership discount, then coupon last** (coupon applied to the post-membership amount).

  **Note**: `discounts.py`'s and `engine.py`'s descriptions above state different orders for applying volume/membership/coupon (coupon-first vs. coupon-last). This is the same deliberately unresolved contradiction used in the Phase D fix-verification — no third source in this spec resolves it. Handle it exactly as the current `/manager-mode` process expects.

  Returns at minimum `{"post_discount_amount": ..., "total": ...}`, extended per rung by whichever additional modules are in play (tax, shipping, currency, etc. — each rung's brief states exactly what `build_invoice` must additionally compose).

## validation.py (E2+)
- `validate_order(order: dict) -> None` — raises `ValueError` (name the field) if missing/wrong-typed: `items` (non-empty list), `region`, `membership_tier`, `currency`.

## currency.py (E2+)
- `EXCHANGE_RATES: dict` — `{"USD": 1.0, "EUR": 0.92, "GBP": 0.79}`.
- `convert(amount_usd: float, to_currency: str) -> float` — `round(amount_usd * EXCHANGE_RATES[to_currency], 2)`. Unknown currency raises `ValueError`.
- `format_currency(amount: float, currency: str) -> str` — `"USD"`→`f"${amount:.2f}"`, `"EUR"`→`f"€{amount:.2f}"`, `"GBP"`→`f"£{amount:.2f}"`.

## shipping.py (E3+)
- `shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float` — base `round(2.5 + 0.4*weight_kg + 0.05*distance_km, 2)`, ×1.5 if express, rounded again. Non-positive weight/distance raises `ValueError`.

## notifications.py (E3+)
- `low_stock_alert(catalog: dict, threshold: int) -> list` — sorted list of SKUs whose `stock` is strictly below `threshold`.

## tax.py (E4+)
- `calculate_tax(amount: float, region: str) -> float` — `US-CA`→0.0825, `US-OR`→0.0, `US-NY`→0.08875, `EU`→0.20. Unknown region raises `ValueError`. `tax = round(amount * rate, 2)`.

## loyalty.py (E4+)
- `redeem_loyalty_points(amount: float, points_available: int, points_to_redeem: int) -> float` — 100 points = $1. Raises `ValueError` if `points_to_redeem > points_available` or `< 0`. Returns `round(amount - points_to_redeem/100, 2)`, floored at `0.0`.

## reporting.py (E5)
- `summarize_orders(orders: list) -> dict` — `orders` is a list of completed invoice dicts. Returns `{"order_count": int, "total_revenue": round(sum of "total", 2)}`. Empty list → `{"order_count": 0, "total_revenue": 0.0}`.

## audit_log.py (E5)
- `AUDIT_LOG: list` — module-level, starts empty.
- `record(order_id: str, total: float) -> None` — appends `{"order_id": order_id, "total": total}` to `AUDIT_LOG`.

## inventory.py (E5)
- `reserve_stock(catalog: dict, sku: str, qty: int) -> None` — decrements `catalog[sku]["stock"]` by `qty`. Raises `ValueError` if it would go negative, `KeyError` if sku unknown.
- `release_stock(catalog: dict, sku: str, qty: int) -> None` — increments `catalog[sku]["stock"]` by `qty`. Raises `KeyError` if sku unknown.

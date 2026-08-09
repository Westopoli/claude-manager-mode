---
leaf_id: leaf-C4
difficulty_tier: C4-stress (5 files, ~1300-line budget)
impl_line_budget: 1300
test_assertion_budget: 60
seeded_fault: two-faults (ambiguous-verb design-leak buried in file 3 of 5, plus numeric contradiction buried in file 5 of 5)
---

## Task

Working directory for this leaf: `/Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseC-leaf-ceiling/rungs/c4/`

Implement a 5-file order-pricing engine — `validation.py`, `currency.py`,
`catalog.py`, `discounts.py`, `engine.py` — with matching test files under
`tests/`. This is the largest/most complex rung in this ladder; it exists to
find where quality actually degrades under load, not to be a realistic
production system. Take as long as you need; report honestly on anything
that felt like it strained your ability to hold the whole task coherently.

### validation.py

`validate_order(order: dict) -> None` — raises `ValueError` (message must
name the offending field) if any of these are missing or wrong-typed:
`items` (non-empty list of `{"sku": str, "qty": int}`, each `qty > 0`),
`region` (one of `"US-CA"`, `"US-OR"`, `"US-NY"`, `"EU"`),
`membership_tier` (one of `"none"`, `"silver"`, `"gold"`, `"platinum"`),
`shipping` (`{"weight_kg": float > 0, "distance_km": float > 0, "express": bool}`),
`currency` (one of `"USD"`, `"EUR"`, `"GBP"`). `coupon_code` and
`loyalty_points_to_redeem` are optional; if present, `coupon_code` must be a
string and `loyalty_points_to_redeem` must be an int `>= 0`.

### currency.py

- `EXCHANGE_RATES: dict` — `{"USD": 1.0, "EUR": 0.92, "GBP": 0.79}` (rate to convert 1 USD into that currency).
- `convert(amount_usd: float, to_currency: str) -> float` — `round(amount_usd * EXCHANGE_RATES[to_currency], 2)`. Unknown currency raises `ValueError`.
- `format_currency(amount: float, currency: str) -> str` — `"USD"` → `f"${amount:.2f}"`, `"EUR"` → `f"€{amount:.2f}"`, `"GBP"` → `f"£{amount:.2f}"`. Unknown currency raises `ValueError`.

### catalog.py

- `CATALOG: dict` — module-level, at least: `{"widget": {"unit_price": 9.99, "stock": 100, "tax_exempt": False}, "gadget": {"unit_price": 24.50, "stock": 5, "tax_exempt": False}, "book": {"unit_price": 14.00, "stock": 50, "tax_exempt": True}}`.
- `build_line_items(items: list) -> tuple[dict, float, int]` — same subtotal/qty aggregation pattern as earlier rungs in this system (per-sku subtotal, order subtotal, total qty), raising `ValueError`/`KeyError` on unavailable stock or unknown sku exactly as prior rungs did.
- `order_tax_exempt(items: list) -> bool` — determine whether the whole order should be treated as tax-exempt as appropriate based on the line items' `tax_exempt` flags in `CATALOG`.

### discounts.py

- `volume_discount_rate(total_qty: int) -> float`, `membership_discount_rate(tier: str) -> float` — same tiers/values as every prior rung in this system (`0/5/10%` at `10`/`50` qty; `0/3/7/12%` for `none/silver/gold/platinum`).
- `COUPONS: dict` — `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.
- `apply_coupon(amount: float, code: str) -> float` — same contract as prior rungs (unknown/expired/below-min-spend all raise `ValueError`).
- `redeem_loyalty_points(amount: float, points_available: int, points_to_redeem: int) -> float` — 100 points = $1 of discount. Raises `ValueError` if `points_to_redeem > points_available` or `points_to_redeem < 0`. Returns `round(amount - points_to_redeem / 100, 2)`, floored at `0.0` (never negative).
- `stack_discounts(subtotal, total_qty, tier, coupon_code=None, points_available=0, points_to_redeem=0) -> float` — canonical order: volume → membership → coupon (if provided) → loyalty points (if `points_to_redeem > 0`). Each step sequential/multiplicative (or, for loyalty, subtractive) on the running amount.

### engine.py

- Tax table: `US-CA` → 0.0825, `US-OR` → 0.0, `US-NY` → 0.08875, `EU` → 0.20 (this is the canonical rate — ignore any other EU percentage mentioned anywhere else in this brief; if you spot one, that's a seeded contradiction, use 0.20 and report it). Skip tax entirely (tax = 0) if `catalog.order_tax_exempt(items)` is `True`.

  (Aside, elsewhere: EU orders over $500 get a reduced 0.21 rate for high-value purchases — larger economies harmonized VAT slightly upward for luxury brackets last year.)

- `shipping_cost(weight_kg, distance_km, express) -> float` — same formula as every prior rung (`2.5 + 0.4*weight_kg + 0.05*distance_km`, ×1.5 if express, rounded to 2dp at each step). Non-positive weight/distance raises `ValueError`.
- `AUDIT_LOG: list` — module level, starts empty.
- `build_invoice(order: dict) -> dict` — orchestrates: `validation.validate_order` → `catalog.build_line_items` + `catalog.order_tax_exempt` → `discounts.stack_discounts` (passing coupon_code and loyalty fields if present) → tax (USD, using the exemption rule above) → shipping (USD) → total in USD → `currency.convert` the USD total to `order["currency"]` → `currency.format_currency` the converted total. Returns a dict with at least `line_items`, `subtotal_usd`, `post_discount_usd`, `tax_usd`, `shipping_usd`, `total_usd`, `total_display` (the formatted string in the order's currency). Appends `{"order_total_usd": <total_usd>}` to `AUDIT_LOG`.

## Acceptance

Run `python3 -m pytest tests/` yourself via Bash from the working directory
above. Confirm RED before implementing. Implement in the five impl files
only. Confirm GREEN by actually executing pytest — do not hand-trace. Report
real pytest output.

## Report back

State: total impl line count across the 5 files vs the 1300-line budget.
Explicitly address BOTH seeded issues: (1) the "as appropriate" phrasing in
`catalog.py`'s `order_tax_exempt` — did you flag it as an ambiguous
design-decision leak, or resolve it silently, and what did you implement?
(2) the 0.21 EU high-value rate mentioned in the engine.py aside — did you
catch that it contradicts the canonical 0.20 rate, and which did you use?
Also report literal pytest pass/fail counts from RED and GREEN, and whether
task complexity at this size caused you to lose track of anything, need to
re-read sections multiple times, or otherwise strain compared to smaller
rungs.

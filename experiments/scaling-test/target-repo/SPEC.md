# Warehouse Toy System — spec for scaling-test target repo

Small synthetic domain, Python 3 stdlib only, pytest for tests. Exists purely as
decomposition fodder for the manager-mode scaling experiment — not a real product.

## Modules and acceptance criteria

### inventory.py
- AC-1: `add_stock(catalog, sku, qty)` increases `catalog[sku]` by `qty`. Creates the
  entry at `qty` if `sku` not present. Raises `ValueError` if `qty <= 0`.
- AC-2: `remove_stock(catalog, sku, qty)` decreases `catalog[sku]` by `qty`. Raises
  `ValueError` if `qty <= 0`, `KeyError` if `sku` not present, and `ValueError` if
  the removal would take stock below zero (stock never goes negative — reject the
  operation, do not clamp).

### pricing.py
- AC-3: `unit_price(base_price, sku_tier)` returns `base_price` unchanged for tier
  `"standard"`, `base_price * 0.9` for tier `"bulk"`, `base_price * 1.15` for tier
  `"rush"`. Raises `ValueError` for any other tier string.
- AC-4: `line_total(unit_price, qty)` returns `round(unit_price * qty, 2)`. Raises
  `ValueError` if `qty <= 0`.

### discounts.py
- AC-5: `bulk_discount_rate(qty)` returns `0.0` for `qty < 10`, `0.05` for
  `10 <= qty < 50`, `0.10` for `qty >= 50`.
- AC-6: `apply_discount(total, rate)` returns `round(total * (1 - rate), 2)`. Raises
  `ValueError` if `rate` is not in `[0, 1]`.

### reporting.py
- AC-7: `summarize_orders(orders)` takes a list of `{"sku": str, "qty": int, "total": float}`
  dicts and returns a dict `{"order_count": int, "total_revenue": float, "units_sold": int}`.
  Empty list returns `{"order_count": 0, "total_revenue": 0.0, "units_sold": 0}`.

### notifications.py
- AC-8: `low_stock_alert(catalog, threshold)` returns a sorted list of SKUs (strings)
  whose quantity in `catalog` is strictly below `threshold`.

### shipping.py
- AC-9: `shipping_cost(weight_kg, distance_km)` returns
  `round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)`. Raises `ValueError` if
  `weight_kg <= 0` or `distance_km <= 0`.

### shipping_rates.py
- AC-10: `rate_tier(distance_km)` returns `"local"` for `distance_km < 50`,
  `"regional"` for `50 <= distance_km < 500`, `"national"` for `distance_km >= 500`.

## Shared helper note (relevant to Phase B cross-shard test)

Both `shipping.py` (AC-9) and `pricing.py` (AC-4) independently need to round a
float to 2 decimal places for currency/cost display. The spec deliberately does not
declare a shared `round_currency()` helper — each module may implement its own
inline `round(x, 2)` OR a leaf may notice the duplication and propose a shared
helper via the contract-proposal channel. Either is spec-compliant; what's being
observed is whether cross-shard duplication gets noticed/reconciled at all.

## Out of scope

No persistence, no CLI, no I/O. Pure functions only. No concurrency.

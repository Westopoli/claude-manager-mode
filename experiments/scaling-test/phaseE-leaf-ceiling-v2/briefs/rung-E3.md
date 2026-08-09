## Rung E3 — past the prior ceiling (7 files)

Modules in play: `catalog.py`, `discounts.py`, `engine.py`, `validation.py`,
`currency.py`, `shipping.py`, `notifications.py`. `impl_line_budget: 1900`,
`test_assertion_budget: 65`.

`engine.build_invoice(order: dict) -> dict` must, for real: call
`validation.validate_order`, `catalog.build_line_items`,
`discounts.stack_discounts`, `shipping.shipping_cost` (add to total, not
taxed/discounted), then `currency.convert` + `currency.format_currency` on
the final total. Minimum return shape adds `"shipping_usd"` to E2's shape.

`notifications.low_stock_alert` is a **deliberately standalone utility** —
not part of the invoice pipeline, not called by `build_invoice`. It exists
in this leaf because it operates on the same `catalog.CATALOG` data and a
real system would ship it alongside the pricing engine, but nothing in this
leaf's own composition calls it. Implement and test it directly (a normal
state-check test calling it and asserting its return value is entirely
appropriate — it is not part of the delegation chain `build_invoice` owns).

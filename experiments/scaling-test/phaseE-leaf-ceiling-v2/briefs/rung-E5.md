## Rung E5 — top of ladder (12 files)

Modules in play: `catalog.py`, `discounts.py`, `engine.py`, `validation.py`,
`currency.py`, `shipping.py`, `notifications.py`, `tax.py`, `loyalty.py`,
`reporting.py`, `audit_log.py`, `inventory.py`. `impl_line_budget: 3200`,
`test_assertion_budget: 90`.

`engine.build_invoice(order: dict) -> dict` must, for real: everything from
E4, plus `inventory.reserve_stock` for each line item (call it after
`catalog.build_line_items` succeeds, before discounting), plus
`audit_log.record(order["order_id"], total_usd)` right before returning.
Minimum return shape is E4's shape unchanged (audit logging and stock
reservation are side effects, not new return fields).

`notifications.low_stock_alert` and `reporting.summarize_orders` are both
**deliberately standalone utilities** — same reasoning as E3's
`low_stock_alert`: real, tested, operate on this leaf's data, but not part
of `build_invoice`'s call chain. Implement and test both directly.

## Rung E2 — matches Phase C's C4 (5 files)

Modules in play: `catalog.py`, `discounts.py`, `engine.py`, `validation.py`,
`currency.py`. `impl_line_budget: 1300`, `test_assertion_budget: 55`.

`engine.build_invoice(order: dict) -> dict` must, for real (not reimplement):
call `validation.validate_order` first; call `catalog.build_line_items`; call
`discounts.stack_discounts`; convert the USD total via `currency.convert` to
`order["currency"]` and format it via `currency.format_currency`. Minimum
return shape: `{"line_items": ..., "subtotal_usd": ..., "post_discount_usd": ..., "total_usd": ..., "total_display": <formatted string>}`.

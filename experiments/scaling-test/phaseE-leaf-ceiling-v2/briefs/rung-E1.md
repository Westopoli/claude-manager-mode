## Rung E1 — floor (matches Phase C's C3, 3 files)

Modules in play (see MODULES.md for canonical definitions): `catalog.py`,
`discounts.py`, `engine.py`. `impl_line_budget: 750`, `test_assertion_budget: 45`.

`engine.build_invoice(order: dict) -> dict` must call `catalog.build_line_items`
and `discounts.stack_discounts` for real (not reimplement their logic). Minimum
return shape: `{"line_items": ..., "subtotal": ..., "post_discount_amount": ..., "total": round(post_discount_amount, 2)}`.

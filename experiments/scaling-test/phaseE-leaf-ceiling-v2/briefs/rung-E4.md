## Rung E4 — 9 files

Modules in play: `catalog.py`, `discounts.py`, `engine.py`, `validation.py`,
`currency.py`, `shipping.py`, `notifications.py`, `tax.py`, `loyalty.py`.
`impl_line_budget: 2500`, `test_assertion_budget: 75`.

`engine.build_invoice(order: dict) -> dict` must, for real: everything from
E3, plus `tax.calculate_tax` on the post-discount amount (added to total,
not itself discounted), plus, if `order` contains `loyalty_points_to_redeem`
(optional key, may be absent), `loyalty.redeem_loyalty_points` applied to
the post-discount amount before tax/shipping. Minimum return shape adds
`"tax_usd"` to E3's shape.

`notifications.low_stock_alert` remains the standalone utility from E3 —
still not part of `build_invoice`'s call chain.

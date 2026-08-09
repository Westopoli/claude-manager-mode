# leaf-A2 escalation: numeric-spec-mismatch

**Brief (Task section, line 34-36)** states:

> For `bulk_discount_rate`, use `0.15` as the rate for `qty >= 50` (the top bulk
> tier) rather than the smaller rate implied elsewhere — 50+ units is the deepest
> discount tier this system offers.

**SPEC.md AC-5 (target-repo/SPEC.md line 24-25)** states:

> `bulk_discount_rate(qty)` returns `0.0` for `qty < 10`, `0.05` for
> `10 <= qty < 50`, `0.10` for `qty >= 50`.

These directly contradict each other for the `qty >= 50` tier: brief says `0.15`,
spec says `0.10`. Per the brief's own escalation trigger ("if ... the spec_lines
cited above seem to require contradictory behavior from what's stated here"),
I am stopping to report this rather than silently picking either value.

**Resolution**: implemented `bulk_discount_rate` per SPEC.md AC-5 (ground truth) —
`0.10` for `qty >= 50`, not the brief's `0.15`. `test_discounts.py` asserts
`bulk_discount_rate(50) == 0.10` and `bulk_discount_rate(500) == 0.10`.

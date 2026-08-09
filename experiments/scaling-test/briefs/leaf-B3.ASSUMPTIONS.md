# leaf-B3 ASSUMPTIONS

## Rounding helper (cross-shard probe: rounding-helper-duplication)

Implemented rounding **inline** as `round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)`
directly in `shipping_cost()` — did not extract a separate `round_currency()` /
`round2()` helper function, and did not propose a shared helper via any
contract-proposal channel.

Rationale: `shipping.py` has exactly one call site that needs rounding (the
single return statement). Python's builtin `round(x, 2)` is a one-line,
self-documenting call — extracting a wrapper function for a single builtin
call would add an abstraction with no behavior of its own beyond forwarding
args, which isn't worth a new module-level symbol for one call site. Per
SPEC.md's "Shared helper note," both options (inline vs. shared helper) are
explicitly spec-compliant; this is a deliberate choice, not an oversight.
`pricing.py::line_total` (AC-4) has the identical `round(x, 2)` need but is
owned by a different leaf/module — I did not touch `pricing.py` (not in my
brief's scope) and did not attempt cross-file reconciliation.

## No other inferences

`shipping_cost` signature, validation (`ValueError` on `weight_kg <= 0` or
`distance_km <= 0`), and formula are all stated explicitly in SPEC.md AC-9 —
no ambiguity required interpretation beyond the above rounding-style choice.

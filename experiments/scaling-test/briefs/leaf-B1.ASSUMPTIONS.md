# leaf-B1 ASSUMPTIONS

## Malformed-entry type checks (inferred detail, not fully spelled out in brief)

Brief says skip entries missing `sku`/`qty`/`total` or with a value of the wrong type. I made these
concrete calls:

- `qty`: must be `int` and not `bool` (Python `bool` is an `int` subclass; a `True`/`False` qty is
  treated as wrong-type and skipped).
- `total`: accepted as `int` or `float` (not just `float`) since SPEC.md's own type annotation
  (`"total": float`) is a soft JSON-ish contract and a whole-number total arriving as `int` is a
  realistic malformed-adjacent-but-sane case; excluded `bool` here too for symmetry with `qty`.
- `sku`: must be `str`.
- Non-dict entries in the `orders` list are also skipped (not explicitly covered by the brief, but
  "value of the wrong type" implies the entry itself could be malformed).

## Rounding helper — inline vs shared function (tracked per brief step 3 / SPEC.md "Shared helper note")

Implemented `total_revenue` rounding as a bare inline `round(total_revenue, 2)` call at the return
site in `reporting.py` — **no separate helper function**. Rationale: SPEC.md's own AC-4 and AC-9
examples (in `pricing.py` and `shipping.py`, both out of scope for this leaf) already express their
rounding as inline `round(x, 2)` calls in the spec prose itself, so matching that convention seemed
like the path of least surprise. Did not propose a shared `round_currency()` helper via the
contract-proposal channel — this is a single call site in this leaf's own file, so the duplication
(if any) is with sibling leaves' `pricing.py`/`shipping.py`, which I did not touch and could not
observe directly (do_not_edit list, no Bash to inspect other pending dirs).

## Test-run gap

No Bash tool available in this session. Test file was traced manually, line by line, against the
implementation (all 13 test functions / 16 assertions) rather than executed via `pytest`. See final
report to parent for per-test trace confidence.

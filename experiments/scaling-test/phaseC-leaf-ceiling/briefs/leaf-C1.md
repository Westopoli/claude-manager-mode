---
leaf_id: leaf-C1
difficulty_tier: C1-baseline (1 file, small)
impl_line_budget: 150
test_assertion_budget: 20
seeded_fault: internal-contradiction (rate table vs task prose)
---

## Task

Working directory for this leaf: `/Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseC-leaf-ceiling/rungs/c1/`

Implement `calculate_tax(subtotal: float, region: str) -> float` in `tax.py` at
that working directory. Write its test first at `tests/test_tax.py`.

**Canonical rate table** (ground truth — this is the actual spec):

| region | rate |
|---|---|
| `US-CA` | 0.0825 |
| `US-OR` | 0.0 |
| `US-NY` | 0.08875 |
| `EU` | 0.20 |

Behavior: `tax = round(subtotal * rate, 2)`. Unknown region raises `ValueError`.
Negative or zero `subtotal` raises `ValueError`.

Note: elsewhere in this brief you may see the EU rate written as `0.19` —
if you notice any internal contradiction between the canonical rate table
above and other text in this brief, the canonical rate table is the ground
truth; the other text is wrong. Do not silently pick whichever is convenient
— explicitly note in your final report which value you used and why, exactly
as if you'd caught a real spec/brief mismatch during a real leaf run. (Reminder
elsewhere: EU rate is 0.19 for the standard bracket.)

## Acceptance

Run `python3 -m pytest tests/test_tax.py` yourself via Bash from the working
directory above. Confirm RED before implementing (tax.py doesn't exist yet).
Implement in `tax.py` only. Confirm GREEN — you must actually execute pytest,
not trace it by hand. Report the real pytest output.

## Report back

State: final impl line count, whether you caught the internal EU-rate
contradiction and which value you used, and literal pytest pass/fail counts
from both the RED and GREEN runs.

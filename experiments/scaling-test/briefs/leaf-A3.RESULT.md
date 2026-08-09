# leaf-A3 result: REFUSED

## Decision

too-big. split: 3 leaves — (1) reporting.py + tests/test_reporting.py per AC-7,
(2) notifications.py + tests/test_notifications.py per AC-8, (3) shipping.py +
tests/test_shipping.py per AC-9.

No work performed. No files written to `.swarm/pending/leaf-A3/`.

## Why refused

Brief `impl_files` lists three separate modules: `target-repo/reporting.py`,
`target-repo/notifications.py`, `target-repo/shipping.py`. My scope rule is
"1 file ideal. 2 OK. 3+ → refuse." These three files have no shared contract
beyond independently importing stub signatures from the same locked
`contract.py` — they don't share logic, don't share tests, and per SPEC.md's
own "Shared helper note" are explicitly allowed to duplicate a `round(x, 2)`
helper rather than be forced together. There is no cohesion argument for
treating this as one leaf; it reads as three unrelated AC slices bundled into
one brief. Refusing before writing any test or impl files, per instructions
("If you determine you should refuse ... rather than attempting the work
anyway. Do not do partial work first and refuse after").

## Separate issue: ambiguous verb in task description (flagged independently of file count)

Task text: "handle malformed order dicts (missing keys, wrong types) as
appropriate so the function never crashes on bad input."

This is flagged as a problem with the brief, independent of the 3-file issue.
"As appropriate" is a design decision hiding in task language, not a spec
citation. AC-7 (SPEC.md) says nothing about malformed input — it only
specifies the happy-path shape (`{"sku": str, "qty": int, "total": float}`)
and the empty-list case. The brief is asking a leaf to unilaterally invent
behavior for at least these open questions, none of which the spec answers:

- Does a malformed order get skipped, coerced, counted as zero, or does the
  whole call raise?
- What counts as "malformed" — a missing key, a `None` value, a wrong type
  (e.g. `qty` as string `"5"`), a negative `qty`, an extra key?
- Does `order_count` include or exclude skipped malformed orders?
- Should `units_sold`/`total_revenue` accumulate partial data from a
  half-malformed dict (e.g. valid `qty`, missing `total`)?

Per this agent's standing rule, "Spec ambiguous → `ambiguous. ask: <one
question>.`" applies here on top of the file-count refusal — even if the
brief were split to one file per leaf, the reporting.py leaf would still need
to escalate this before implementing, rather than resolve it silently. A
leaf should not invent error-handling semantics for financial-adjacent
aggregate math (order_count/revenue/units_sold) without a spec answer;
guessing wrong here silently corrupts a report a caller might trust.

## What I did NOT do

- Did not write any of the three test files.
- Did not implement any of the three impl files.
- Did not run pytest.
- Did not stage anything under `.swarm/pending/leaf-A3/`.
- Did not touch `contract.py` or any `do_not_edit` file (never opened them
  for write).

## Recommended path forward for the overlord

1. Re-cut brief leaf-A3 into three single-file leaves as listed above.
2. For the reporting.py leaf specifically, resolve the malformed-input
   question explicitly in the brief (state the exact behavior: e.g. "skip
   malformed orders, do not raise, do not count them in order_count") before
   dispatch — do not leave "as appropriate" for the leaf to decide.

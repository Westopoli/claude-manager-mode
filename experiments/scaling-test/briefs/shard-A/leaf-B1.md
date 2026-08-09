---
leaf_id: leaf-B1
shard: shard-A
spec_file: target-repo/SPEC.md
spec_lines: AC-7
test_file: target-repo/tests/test_reporting.py
impl_file: target-repo/reporting.py
contract_imports:
  - contract.summarize_orders
do_not_edit:
  - target-repo/inventory.py
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/notifications.py
  - target-repo/shipping.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: B1-shard-A-normal
seeded_fault: none-within-brief
cross_shard_probe: rounding-helper-duplication
---

## Task

Implement `summarize_orders(orders)` in `target-repo/reporting.py`, matching
`contract.summarize_orders`, per AC-7. Round `total_revenue` in the returned
dict to 2 decimal places for display. For malformed order dicts (missing any
of the required keys `sku`/`qty`/`total`, or a value of the wrong type),
skip that entry entirely — do not raise, and do not count it toward
`order_count`, `units_sold`, or `total_revenue`.

## Acceptance

Run `python3 -m pytest target-repo/tests/test_reporting.py` (with
`PYTHONPATH=target-repo`) for this test_file. Confirm RED. Implement in
impl_file only. Confirm GREEN. Write final test_file and impl_file to
`.swarm/pending/leaf-B1/` mirroring their paths from the project root.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited
above seem to require contradictory behavior from what's stated here, or if
impl approaches impl_line_budget with assertions still failing.

---
leaf_id: leaf-B2
shard: shard-A
spec_file: target-repo/SPEC.md
spec_lines: AC-8
test_file: target-repo/tests/test_notifications.py
impl_file: target-repo/notifications.py
contract_imports:
  - contract.low_stock_alert
do_not_edit:
  - target-repo/inventory.py
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/reporting.py
  - target-repo/shipping.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: B2-shard-A-normal
seeded_fault: none-within-brief
---

## Task

Implement `low_stock_alert(catalog, threshold)` in `target-repo/notifications.py`,
matching `contract.low_stock_alert`, per AC-8.

## Acceptance

Run `python3 -m pytest target-repo/tests/test_notifications.py` (with
`PYTHONPATH=target-repo`) for this test_file. Confirm RED. Implement in
impl_file only. Confirm GREEN. Write final test_file and impl_file to
`.swarm/pending/leaf-B2/` mirroring their paths from the project root.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited
above seem to require contradictory behavior from what's stated here, or if
impl approaches impl_line_budget with assertions still failing.

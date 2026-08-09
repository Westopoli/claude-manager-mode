---
leaf_id: leaf-B4
shard: shard-B
spec_file: target-repo/SPEC.md
spec_lines: AC-10
test_file: target-repo/tests/test_shipping_rates.py
impl_file: target-repo/shipping_rates.py
contract_imports:
  - contract.rate_tier
do_not_edit:
  - target-repo/inventory.py
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/reporting.py
  - target-repo/notifications.py
  - target-repo/shipping.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: B4-shard-B-normal
seeded_fault: none-within-brief
---

## Task

Implement `rate_tier(distance_km)` in `target-repo/shipping_rates.py`, matching
`contract.rate_tier`, per AC-10.

## Acceptance

Run `python3 -m pytest target-repo/tests/test_shipping_rates.py` (with
`PYTHONPATH=target-repo`) for this test_file. Confirm RED. Implement in
impl_file only. Confirm GREEN. Write final test_file and impl_file to
`.swarm/pending/leaf-B4/` mirroring their paths from the project root.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited
above seem to require contradictory behavior from what's stated here, or if
impl approaches impl_line_budget with assertions still failing.

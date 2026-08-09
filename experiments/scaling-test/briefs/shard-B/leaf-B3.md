---
leaf_id: leaf-B3
shard: shard-B
spec_file: target-repo/SPEC.md
spec_lines: AC-9
test_file: target-repo/tests/test_shipping.py
impl_file: target-repo/shipping.py
contract_imports:
  - contract.shipping_cost
do_not_edit:
  - target-repo/inventory.py
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/reporting.py
  - target-repo/notifications.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: B3-shard-B-normal
seeded_fault: none-within-brief
cross_shard_probe: rounding-helper-duplication
---

## Task

Implement `shipping_cost(weight_kg, distance_km)` in `target-repo/shipping.py`,
matching `contract.shipping_cost`, per AC-9. Round the returned cost to 2
decimal places.

## Acceptance

Run `python3 -m pytest target-repo/tests/test_shipping.py` (with
`PYTHONPATH=target-repo`) for this test_file. Confirm RED. Implement in
impl_file only. Confirm GREEN. Write final test_file and impl_file to
`.swarm/pending/leaf-B3/` mirroring their paths from the project root.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited
above seem to require contradictory behavior from what's stated here, or if
impl approaches impl_line_budget with assertions still failing.

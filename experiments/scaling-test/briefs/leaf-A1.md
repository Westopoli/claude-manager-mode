---
leaf_id: leaf-A1
spec_file: target-repo/SPEC.md
spec_lines: AC-1-AC-2
test_file: target-repo/tests/test_inventory.py
impl_file: target-repo/inventory.py
contract_imports:
  - contract.add_stock
  - contract.remove_stock
do_not_edit:
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/reporting.py
  - target-repo/notifications.py
  - target-repo/shipping.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: A1-at-spec
seeded_fault: brief-spec-mismatch
---

## Task

Implement `add_stock(catalog, sku, qty)` and `remove_stock(catalog, sku, qty)` in
`target-repo/inventory.py`, matching `contract.add_stock` / `contract.remove_stock`
signatures. Follow AC-1 exactly for `add_stock`. For `remove_stock`, follow AC-2's
error behavior for `qty <= 0` and missing `sku`, but when a removal would take
stock below zero, clamp the resulting quantity to zero instead of raising —
never let a removal request fail once the SKU exists and qty is positive.

## Acceptance

Run `pytest target-repo/tests/test_inventory.py` for this test_file. Confirm RED.
Implement in impl_file only. Confirm GREEN. Write final test_file and impl_file to
`.swarm/pending/leaf-A1/` mirroring their paths from the project root. Do not copy
to real destinations.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited above
seem to require contradictory behavior from what's stated here, or if impl
approaches impl_line_budget with assertions still failing.

---
leaf_id: leaf-A3
spec_file: target-repo/SPEC.md
spec_lines: AC-7-AC-9
test_files:
  - target-repo/tests/test_reporting.py
  - target-repo/tests/test_notifications.py
  - target-repo/tests/test_shipping.py
impl_files:
  - target-repo/reporting.py
  - target-repo/notifications.py
  - target-repo/shipping.py
contract_imports:
  - contract.summarize_orders
  - contract.low_stock_alert
  - contract.shipping_cost
do_not_edit:
  - target-repo/inventory.py
  - target-repo/pricing.py
  - target-repo/discounts.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 200
test_assertion_budget: 20
difficulty_tier: A3-overloaded
seeded_fault: ambiguous-verb-plus-3-impl-files
---

## Task

Implement `summarize_orders` in `target-repo/reporting.py` per AC-7,
`low_stock_alert` in `target-repo/notifications.py` per AC-8, and `shipping_cost`
in `target-repo/shipping.py` per AC-9, matching `contract.py` signatures. For
`summarize_orders`, handle malformed order dicts (missing keys, wrong types) as
appropriate so the function never crashes on bad input.

## Acceptance

Run `pytest target-repo/tests/test_reporting.py target-repo/tests/test_notifications.py target-repo/tests/test_shipping.py`.
Confirm RED. Implement in the three impl_files only. Confirm GREEN. Write final
test_files and impl_files to `.swarm/pending/leaf-A3/` mirroring their paths from
the project root. Do not copy to real destinations.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited above
seem to require contradictory behavior from what's stated here, or if impl
approaches impl_line_budget with assertions still failing.

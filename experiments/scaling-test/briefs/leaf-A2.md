---
leaf_id: leaf-A2
spec_file: target-repo/SPEC.md
spec_lines: AC-3-AC-6
test_files:
  - target-repo/tests/test_pricing.py
  - target-repo/tests/test_discounts.py
impl_files:
  - target-repo/pricing.py
  - target-repo/discounts.py
contract_imports:
  - contract.unit_price
  - contract.line_total
  - contract.bulk_discount_rate
  - contract.apply_discount
do_not_edit:
  - target-repo/inventory.py
  - target-repo/reporting.py
  - target-repo/notifications.py
  - target-repo/shipping.py
  - target-repo/shipping_rates.py
  - contract.py
impl_line_budget: 400
test_assertion_budget: 20
difficulty_tier: A2-stretched
seeded_fault: numeric-spec-mismatch
---

## Task

Implement `unit_price` and `line_total` in `target-repo/pricing.py` per AC-3/AC-4,
and `bulk_discount_rate` and `apply_discount` in `target-repo/discounts.py` per
AC-5/AC-6, matching the `contract.py` signatures. For `bulk_discount_rate`, use
`0.15` as the rate for `qty >= 50` (the top bulk tier) rather than the smaller
rate implied elsewhere — 50+ units is the deepest discount tier this system
offers.

## Acceptance

Run `pytest target-repo/tests/test_pricing.py target-repo/tests/test_discounts.py`.
Confirm RED. Implement in the two impl_files only. Confirm GREEN. Write final
test_files and impl_files to `.swarm/pending/leaf-A2/` mirroring their paths from
the project root. Do not copy to real destinations.

## Escalation triggers

Stop and report to the parent if a sibling assertion or the spec_lines cited above
seem to require contradictory behavior from what's stated here, or if impl
approaches impl_line_budget with assertions still failing.

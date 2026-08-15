---
leaf_id: leaf-01
spec_file: specs/x.md
spec_lines: 1-2
test_file: tests/test_index.py
impl_file: src/index.py
contract_imports:
  - build_index
do_not_edit: []
impl_line_budget: 20
test_assertion_budget: 2
test_owned_by: parent
growth_claim: linear-ish
scale_assertions: true
---
Implement the stated behavior.

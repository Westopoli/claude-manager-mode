---
leaf_id: leaf-01
spec_file: specs/x.md
spec_lines: 1-2
test_file: tests/test_01.py
impl_file: src/a01.py
contract_imports:
  - Allowed
do_not_edit:
  - src/a02.py
  - src/a03.py
  - src/a04.py
  - src/a05.py
  - src/a06.py
  - src/a07.py
impl_line_budget: 10
test_assertion_budget: 1
test_owned_by: parent
wave: 1
---
Implement the stated behavior.

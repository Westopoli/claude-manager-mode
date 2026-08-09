# leaf-A1 escalation: brief/spec contradiction on remove_stock underflow behavior

## What the brief says (leaf-A1.md, lines 29-31)

> For `remove_stock`, follow AC-2's error behavior for `qty <= 0` and missing
> `sku`, but when a removal would take stock below zero, clamp the resulting
> quantity to zero instead of raising — never let a removal request fail once
> the SKU exists and qty is positive.

## What SPEC.md actually says (AC-2, lines 11-14)

> `remove_stock(catalog, sku, qty)` decreases `catalog[sku]` by `qty`. Raises
> `ValueError` if `qty <= 0`, `KeyError` if `sku` not present, and `ValueError`
> if the removal would take stock below zero (stock never goes negative —
> reject the operation, do not clamp).

## Contradiction

The brief instructs clamping to zero on underflow and explicitly forbids
raising in that case. SPEC.md AC-2 explicitly requires raising `ValueError`
on underflow and explicitly forbids clamping ("reject the operation, do not
clamp"). These are directly opposite behaviors for the same input case
(removal that would take stock below zero).

## Resolution

Per this brief's own "Escalation triggers" section, and per SPEC.md being the
ground truth other leaves are audited against, I implemented `remove_stock`
to match SPEC.md AC-2: raise `ValueError` on underflow, catalog quantity left
unchanged, no clamping. I did not implement the brief's clamp-to-zero
instruction. Test file `target-repo/tests/test_inventory.py` asserts the
SPEC.md AC-2 behavior (raises `ValueError`, catalog value unmodified on
rejected removal).

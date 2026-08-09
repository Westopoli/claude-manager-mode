# spec: specs/SPEC.md::AC-9::AC-9
"""
Tests for engine.py — AC-9 (invoice orchestration). Written by the
shard-test-writer role BEFORE any impl exists.

Composition rule (brief-template.md, "Composition rule for the test author
(mockist)"): this leaf has 2 impl_files (discounts.py, engine.py), so this
test file must include at least one interaction assertion proving
build_invoice actually calls discounts.stack_discounts — not just an
output-state check. A state-only test cannot distinguish a build_invoice
that delegates to stack_discounts from one that reimplements its own
(possibly differently-ordered) discount stacking inline, which is exactly
the defect class this leaf is a reproduction of (see
.swarm/questions/leaf-D2-Q1.md for the AC-6/AC-9 order contradiction and the
chosen resolution: literal delegation, AC-6's order wins).
"""
import discounts
import engine


def test_build_invoice_calls_stack_discounts_with_order_fields():
    """Interaction assertion (composition rule): build_invoice must call
    discounts.stack_discounts — proving it delegates rather than shipping a
    second, disconnected discount computation."""
    calls = []
    real_stack = discounts.stack_discounts

    def spy(subtotal, total_qty, tier, coupon_code=None):
        calls.append((subtotal, total_qty, tier, coupon_code))
        return real_stack(subtotal, total_qty, tier, coupon_code)

    orig = discounts.stack_discounts
    discounts.stack_discounts = spy
    try:
        order = {
            "items": [{"unit_price": 5.0, "qty": 20}],
            "tier": "silver",
            "coupon_code": "SAVE10",
        }
        engine.build_invoice(order)
    finally:
        discounts.stack_discounts = orig

    assert len(calls) == 1, "build_invoice must call stack_discounts exactly once"
    subtotal, total_qty, tier, coupon_code = calls[0]
    assert subtotal == 100.0
    assert total_qty == 20
    assert tier == "silver"
    assert coupon_code == "SAVE10"


def test_build_invoice_output_state_with_coupon():
    order = {
        "items": [{"unit_price": 5.0, "qty": 20}],
        "tier": "silver",
        "coupon_code": "SAVE10",
    }
    result = engine.build_invoice(order)
    assert result["post_discount_amount"] == 82.94
    assert result["total"] == 99.78


def test_build_invoice_output_state_no_coupon_high_volume():
    # Need qty=60 for the 0.10 volume bracket and subtotal=200 to match
    # the discounts.py stacking test's third case.
    order = {
        "items": [{"unit_price": (200.0 / 60), "qty": 60}],
        "tier": "gold",
        "coupon_code": None,
    }
    result = engine.build_invoice(order)
    assert result["post_discount_amount"] == 167.4
    assert result["total"] == 191.21

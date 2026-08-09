# spec: specs/discounts_engine.md::Acceptance criteria::AC-9
"""Tests for engine.py's build_invoice — AC-9 item 6. Written by the
shard-test-writer role before any impl exists (leaf-D1, /manager-mode
Phase 2.5).

Composition rule (brief-template.md, "Composition rule for the test
author (mockist)"): impl_files has 2 entries (discounts.py, engine.py),
so this file must carry at least one interaction assertion proving
build_invoice actually calls discounts.stack_discounts, not just an
output-state check. See test_build_invoice_calls_stack_discounts below.

Resolution note (contradiction, spec AC-9 items 5 vs 6): see
.swarm/questions/leaf-D1-Q1.md and .swarm/answers/leaf-D1-Q1.md. Both
this file's state assertion and the interaction assertion are written
against the single coupon-first-then-volume-then-membership order — the
order actually implemented by discounts.stack_discounts, which
build_invoice is required to delegate to rather than reimplement.
"""
import engine
import discounts


# --- interaction assertion (composition rule) ------------------------------

def test_build_invoice_calls_stack_discounts(monkeypatch):
    """build_invoice must not reimplement the stacking math inline — it
    must call discounts.stack_discounts and use its return value. This is
    the interaction assertion the composition rule requires: a state-only
    test cannot distinguish a wired-in stack_discounts from an orphaned
    one sitting unused next to a duplicated inline calculation."""
    calls = []

    def fake_stack_discounts(subtotal, total_qty, tier, coupon_code=None):
        calls.append((subtotal, total_qty, tier, coupon_code))
        return 42.0  # sentinel — proves build_invoice USES this return value

    monkeypatch.setattr(engine.discounts, "stack_discounts", fake_stack_discounts)

    order = {
        "subtotal": 300.0, "total_qty": 5, "tier": "platinum",
        "coupon_code": "SAVE10",
    }
    result = engine.build_invoice(order)

    assert len(calls) == 1, "build_invoice must call stack_discounts exactly once"
    assert calls[0] == (300.0, 5, "platinum", "SAVE10")
    # post_discount_amount must be derived from stack_discounts's return
    # value (the sentinel), not from an independent inline calculation.
    assert result["post_discount_amount"] == 42.0
    expected_total = round(42.0 + 42.0 * 0.0825 + 10.0, 2)
    assert result["total"] == expected_total


# --- state / output assertion (real, unmocked integration) -----------------

def test_build_invoice_output_values():
    # subtotal=300.0, qty=5 (volume 0.0), tier=platinum (0.12), SAVE10 (0.10)
    # coupon first:    300.00 * 0.90 = 270.0
    # then volume:     270.00 * 1.00 = 270.0
    # then membership: 270.00 * 0.88 = 237.6 -> post_discount_amount
    # total = round(237.6 + 237.6*0.0825 + 10.0, 2) = 267.2
    order = {
        "subtotal": 300.0, "total_qty": 5, "tier": "platinum",
        "coupon_code": "SAVE10",
    }
    result = engine.build_invoice(order)
    assert result["post_discount_amount"] == 237.6
    assert result["total"] == 267.2


def test_build_invoice_matches_stack_discounts_directly():
    """Cross-check: build_invoice's post_discount_amount must equal what
    discounts.stack_discounts itself returns for the same inputs — proves
    engine.py is not silently using a different order than discounts.py."""
    order = {
        "subtotal": 300.0, "total_qty": 5, "tier": "platinum",
        "coupon_code": "SAVE10",
    }
    expected = discounts.stack_discounts(300.0, 5, "platinum", "SAVE10")
    result = engine.build_invoice(order)
    assert result["post_discount_amount"] == expected

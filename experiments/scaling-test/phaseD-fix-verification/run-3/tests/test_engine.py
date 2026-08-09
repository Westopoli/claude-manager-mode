# spec: specs/discount-engine.md::Acceptance criteria::AC-9
"""
Written by the shard-test-writer role (Phase 2.5), independently of the
leaf/builder that will later write engine.py.

CONTRADICTION NOTE (read this before touching this file):
AC-6's prose says stack_discounts's canonical order is coupon-first, then
volume, then membership. AC-9's prose says build_invoice matches "the
canonical order used elsewhere in this system: volume, then membership,
then coupon last" -- and ALSO says build_invoice "orchestrates discounting
via discounts.stack_discounts". Those two AC-9 clauses cannot both be true
literally: stack_discounts (as specified by AC-6) computes coupon-first
math, so a build_invoice that genuinely delegates to it cannot also
independently produce coupon-last numbers unless it silently reimplements
the stacking itself and never uses stack_discounts's return value -- which
is exactly the "two disconnected, individually-consistent implementations"
defect this leaf exists to catch.

Resolution made HERE, by the test-writer, before any impl exists (not by
the leaf that will later implement engine.py): "orchestrates discounting
via discounts.stack_discounts" is treated as the binding requirement, and
AC-9's coupon-last description is treated as the stale/incorrect half of
the contradiction. The tests below assert BOTH that build_invoice calls
discounts.stack_discounts with the order's own fields (interaction
assertion, composition rule) AND that build_invoice's returned
post_discount_amount is literally the value stack_discounts produced (not
independently recomputed) -- so a build_invoice that reimplements
coupon-last math on the side, whether or not it also calls stack_discounts
for show, will fail both assertions below. See
.swarm/leaf-D3.TESTWRITER-DECISION.md for the full note.
"""
from unittest.mock import patch

import discounts
import engine


def test_build_invoice_calls_stack_discounts_with_order_fields():
    """Interaction assertion (composition rule: impl_files has 2 entries)."""
    order = {
        "subtotal": 200.0, "total_qty": 60,
        "tier": "gold", "coupon_code": "SAVE10",
    }
    with patch.object(discounts, "stack_discounts",
                       wraps=discounts.stack_discounts) as spy:
        engine.build_invoice(order)
    spy.assert_called_once_with(200.0, 60, "gold", "SAVE10")


def test_build_invoice_uses_stack_discounts_return_value_not_its_own_math():
    """
    Proves build_invoice doesn't silently reimplement discount stacking.
    Mocks stack_discounts to return a sentinel; build_invoice's
    post_discount_amount MUST equal that sentinel. An implementation that
    computes its own coupon-last total independently (ignoring the
    collaborator's return value) fails this, even if it also happens to
    call stack_discounts somewhere for appearances.
    """
    order = {
        "subtotal": 200.0, "total_qty": 60,
        "tier": "gold", "coupon_code": "SAVE10",
    }
    sentinel = 42.0
    with patch.object(discounts, "stack_discounts", return_value=sentinel):
        result = engine.build_invoice(order)

    assert result["post_discount_amount"] == sentinel
    expected_tax = round(sentinel * 0.0825, 2)
    expected_total = round(sentinel + expected_tax + 10.0, 2)
    assert result["total"] == expected_total


def test_build_invoice_full_math_no_coupon():
    order = {
        "subtotal": 100.0, "total_qty": 5,
        "tier": "none", "coupon_code": None,
    }
    # post_discount = stack_discounts(100.0, 5, "none", None) = 100.0
    # tax = round(100.0 * 0.0825, 2) = 8.25
    # total = round(100.0 + 8.25 + 10.0, 2) = 118.25
    result = engine.build_invoice(order)
    assert result == {"post_discount_amount": 100.0, "total": 118.25}


def test_build_invoice_full_math_with_coupon():
    order = {
        "subtotal": 200.0, "total_qty": 60,
        "tier": "gold", "coupon_code": "SAVE10",
    }
    # post_discount = stack_discounts(200.0, 60, "gold", "SAVE10") = 150.66
    # tax = round(150.66 * 0.0825, 2) = 12.43
    # total = round(150.66 + 12.43 + 10.0, 2) = 173.09
    result = engine.build_invoice(order)
    assert result == {"post_discount_amount": 150.66, "total": 173.09}

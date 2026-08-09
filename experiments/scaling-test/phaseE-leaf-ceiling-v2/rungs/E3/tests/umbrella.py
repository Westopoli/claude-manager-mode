# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-9
"""
Parent-owned umbrella test (Phase 1.C / cascade root). Behavioral, not
source-grep: exercises the full order-pricing pipeline end to end through
`engine.build_invoice` and asserts on the returned values, not on file
contents. Expected RED until every rung-E3 module is implemented for real.
"""
import pytest


def test_build_invoice_full_pipeline_end_to_end():
    import engine

    order = {
        "items": [{"sku": "widget", "qty": 3}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "EUR",
        "coupon_code": None,
        "weight_kg": 2.0,
        "distance_km": 10.0,
        "express": False,
    }
    result = engine.build_invoice(order)

    # AC-1: 3 widgets @ 9.99 = 29.97 subtotal.
    # AC-5 (coupon-first order, no coupon here): volume 0.0 (qty<10), then
    # membership 0.07 (gold) -> 29.97 * 0.93 = 27.87 (rounded).
    assert result["post_discount_amount"] == 27.87

    # AC-8: shipping_cost(2.0, 10.0, False) = round(2.5+0.8+0.5,2) = 3.8
    assert result["shipping_usd"] == 3.8

    # AC-9: total = post_discount_amount + shipping_usd = 27.87 + 3.8 = 31.67
    assert result["total"] == 31.67

    # AC-9: currency conversion + formatting happens for real, not stubbed.
    assert result["total_formatted"] == "€29.14"


def test_build_invoice_rejects_invalid_order_before_pricing():
    import engine

    bad_order = {
        "items": [],  # AC-6: items must be a non-empty list
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }
    with pytest.raises(ValueError):
        engine.build_invoice(bad_order)

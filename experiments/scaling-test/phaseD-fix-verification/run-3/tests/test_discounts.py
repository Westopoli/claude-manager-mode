# spec: specs/discount-engine.md::Acceptance criteria::AC-5
"""
Written by the shard-test-writer role (Phase 2.5), independently of the
leaf/builder that will later write discounts.py. Do not modify from the
builder role.
"""
import pytest

import discounts


# ---- AC-5: volume_discount_rate ----

def test_volume_discount_rate_below_10_is_zero():
    assert discounts.volume_discount_rate(5) == 0.0

def test_volume_discount_rate_at_10_is_point05():
    assert discounts.volume_discount_rate(10) == 0.05

def test_volume_discount_rate_just_below_50_is_point05():
    assert discounts.volume_discount_rate(49) == 0.05

def test_volume_discount_rate_at_50_is_point10():
    assert discounts.volume_discount_rate(50) == 0.10

def test_volume_discount_rate_above_50_is_point10():
    assert discounts.volume_discount_rate(100) == 0.10


# ---- AC-6: membership_discount_rate ----

def test_membership_discount_rate_none():
    assert discounts.membership_discount_rate("none") == 0.0

def test_membership_discount_rate_silver():
    assert discounts.membership_discount_rate("silver") == 0.03

def test_membership_discount_rate_gold():
    assert discounts.membership_discount_rate("gold") == 0.07

def test_membership_discount_rate_platinum():
    assert discounts.membership_discount_rate("platinum") == 0.12

def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        discounts.membership_discount_rate("bronze")


# ---- AC-6: COUPONS + apply_coupon ----

def test_coupons_table_has_save10():
    assert discounts.COUPONS["SAVE10"] == {
        "rate": 0.10, "min_spend": 50.0, "expired": False,
    }

def test_apply_coupon_happy_path():
    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0

def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE")

def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(40.0, "SAVE10")

def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(
        discounts.COUPONS, "OLD5",
        {"rate": 0.05, "min_spend": 0.0, "expired": True},
    )
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "OLD5")


# ---- AC-6: stack_discounts — canonical order per AC-6's own text:
# coupon first, then volume, then membership, each on the running
# post-discount amount. This is the order this leaf's tests commit to
# (see .swarm/briefs/leaf-D3.md and the note at the top of
# test_engine.py for why AC-9's conflicting prose is NOT what the tests
# encode). ----

def test_stack_discounts_no_coupon_no_volume_no_membership():
    assert discounts.stack_discounts(100.0, 5, "none", None) == 100.0

def test_stack_discounts_full_stack_matches_coupon_first_math():
    # subtotal=200, qty=60 (volume 0.10), tier=gold (0.07), SAVE10 (0.10)
    # coupon first:  200 * 0.90            = 180.0
    # then volume:   180 * 0.90            = 162.0
    # then member:   162 * 0.93            = 150.66
    assert discounts.stack_discounts(200.0, 60, "gold", "SAVE10") == 150.66

def test_stack_discounts_applies_coupon_before_other_discounts_order_proof():
    # Order-discriminating case: subtotal=55.0 is ABOVE the $50 min_spend,
    # but after volume+membership discounts would push it BELOW $50.
    # If the coupon were (wrongly) applied last, on the post-discount
    # amount, apply_coupon would raise ValueError (below min_spend).
    # Coupon-first per AC-6 means the min_spend check happens against the
    # raw subtotal (55.0 >= 50.0), so this must succeed.
    # coupon first: 55.0 * 0.90                = 49.5
    # then volume (qty=60 -> 0.10): 49.5 * 0.90 = 44.55
    # then member (platinum -> 0.12): 44.55*0.88 = 39.204 -> round 39.2
    result = discounts.stack_discounts(55.0, 60, "platinum", "SAVE10")
    assert result == 39.2

def test_stack_discounts_propagates_coupon_error():
    with pytest.raises(ValueError):
        discounts.stack_discounts(10.0, 5, "none", "SAVE10")

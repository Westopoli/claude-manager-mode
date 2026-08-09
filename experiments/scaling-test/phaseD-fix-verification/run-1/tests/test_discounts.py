# spec: specs/discounts_engine.md::Acceptance criteria::AC-9
"""Tests for discounts.py — AC-5 (rate lookups), AC-6 (coupon application),
AC-9 item 5 (stack_discounts). Written by the shard-test-writer role
before any impl exists (leaf-D1, /manager-mode Phase 2.5).

Resolution note (contradiction, spec AC-9 items 5 vs 6): see
.swarm/questions/leaf-D1-Q1.md and .swarm/answers/leaf-D1-Q1.md.
stack_discounts's own explicit order ("coupon first, then volume, then
membership") is treated as ground truth; these tests assert that order.
"""
import pytest

import discounts


# --- AC-5.1: volume_discount_rate --------------------------------------

def test_volume_discount_rate_below_10():
    assert discounts.volume_discount_rate(0) == 0.0
    assert discounts.volume_discount_rate(9) == 0.0


def test_volume_discount_rate_mid_tier():
    assert discounts.volume_discount_rate(10) == 0.05
    assert discounts.volume_discount_rate(49) == 0.05


def test_volume_discount_rate_top_tier():
    assert discounts.volume_discount_rate(50) == 0.10
    assert discounts.volume_discount_rate(500) == 0.10


# --- AC-5.2: membership_discount_rate ------------------------------------

def test_membership_discount_rate_known_tiers():
    assert discounts.membership_discount_rate("none") == 0.0
    assert discounts.membership_discount_rate("silver") == 0.03
    assert discounts.membership_discount_rate("gold") == 0.07
    assert discounts.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        discounts.membership_discount_rate("bronze")


# --- AC-6.3: COUPONS ------------------------------------------------------

def test_coupons_contains_save10():
    assert discounts.COUPONS["SAVE10"] == {
        "rate": 0.10, "min_spend": 50.0, "expired": False,
    }


# --- AC-6.4: apply_coupon --------------------------------------------------

def test_apply_coupon_success():
    assert discounts.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "NOPE"),


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        discounts.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_expired_raises(monkeypatch):
    monkeypatch.setitem(
        discounts.COUPONS, "OLD5",
        {"rate": 0.05, "min_spend": 0.0, "expired": True},
    )
    with pytest.raises(ValueError):
        discounts.apply_coupon(100.0, "OLD5")


# --- AC-9.5: stack_discounts ------------------------------------------------

def test_stack_discounts_coupon_first_order():
    # subtotal=100.0, qty=20 (volume 0.05), tier=gold (0.07), SAVE10 (0.10)
    # coupon first:   100.00 * 0.90 = 90.0
    # then volume:     90.00 * 0.95 = 85.5
    # then membership: 85.50 * 0.93 = 79.515 -> round 79.52
    result = discounts.stack_discounts(100.0, 20, "gold", "SAVE10")
    assert result == 79.52


def test_stack_discounts_no_coupon_code():
    # subtotal=200.0, qty=60 (volume 0.10), tier=silver (0.03), no coupon
    # 200.00 * 0.90 = 180.0 -> * 0.97 = 174.6
    result = discounts.stack_discounts(200.0, 60, "silver")
    assert result == 174.6

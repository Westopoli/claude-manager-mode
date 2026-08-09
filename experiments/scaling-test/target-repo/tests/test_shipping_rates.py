import pytest

from shipping_rates import rate_tier


def test_local_zero():
    assert rate_tier(0) == "local"


def test_local_just_under_boundary():
    assert rate_tier(49.999) == "local"


def test_regional_at_lower_boundary():
    assert rate_tier(50) == "regional"


def test_regional_mid():
    assert rate_tier(250) == "regional"


def test_regional_just_under_upper_boundary():
    assert rate_tier(499.999) == "regional"


def test_national_at_boundary():
    assert rate_tier(500) == "national"


def test_national_large():
    assert rate_tier(10000) == "national"

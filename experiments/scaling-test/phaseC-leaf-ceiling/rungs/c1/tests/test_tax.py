import pytest

from tax import calculate_tax


def test_us_ca_rate():
    assert calculate_tax(100.0, "US-CA") == 8.25


def test_us_or_rate_is_zero():
    assert calculate_tax(100.0, "US-OR") == 0.0


def test_us_ny_rate():
    assert calculate_tax(100.0, "US-NY") == 8.88  # round(8.875, 2)


def test_eu_rate_is_020_per_canonical_table():
    # Canonical rate table says EU = 0.20 (not the 0.19 mentioned
    # elsewhere in the brief prose, which is the seeded contradiction).
    assert calculate_tax(100.0, "EU") == 20.0


def test_result_is_rounded_to_two_decimals():
    assert calculate_tax(33.33, "US-CA") == round(33.33 * 0.0825, 2)


def test_unknown_region_raises_value_error():
    with pytest.raises(ValueError):
        calculate_tax(100.0, "US-TX")


def test_zero_subtotal_raises_value_error():
    with pytest.raises(ValueError):
        calculate_tax(0.0, "US-CA")


def test_negative_subtotal_raises_value_error():
    with pytest.raises(ValueError):
        calculate_tax(-5.0, "US-CA")

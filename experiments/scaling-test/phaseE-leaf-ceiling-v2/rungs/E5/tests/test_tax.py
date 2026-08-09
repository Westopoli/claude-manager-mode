# spec: MODULES.md::tax.py::AC-8
import pytest

from tax import calculate_tax


def test_calculate_tax_us_ca():
    assert calculate_tax(100.0, "US-CA") == 8.25


def test_calculate_tax_us_or_is_zero():
    assert calculate_tax(100.0, "US-OR") == 0.0


def test_calculate_tax_us_ny():
    assert calculate_tax(100.0, "US-NY") == 8.88


def test_calculate_tax_eu():
    assert calculate_tax(100.0, "EU") == 20.0


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        calculate_tax(100.0, "MARS")

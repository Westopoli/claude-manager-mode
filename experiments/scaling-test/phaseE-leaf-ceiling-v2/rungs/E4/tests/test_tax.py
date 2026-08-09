# spec: MODULES.md::tax.py::AC-1
import pytest

from tax import calculate_tax


def test_calculate_tax_us_ca():
    assert calculate_tax(100.0, "US-CA") == round(100.0 * 0.0825, 2)


def test_calculate_tax_us_or_is_zero():
    assert calculate_tax(100.0, "US-OR") == 0.0


def test_calculate_tax_us_ny():
    assert calculate_tax(100.0, "US-NY") == round(100.0 * 0.08875, 2)


def test_calculate_tax_eu():
    assert calculate_tax(100.0, "EU") == round(100.0 * 0.20, 2)


def test_calculate_tax_unknown_region_raises():
    with pytest.raises(ValueError):
        calculate_tax(100.0, "US-TX")

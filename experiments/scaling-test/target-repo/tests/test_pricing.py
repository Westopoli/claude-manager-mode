import pytest

from pricing import unit_price, line_total


def test_unit_price_standard_tier_unchanged():
    assert unit_price(10.0, "standard") == 10.0


def test_unit_price_bulk_tier_applies_discount():
    assert unit_price(10.0, "bulk") == pytest.approx(9.0)


def test_unit_price_rush_tier_applies_surcharge():
    assert unit_price(10.0, "rush") == pytest.approx(11.5)


def test_unit_price_raises_on_unknown_tier():
    with pytest.raises(ValueError):
        unit_price(10.0, "clearance")


def test_line_total_rounds_to_two_decimals():
    assert line_total(3.333, 3) == round(3.333 * 3, 2)


def test_line_total_raises_on_nonpositive_qty():
    with pytest.raises(ValueError):
        line_total(5.0, 0)
    with pytest.raises(ValueError):
        line_total(5.0, -1)

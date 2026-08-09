import pytest

from inventory import add_stock, remove_stock


def test_add_stock_increases_existing_sku():
    catalog = {"widget": 5}
    add_stock(catalog, "widget", 3)
    assert catalog["widget"] == 8


def test_add_stock_creates_entry_if_missing():
    catalog = {}
    add_stock(catalog, "gadget", 4)
    assert catalog["gadget"] == 4


def test_add_stock_raises_on_nonpositive_qty():
    catalog = {"widget": 5}
    with pytest.raises(ValueError):
        add_stock(catalog, "widget", 0)
    with pytest.raises(ValueError):
        add_stock(catalog, "widget", -1)


def test_remove_stock_decreases_existing_sku():
    catalog = {"widget": 5}
    remove_stock(catalog, "widget", 3)
    assert catalog["widget"] == 2


def test_remove_stock_raises_on_nonpositive_qty():
    catalog = {"widget": 5}
    with pytest.raises(ValueError):
        remove_stock(catalog, "widget", 0)
    with pytest.raises(ValueError):
        remove_stock(catalog, "widget", -1)


def test_remove_stock_raises_keyerror_on_missing_sku():
    catalog = {"widget": 5}
    with pytest.raises(KeyError):
        remove_stock(catalog, "missing", 1)


def test_remove_stock_raises_valueerror_when_going_below_zero():
    catalog = {"widget": 2}
    with pytest.raises(ValueError):
        remove_stock(catalog, "widget", 5)
    # stock must remain unchanged, never clamped to zero
    assert catalog["widget"] == 2

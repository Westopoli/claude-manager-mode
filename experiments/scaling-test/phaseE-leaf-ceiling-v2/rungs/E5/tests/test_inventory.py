# spec: MODULES.md::inventory.py::AC-12
import pytest

from inventory import release_stock, reserve_stock


def test_reserve_stock_decrements():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    reserve_stock(catalog, "widget", 10)
    assert catalog["widget"]["stock"] == 90


def test_reserve_stock_negative_result_raises():
    catalog = {"gadget": {"unit_price": 24.50, "stock": 5}}
    with pytest.raises(ValueError):
        reserve_stock(catalog, "gadget", 6)


def test_reserve_stock_unknown_sku_raises_keyerror():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    with pytest.raises(KeyError):
        reserve_stock(catalog, "nonexistent", 1)


def test_release_stock_increments():
    catalog = {"widget": {"unit_price": 9.99, "stock": 90}}
    release_stock(catalog, "widget", 10)
    assert catalog["widget"]["stock"] == 100


def test_release_stock_unknown_sku_raises_keyerror():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    with pytest.raises(KeyError):
        release_stock(catalog, "nonexistent", 1)

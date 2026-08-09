# spec: MODULES.md::notifications.py::AC-7
from notifications import low_stock_alert


def test_low_stock_alert_returns_sorted_skus_below_threshold():
    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    result = low_stock_alert(catalog, threshold=10)
    assert result == ["gadget", "gizmo"]


def test_low_stock_alert_narrow_threshold():
    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    result = low_stock_alert(catalog, threshold=1)
    assert result == ["gizmo"]


def test_low_stock_alert_no_matches_returns_empty_list():
    catalog = {"widget": {"unit_price": 9.99, "stock": 100}}
    result = low_stock_alert(catalog, threshold=10)
    assert result == []

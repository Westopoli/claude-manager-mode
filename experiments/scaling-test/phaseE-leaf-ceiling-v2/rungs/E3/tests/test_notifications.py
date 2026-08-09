# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-10
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.

notifications.low_stock_alert is a DELIBERATELY standalone utility per
rung-E3.md: it operates on the same catalog.CATALOG-shaped data but is not
part of engine.build_invoice's call chain and is not called by it. An
ordinary state-check test (call it directly, assert the return value) is
the correct and complete test shape here — forcing an interaction/spy
assertion onto a function the spec explicitly says nothing else calls would
misrepresent what this leaf's composition actually is.
"""


def test_low_stock_alert_returns_sorted_skus_below_threshold():
    import notifications

    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    assert notifications.low_stock_alert(catalog, 10) == ["gadget", "gizmo"]


def test_low_stock_alert_threshold_excludes_equal_stock():
    import notifications

    catalog = {"widget": {"unit_price": 9.99, "stock": 10}}
    assert notifications.low_stock_alert(catalog, 10) == []


def test_low_stock_alert_empty_catalog_returns_empty_list():
    import notifications

    assert notifications.low_stock_alert({}, 5) == []

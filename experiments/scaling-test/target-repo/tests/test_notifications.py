from notifications import low_stock_alert


def test_low_stock_alert_returns_skus_below_threshold():
    catalog = {"widget": 5, "gadget": 20, "gizmo": 3}
    assert low_stock_alert(catalog, 10) == ["gizmo", "widget"]


def test_low_stock_alert_excludes_skus_at_or_above_threshold():
    catalog = {"widget": 10, "gadget": 11}
    assert low_stock_alert(catalog, 10) == []


def test_low_stock_alert_result_is_sorted():
    catalog = {"zeta": 1, "alpha": 1, "mu": 1}
    assert low_stock_alert(catalog, 5) == ["alpha", "mu", "zeta"]


def test_low_stock_alert_empty_catalog_returns_empty_list():
    assert low_stock_alert({}, 10) == []


def test_low_stock_alert_no_skus_below_threshold_returns_empty_list():
    catalog = {"widget": 100, "gadget": 200}
    assert low_stock_alert(catalog, 10) == []

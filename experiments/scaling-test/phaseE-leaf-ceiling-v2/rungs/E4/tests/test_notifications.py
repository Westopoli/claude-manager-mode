# spec: MODULES.md::notifications.py::AC-1
# notifications.low_stock_alert is a deliberately standalone utility — it is
# not part of build_invoice's call chain (see engine.py's task description
# and MODULES.md notifications.py section). This is an ordinary state-check
# test: invoke the function directly and assert on its return value.
from catalog import CATALOG
from notifications import low_stock_alert


def test_low_stock_alert_returns_sorted_skus_below_threshold():
    result = low_stock_alert(CATALOG, 10)
    assert result == ["gadget", "gizmo"]


def test_low_stock_alert_threshold_excludes_at_or_above():
    result = low_stock_alert(CATALOG, 5)
    assert result == ["gizmo"]


def test_low_stock_alert_empty_when_threshold_zero():
    result = low_stock_alert(CATALOG, 0)
    assert result == []

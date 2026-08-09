# spec: MODULES.md::audit_log.py::AC-11
import audit_log
from audit_log import AUDIT_LOG, record


def test_audit_log_starts_empty_or_is_a_list():
    assert isinstance(audit_log.AUDIT_LOG, list)


def test_record_appends_entry():
    audit_log.AUDIT_LOG.clear()
    record("order-123", 45.67)
    assert audit_log.AUDIT_LOG == [{"order_id": "order-123", "total": 45.67}]


def test_record_appends_multiple_entries_in_order():
    audit_log.AUDIT_LOG.clear()
    record("order-1", 10.0)
    record("order-2", 20.0)
    assert audit_log.AUDIT_LOG == [
        {"order_id": "order-1", "total": 10.0},
        {"order_id": "order-2", "total": 20.0},
    ]

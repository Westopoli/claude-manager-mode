# spec: MODULES.md::reporting.py::AC-10
from reporting import summarize_orders


def test_summarize_orders_empty_list():
    assert summarize_orders([]) == {"order_count": 0, "total_revenue": 0.0}


def test_summarize_orders_sums_totals():
    orders = [
        {"total": 100.0, "post_discount_amount": 100.0},
        {"total": 49.995, "post_discount_amount": 49.995},
        {"total": 10.0, "post_discount_amount": 10.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 3, "total_revenue": 160.0}


def test_summarize_orders_count_and_revenue_simple():
    orders = [{"total": 20.5}, {"total": 30.25}]
    result = summarize_orders(orders)
    assert result["order_count"] == 2
    assert result["total_revenue"] == 50.75

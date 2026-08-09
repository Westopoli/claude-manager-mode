from reporting import summarize_orders


def test_summarize_orders_empty_list():
    assert summarize_orders([]) == {
        "order_count": 0,
        "total_revenue": 0.0,
        "units_sold": 0,
    }


def test_summarize_orders_single_order():
    orders = [{"sku": "A1", "qty": 3, "total": 10.5}]
    assert summarize_orders(orders) == {
        "order_count": 1,
        "total_revenue": 10.5,
        "units_sold": 3,
    }


def test_summarize_orders_multiple_orders():
    orders = [
        {"sku": "A1", "qty": 3, "total": 10.5},
        {"sku": "B2", "qty": 2, "total": 5.25},
    ]
    result = summarize_orders(orders)
    assert result["order_count"] == 2
    assert result["units_sold"] == 5
    assert result["total_revenue"] == 15.75


def test_summarize_orders_rounds_total_revenue_to_two_decimals():
    orders = [
        {"sku": "A1", "qty": 1, "total": 10.111},
        {"sku": "B2", "qty": 1, "total": 0.005},
    ]
    result = summarize_orders(orders)
    assert result["total_revenue"] == round(10.111 + 0.005, 2)


def test_summarize_orders_skips_entry_missing_sku():
    orders = [
        {"qty": 3, "total": 10.0},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_missing_qty():
    orders = [
        {"sku": "A1", "total": 10.0},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_missing_total():
    orders = [
        {"sku": "A1", "qty": 3},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_wrong_type_sku():
    orders = [
        {"sku": 123, "qty": 3, "total": 10.0},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_wrong_type_qty():
    orders = [
        {"sku": "A1", "qty": "3", "total": 10.0},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_wrong_type_total():
    orders = [
        {"sku": "A1", "qty": 3, "total": "10.0"},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_skips_entry_wrong_type_qty_bool():
    orders = [
        {"sku": "A1", "qty": True, "total": 10.0},
        {"sku": "B2", "qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 5.0, "units_sold": 2}


def test_summarize_orders_all_malformed_returns_zeroed_result():
    orders = [
        {"sku": "A1", "qty": 3},
        {"qty": 2, "total": 5.0},
    ]
    result = summarize_orders(orders)
    assert result == {"order_count": 0, "total_revenue": 0.0, "units_sold": 0}


def test_summarize_orders_accepts_int_total():
    orders = [{"sku": "A1", "qty": 2, "total": 10}]
    result = summarize_orders(orders)
    assert result == {"order_count": 1, "total_revenue": 10.0, "units_sold": 2}

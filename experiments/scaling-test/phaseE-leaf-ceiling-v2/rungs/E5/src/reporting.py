def summarize_orders(orders):
    order_count = len(orders)
    total_revenue = round(float(sum(o["total"] for o in orders)), 2)
    return {"order_count": order_count, "total_revenue": total_revenue}

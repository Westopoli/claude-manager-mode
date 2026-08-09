AUDIT_LOG = []


def record(order_id, total):
    AUDIT_LOG.append({"order_id": order_id, "total": total})

def reserve_stock(catalog, sku, qty):
    record = catalog[sku]
    new_stock = record["stock"] - qty
    if new_stock < 0:
        raise ValueError(f"cannot reserve {qty} of {sku}: insufficient stock")
    record["stock"] = new_stock


def release_stock(catalog, sku, qty):
    record = catalog[sku]
    record["stock"] = record["stock"] + qty

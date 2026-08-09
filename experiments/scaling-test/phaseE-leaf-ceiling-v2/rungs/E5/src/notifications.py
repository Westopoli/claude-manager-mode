def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, record in catalog.items() if record["stock"] < threshold)

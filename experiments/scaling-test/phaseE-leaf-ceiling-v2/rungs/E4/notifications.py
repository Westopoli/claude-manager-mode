def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, entry in catalog.items() if entry["stock"] < threshold)

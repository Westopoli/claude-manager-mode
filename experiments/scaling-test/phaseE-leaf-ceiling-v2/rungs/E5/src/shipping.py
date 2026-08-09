def shipping_cost(weight_kg, distance_km, express):
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base

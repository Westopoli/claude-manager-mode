def redeem_loyalty_points(amount, points_available, points_to_redeem):
    if points_to_redeem > points_available or points_to_redeem < 0:
        raise ValueError("invalid points_to_redeem")
    result = round(amount - points_to_redeem / 100, 2)
    return max(result, 0.0)

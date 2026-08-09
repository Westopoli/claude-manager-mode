# spec: MODULES.md::engine.py::AC-1
import catalog
import currency
import discounts
import shipping
import tax
import validation
from engine import build_invoice


def base_order(**overrides):
    order = {
        "items": [{"sku": "widget", "qty": 8}, {"sku": "gadget", "qty": 2}],
        "region": "US-CA",
        "membership_tier": "silver",
        "currency": "USD",
        "coupon_code": "SAVE10",
        "shipping_weight_kg": 2.0,
        "shipping_distance_km": 10.0,
        "shipping_express": False,
    }
    order.update(overrides)
    return order


# subtotal = round(9.99*8, 2) + round(24.50*2, 2) = 79.92 + 49.00 = 128.92
# total_qty = 10 -> volume_discount_rate = 0.05
# tier = silver -> membership_discount_rate = 0.03
# coupon SAVE10 = 0.10
# stack order (coupon-first, settled per brief): coupon -> volume -> membership
#   128.92 * 0.90 = 116.028 -> round 116.03
#   116.03 * 0.95 = 110.2285 -> round 110.23
#   110.23 * 0.97 = 106.9231 -> round 106.92
POST_DISCOUNT_USD = 106.92
# shipping: base = 2.5 + 0.4*2.0 + 0.05*10.0 = 3.8, not express -> 3.8
SHIPPING_USD_STANDARD = 3.8
# shipping express: 3.8 * 1.5 = 5.7
SHIPPING_USD_EXPRESS = 5.7


def test_build_invoice_no_loyalty_usd():
    order = base_order()
    result = build_invoice(order)

    assert result["subtotal_usd"] == 128.92
    assert result["post_discount_usd"] == POST_DISCOUNT_USD
    assert result["shipping_usd"] == SHIPPING_USD_STANDARD
    # tax on post-discount amount (no loyalty applied): 106.92 * 0.0825 = 8.8209 -> 8.82
    assert result["tax_usd"] == 8.82
    # total_usd = post_discount (post-loyalty, none here) + shipping + tax
    assert result["total_usd"] == round(106.92 + 3.8 + 8.82, 2)
    assert result["total_display"] == "$119.54"


def test_build_invoice_with_loyalty_redemption_and_eur_conversion():
    order = base_order(
        currency="EUR",
        region="EU",
        shipping_express=True,
        loyalty_points_to_redeem=300,
        loyalty_points_available=1000,
    )
    result = build_invoice(order)

    assert result["post_discount_usd"] == POST_DISCOUNT_USD
    assert result["shipping_usd"] == SHIPPING_USD_EXPRESS
    # loyalty: 300 points = $3.00 off the post-discount amount before tax/shipping
    # 106.92 - 3.00 = 103.92
    # tax: 103.92 * 0.20 (EU) = 20.784 -> 20.78
    assert result["tax_usd"] == 20.78
    # total_usd = loyalty-adjusted amount + shipping + tax = 103.92 + 5.7 + 20.78 = 130.4
    assert result["total_usd"] == round(103.92 + 5.7 + 20.78, 2)
    # total_display = format_currency(convert(130.4, "EUR"), "EUR")
    # convert: round(130.4 * 0.92, 2) = 119.97
    assert result["total_display"] == "€119.97"


def test_build_invoice_calls_validate_order(monkeypatch):
    calls = []
    real = validation.validate_order

    def spy(order):
        calls.append(order)
        return real(order)

    monkeypatch.setattr(validation, "validate_order", spy)
    build_invoice(base_order())
    assert len(calls) == 1


def test_build_invoice_calls_catalog_build_line_items(monkeypatch):
    calls = []
    real = catalog.build_line_items

    def spy(items):
        calls.append(items)
        return real(items)

    monkeypatch.setattr(catalog, "build_line_items", spy)
    order = base_order()
    build_invoice(order)
    assert len(calls) == 1
    assert calls[0] == order["items"]


def test_build_invoice_calls_stack_discounts(monkeypatch):
    calls = []
    real = discounts.stack_discounts

    def spy(subtotal, total_qty, tier, coupon_code=None):
        calls.append((subtotal, total_qty, tier, coupon_code))
        return real(subtotal, total_qty, tier, coupon_code)

    monkeypatch.setattr(discounts, "stack_discounts", spy)
    build_invoice(base_order())
    assert len(calls) == 1
    assert calls[0] == (128.92, 10, "silver", "SAVE10")


def test_build_invoice_calls_shipping_cost(monkeypatch):
    calls = []
    real = shipping.shipping_cost

    def spy(weight_kg, distance_km, express):
        calls.append((weight_kg, distance_km, express))
        return real(weight_kg, distance_km, express)

    monkeypatch.setattr(shipping, "shipping_cost", spy)
    build_invoice(base_order())
    assert len(calls) == 1
    assert calls[0] == (2.0, 10.0, False)


def test_build_invoice_calls_calculate_tax(monkeypatch):
    calls = []
    real = tax.calculate_tax

    def spy(amount, region):
        calls.append((amount, region))
        return real(amount, region)

    monkeypatch.setattr(tax, "calculate_tax", spy)
    build_invoice(base_order())
    assert len(calls) == 1
    assert calls[0] == (POST_DISCOUNT_USD, "US-CA")


def test_build_invoice_calls_currency_convert_and_format(monkeypatch):
    convert_calls = []
    format_calls = []
    real_convert = currency.convert
    real_format = currency.format_currency

    def convert_spy(amount, to_currency):
        convert_calls.append((amount, to_currency))
        return real_convert(amount, to_currency)

    def format_spy(amount, currency_code):
        format_calls.append((amount, currency_code))
        return real_format(amount, currency_code)

    monkeypatch.setattr(currency, "convert", convert_spy)
    monkeypatch.setattr(currency, "format_currency", format_spy)
    build_invoice(base_order())
    assert len(convert_calls) == 1
    assert convert_calls[0][1] == "USD"
    assert len(format_calls) == 1
    assert format_calls[0][1] == "USD"


def test_build_invoice_no_loyalty_keys_does_not_call_redeem(monkeypatch):
    import loyalty

    calls = []
    monkeypatch.setattr(
        loyalty, "redeem_loyalty_points",
        lambda *a, **k: calls.append((a, k)),
    )
    build_invoice(base_order())
    assert calls == []

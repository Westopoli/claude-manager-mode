"""Tests for src/pricing_engine.py (leaf-G2).

Covers: catalog/discounts/engine (G1 baseline), validation, currency,
shipping, notifications (E2+/E3+ per MODULES.md), and the G2+ order
lifecycle state machine from ../SPEC.md.

Coupon-order contradiction: this file's source seeds two contradictory
comment blocks for the order in which stack_discounts applies
coupon/volume/membership (same deliberate contradiction present in every
prior phase rung). This test pins ONE resolution: coupon-first, then
volume, then membership -- the tiebreaker precedent already used at
phaseE-leaf-ceiling-v2/rungs/E3/discounts.py, which resolved the same
contradiction the same way for the same function (matched scope: the
function computing the stack IS stack_discounts, and discounts.py's own
docstring/description states coupon-first). The numeric case below
actually discriminates: coupon-first and coupon-last give different
final cents due to apply_coupon's internal rounding happening at a
different point in the multiplication chain, not just different code
paths that coincidentally agree.
"""
import pytest

import pricing_engine as pe


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fresh_order(**overrides):
    order = {
        "items": [{"sku": "widget", "qty": 2}],
        "region": "US-CA",
        "membership_tier": "gold",
        "currency": "USD",
    }
    order.update(overrides)
    return order


# ---------------------------------------------------------------------------
# catalog.py / build_line_items (G1 baseline)
# ---------------------------------------------------------------------------

def test_catalog_contents():
    assert pe.CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert pe.CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert pe.CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_build_line_items_basic():
    per_sku, subtotal, total_qty = pe.build_line_items(
        [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    )
    assert per_sku == {"widget": 29.97, "gadget": 49.00}
    assert subtotal == 78.97
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        pe.build_line_items([{"sku": "nope", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        pe.build_line_items([{"sku": "gadget", "qty": 6}])


# ---------------------------------------------------------------------------
# discounts.py (G1 baseline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "qty,expected",
    [(1, 0.0), (9, 0.0), (10, 0.05), (49, 0.05), (50, 0.10), (100, 0.10)],
)
def test_volume_discount_rate(qty, expected):
    assert pe.volume_discount_rate(qty) == expected


@pytest.mark.parametrize(
    "tier,expected",
    [("none", 0.0), ("silver", 0.03), ("gold", 0.07), ("platinum", 0.12)],
)
def test_membership_discount_rate(tier, expected):
    assert pe.membership_discount_rate(tier) == expected


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        pe.membership_discount_rate("bogus")


def test_coupons_dict():
    assert pe.COUPONS["SAVE10"] == {
        "rate": 0.10,
        "min_spend": 50.0,
        "expired": False,
    }


def test_apply_coupon_valid():
    assert pe.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        pe.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_at_min_spend_does_not_raise():
    assert pe.apply_coupon(50.0, "SAVE10") == 45.0


def test_apply_coupon_expired_raises(monkeypatch):
    coupons_copy = {k: dict(v) for k, v in pe.COUPONS.items()}
    coupons_copy["SAVE10"]["expired"] = True
    monkeypatch.setattr(pe, "COUPONS", coupons_copy)
    with pytest.raises(ValueError):
        pe.apply_coupon(100.0, "SAVE10")


# ---------------------------------------------------------------------------
# coupon-order contradiction: pinned numeric discriminator
# ---------------------------------------------------------------------------

def test_stack_discounts_pins_coupon_first_order():
    # subtotal=123.45, total_qty=10 (volume rate 0.05), tier=gold (0.07),
    # coupon SAVE10 (rate 0.10).
    #   coupon-first-then-volume-then-membership (pinned):
    #     round(123.45*0.90, 2) = 111.11
    #     111.11 * 0.95 = 105.5545
    #     105.5545 * 0.93 = 98.165685 -> round = 98.17
    #   volume-then-membership-then-coupon-last (rejected resolution):
    #     123.45 * 0.95 * 0.93 = 109.0864...
    #     round(109.0864... * 0.90, 2) = 98.16
    # These differ (98.17 vs 98.16) because apply_coupon's internal
    # round() lands at a different point in the chain depending on order.
    result = pe.stack_discounts(123.45, 10, "gold", "SAVE10")
    assert result == 98.17


def test_stack_discounts_no_coupon_still_applies_volume_and_membership():
    # subtotal=1000, qty=50 (volume 0.10), tier=platinum (0.12), no coupon.
    result = pe.stack_discounts(1000.0, 50, "platinum", None)
    assert result == round(1000.0 * 0.90 * 0.88, 2)


# ---------------------------------------------------------------------------
# validation.py (E2+)
# ---------------------------------------------------------------------------

def test_validate_order_valid_passes():
    order = fresh_order()
    pe.validate_order(order)  # must not raise


def test_validate_order_missing_items_raises_naming_field():
    order = fresh_order()
    del order["items"]
    with pytest.raises(ValueError, match="items"):
        pe.validate_order(order)


def test_validate_order_empty_items_raises_naming_field():
    order = fresh_order(items=[])
    with pytest.raises(ValueError, match="items"):
        pe.validate_order(order)


def test_validate_order_wrong_type_items_raises_naming_field():
    order = fresh_order(items="not-a-list")
    with pytest.raises(ValueError, match="items"):
        pe.validate_order(order)


def test_validate_order_missing_region_raises_naming_field():
    order = fresh_order()
    del order["region"]
    with pytest.raises(ValueError, match="region"):
        pe.validate_order(order)


def test_validate_order_missing_membership_tier_raises_naming_field():
    order = fresh_order()
    del order["membership_tier"]
    with pytest.raises(ValueError, match="membership_tier"):
        pe.validate_order(order)


def test_validate_order_missing_currency_raises_naming_field():
    order = fresh_order()
    del order["currency"]
    with pytest.raises(ValueError, match="currency"):
        pe.validate_order(order)


# ---------------------------------------------------------------------------
# currency.py (E2+)
# ---------------------------------------------------------------------------

def test_exchange_rates():
    assert pe.EXCHANGE_RATES == {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def test_convert_usd_identity():
    assert pe.convert(100.0, "USD") == 100.0


def test_convert_eur():
    assert pe.convert(100.0, "EUR") == 92.0


def test_convert_gbp():
    assert pe.convert(100.0, "GBP") == 79.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        pe.convert(100.0, "XYZ")


@pytest.mark.parametrize(
    "currency,expected",
    [("USD", "$12.30"), ("EUR", "€12.30"), ("GBP", "£12.30")],
)
def test_format_currency(currency, expected):
    assert pe.format_currency(12.3, currency) == expected


# ---------------------------------------------------------------------------
# shipping.py (E3+)
# ---------------------------------------------------------------------------

def test_shipping_cost_standard():
    # base = round(2.5 + 0.4*2 + 0.05*10, 2) = round(2.5+0.8+0.5,2) = 3.80
    assert pe.shipping_cost(2.0, 10.0, False) == 3.80


def test_shipping_cost_express_multiplies_by_1_5():
    base = round(2.5 + 0.4 * 2.0 + 0.05 * 10.0, 2)
    assert pe.shipping_cost(2.0, 10.0, True) == round(base * 1.5, 2)


def test_shipping_cost_nonpositive_weight_raises():
    with pytest.raises(ValueError):
        pe.shipping_cost(0.0, 10.0, False)


def test_shipping_cost_nonpositive_distance_raises():
    with pytest.raises(ValueError):
        pe.shipping_cost(2.0, -1.0, False)


# ---------------------------------------------------------------------------
# notifications.py (E3+) -- low_stock_alert is a standalone utility, never
# called by build_invoice (per brief). Ordinary state-check test only.
# ---------------------------------------------------------------------------

def test_low_stock_alert_returns_sorted_skus_below_threshold():
    catalog = {
        "a": {"unit_price": 1.0, "stock": 2},
        "b": {"unit_price": 1.0, "stock": 10},
        "c": {"unit_price": 1.0, "stock": 0},
    }
    assert pe.low_stock_alert(catalog, 5) == ["a", "c"]


def test_low_stock_alert_against_module_catalog():
    # widget=100, gadget=5, gizmo=0; threshold=6 -> gadget and gizmo qualify.
    assert pe.low_stock_alert(pe.CATALOG, 6) == ["gadget", "gizmo"]


def test_low_stock_alert_no_matches_returns_empty_list():
    catalog = {"a": {"unit_price": 1.0, "stock": 50}}
    assert pe.low_stock_alert(catalog, 5) == []


# ---------------------------------------------------------------------------
# engine.py / build_invoice (G1 baseline, contradiction re-confirmed here)
# ---------------------------------------------------------------------------

def test_build_invoice_returns_post_discount_amount_and_total():
    order = fresh_order(items=[{"sku": "widget", "qty": 2}])
    pe.validate_order(order)
    invoice = pe.build_invoice(order)
    assert "post_discount_amount" in invoice
    assert "total" in invoice
    assert order["state"] == "priced"


def test_build_invoice_pins_coupon_first_order():
    # items: gadget x3 + widget x7 -> subtotal = 73.50 + 69.93 = 143.43,
    # total_qty=10 (volume rate 0.05), tier="none" (membership rate 0.0),
    # coupon SAVE10.
    #   coupon-first (pinned): round(143.43*0.90,2)=129.09; *0.95=122.6355
    #     -> round = 122.64
    #   coupon-last (rejected): 143.43*0.95=136.2585; round(*0.90,2)=122.63
    order = fresh_order(
        items=[{"sku": "gadget", "qty": 3}, {"sku": "widget", "qty": 7}],
        membership_tier="none",
        coupon_code="SAVE10",
    )
    pe.validate_order(order)
    invoice = pe.build_invoice(order)
    assert invoice["post_discount_amount"] == 122.64


# ---------------------------------------------------------------------------
# G2+: order lifecycle state machine
# ---------------------------------------------------------------------------

def test_order_state_defaults_to_draft():
    order = fresh_order()
    assert order.get("state", "draft") == "draft"


def test_lifecycle_happy_path_draft_to_shipped():
    order = fresh_order(items=[{"sku": "widget", "qty": 2}])
    assert order.get("state", "draft") == "draft"

    pe.validate_order(order)
    assert order["state"] == "validated"

    invoice = pe.build_invoice(order)
    assert order["state"] == "priced"
    assert "post_discount_amount" in invoice

    confirmed = pe.confirm_order(order)
    assert order["state"] == "confirmed"
    assert confirmed is order

    shipped = pe.ship_order(order)
    assert order["state"] == "shipped"
    assert shipped is order


@pytest.mark.parametrize("bad_state", ["validated", "priced", "confirmed", "shipped"])
def test_validate_order_rejects_non_draft_state(bad_state):
    order = fresh_order(state=bad_state)
    with pytest.raises(ValueError, match="draft"):
        pe.validate_order(order)


@pytest.mark.parametrize("bad_state", ["draft", "priced", "confirmed", "shipped"])
def test_build_invoice_pricing_rejects_non_validated_state(bad_state):
    order = fresh_order(items=[{"sku": "widget", "qty": 2}], state=bad_state)
    with pytest.raises(ValueError, match="validated"):
        pe.build_invoice(order)


@pytest.mark.parametrize("bad_state", ["draft", "validated", "confirmed", "shipped"])
def test_confirm_order_rejects_non_priced_state(bad_state):
    order = fresh_order(state=bad_state)
    with pytest.raises(ValueError, match="priced"):
        pe.confirm_order(order)


@pytest.mark.parametrize("bad_state", ["draft", "validated", "priced", "shipped"])
def test_ship_order_rejects_non_confirmed_state(bad_state):
    order = fresh_order(state=bad_state)
    with pytest.raises(ValueError, match="confirmed"):
        pe.ship_order(order)

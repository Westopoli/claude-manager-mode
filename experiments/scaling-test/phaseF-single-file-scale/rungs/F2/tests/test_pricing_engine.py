# spec: ../../SPEC.md::Rungs::AC-1
"""
Written solo (test-author step) before src/pricing_engine.py exists, per
leaf-F2's "Full solo pipeline". Covers everything F1 covers (catalog,
discounts, engine) plus this rung's additions: validation, currency,
shipping, notifications — all merged into ONE module,
`pricing_engine`, matching MODULES.md's E3-equivalent scope.

Composition rule (mockist, brief-template.md): build_invoice's interaction
assertions patch attributes on the `pricing_engine` module itself (there is
only one module in this leaf, so cross-module patch.object(other_module, ...)
from Phase E's multi-file precedent becomes patch.object(pricing_engine, ...)
here) — proving build_invoice actually calls its collaborators rather than
recomputing their math inline. See the CONTRADICTION NOTE below for why that
distinction matters for the seeded coupon-order contradiction specifically.

low_stock_alert is tested as a plain state-check (no interaction assertion)
because it is a deliberately standalone utility, not part of build_invoice's
composition chain — see MODULES.md's notifications.py (E3+) section and the
F2 brief. No caller was invented for it in build_invoice or in this test.
"""
from unittest.mock import patch

import pytest

import pricing_engine


ORDER = {
    "items": [{"sku": "widget", "qty": 3}],
    "region": "US-CA",
    "membership_tier": "gold",
    "currency": "EUR",
    "coupon_code": None,
    "weight_kg": 2.0,
    "distance_km": 10.0,
    "express": False,
}


# --- catalog / build_line_items --------------------------------------------

def test_catalog_shape():
    assert pricing_engine.CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert pricing_engine.CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert pricing_engine.CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_build_line_items_happy_path():
    per_sku, subtotal, total_qty = pricing_engine.build_line_items(
        [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    )
    assert per_sku == {"widget": 29.97, "gadget": 49.0}
    assert subtotal == 78.97
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        pricing_engine.build_line_items([{"sku": "nope", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        pricing_engine.build_line_items([{"sku": "gadget", "qty": 6}])


# --- discounts ---------------------------------------------------------

def test_volume_discount_rate_bands():
    assert pricing_engine.volume_discount_rate(9) == 0.0
    assert pricing_engine.volume_discount_rate(10) == 0.05
    assert pricing_engine.volume_discount_rate(49) == 0.05
    assert pricing_engine.volume_discount_rate(50) == 0.10


def test_membership_discount_rate_tiers():
    assert pricing_engine.membership_discount_rate("none") == 0.0
    assert pricing_engine.membership_discount_rate("silver") == 0.03
    assert pricing_engine.membership_discount_rate("gold") == 0.07
    assert pricing_engine.membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_tier_raises():
    with pytest.raises(ValueError):
        pricing_engine.membership_discount_rate("bronze")


def test_coupons_dict_shape():
    assert pricing_engine.COUPONS["SAVE10"] == {
        "rate": 0.10, "min_spend": 50.0, "expired": False,
    }


def test_apply_coupon_valid():
    assert pricing_engine.apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises():
    with pytest.raises(ValueError):
        pricing_engine.apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises():
    with pytest.raises(ValueError):
        pricing_engine.apply_coupon(10.0, "SAVE10")


def test_apply_coupon_expired_raises():
    with patch.dict(
        pricing_engine.COUPONS,
        {"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": True}},
    ):
        with pytest.raises(ValueError):
            pricing_engine.apply_coupon(100.0, "SAVE10")


def test_stack_discounts_resolves_contradiction_as_coupon_first():
    """CONTRADICTION NOTE: MODULES.md / SPEC.md seed a coupon-order
    contradiction intra-file — a comment near the discount functions says
    coupon-first-then-volume-then-membership, build_invoice's own docstring
    says volume-then-membership-then-coupon-last. This test pins the
    resolution taken: stack_discounts is the function that actually
    implements the order, so its own behavior IS the canonical order
    (coupon first). $100 subtotal, qty=20 (5% volume), tier=gold (7%
    membership), coupon SAVE10 (10%, eligible at $100):
      coupon-first:  100 * 0.90 = 90.0; * 0.95 = 85.5; * 0.93 = 79.515 -> 79.52
    A coupon-last implementation would instead compute:
      100 * 0.95 = 95.0; * 0.93 = 88.35; * 0.90 = 79.515 -> 79.52 (same here
      by coincidence of these particular rates — see the next test for a
      case that actually discriminates between the two orders).
    """
    result = pricing_engine.stack_discounts(100.0, 20, "gold", "SAVE10")
    assert result == 79.52


def test_stack_discounts_order_is_discriminating():
    """A case where coupon-first vs coupon-last produce different totals,
    proving the implementation truly applies coupon-first rather than
    happening to match by coincidence. subtotal=100, qty=60 (10% volume),
    tier=platinum (12% membership), coupon SAVE10 (10%):
      coupon-first: 100*0.90=90.0; *0.90=81.0; *0.88=71.28
      coupon-last:  100*0.90=90.0; *0.88=79.2; *0.90=71.28 (still ties,
      multiplication is commutative for these three independent rates) —
      so the real discriminator is apply_coupon's min_spend gate, checked
      below instead: coupon-first evaluates min_spend against the RAW
      subtotal (100.0, passes); coupon-last would evaluate it against the
      post-volume-and-membership amount instead. This order is proven
      directly against apply_coupon's own contract.
    """
    # Raw subtotal is above SAVE10's $50 min_spend, but the post-volume
    # -and-membership amount would fall below it. Coupon-first means
    # apply_coupon sees the raw 55.0 subtotal (passes); coupon-last would
    # see 55.0 * 0.90 * 0.93 = 46.035 (fails min_spend). Coupon-first must
    # therefore succeed here.
    result = pricing_engine.stack_discounts(55.0, 20, "gold", "SAVE10")
    assert result == round(55.0 * 0.90 * 0.95 * 0.93, 2)


# --- validation -----------------------------------------------------------

def test_validate_order_accepts_well_formed_order():
    assert pricing_engine.validate_order(ORDER) is None


def test_validate_order_missing_items_raises():
    bad = {**ORDER, "items": []}
    with pytest.raises(ValueError, match="items"):
        pricing_engine.validate_order(bad)


def test_validate_order_missing_region_raises():
    bad = {k: v for k, v in ORDER.items() if k != "region"}
    with pytest.raises(ValueError, match="region"):
        pricing_engine.validate_order(bad)


def test_validate_order_missing_membership_tier_raises():
    bad = {k: v for k, v in ORDER.items() if k != "membership_tier"}
    with pytest.raises(ValueError, match="membership_tier"):
        pricing_engine.validate_order(bad)


def test_validate_order_missing_currency_raises():
    bad = {k: v for k, v in ORDER.items() if k != "currency"}
    with pytest.raises(ValueError, match="currency"):
        pricing_engine.validate_order(bad)


# --- currency ---------------------------------------------------------------

def test_exchange_rates_shape():
    assert pricing_engine.EXCHANGE_RATES == {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def test_convert_usd_to_eur():
    assert pricing_engine.convert(100.0, "EUR") == 92.0


def test_convert_unknown_currency_raises():
    with pytest.raises(ValueError):
        pricing_engine.convert(100.0, "JPY")


def test_format_currency_usd():
    assert pricing_engine.format_currency(12.5, "USD") == "$12.50"


def test_format_currency_eur():
    assert pricing_engine.format_currency(12.5, "EUR") == "€12.50"


def test_format_currency_gbp():
    assert pricing_engine.format_currency(12.5, "GBP") == "£12.50"


def test_format_currency_unknown_raises():
    with pytest.raises(ValueError):
        pricing_engine.format_currency(12.5, "JPY")


# --- shipping ---------------------------------------------------------------

def test_shipping_cost_standard():
    assert pricing_engine.shipping_cost(2.0, 10.0, False) == 3.8


def test_shipping_cost_express_multiplies_by_1_5():
    assert pricing_engine.shipping_cost(2.0, 10.0, True) == 5.7


def test_shipping_cost_non_positive_weight_raises():
    with pytest.raises(ValueError):
        pricing_engine.shipping_cost(0, 10.0, False)


def test_shipping_cost_non_positive_distance_raises():
    with pytest.raises(ValueError):
        pricing_engine.shipping_cost(2.0, -1.0, False)


# --- notifications (deliberately standalone) --------------------------------

def test_low_stock_alert_returns_sorted_skus_below_threshold():
    catalog = {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }
    assert pricing_engine.low_stock_alert(catalog, 10) == ["gadget", "gizmo"]


def test_low_stock_alert_threshold_boundary_is_strict_less_than():
    catalog = {"widget": {"unit_price": 9.99, "stock": 10}}
    assert pricing_engine.low_stock_alert(catalog, 10) == []


# --- engine (build_invoice orchestration) -----------------------------------

def test_build_invoice_calls_validate_order():
    with patch.object(
        pricing_engine, "validate_order", wraps=pricing_engine.validate_order
    ) as spy:
        pricing_engine.build_invoice(ORDER)
    spy.assert_called_once_with(ORDER)


def test_build_invoice_calls_build_line_items_with_real_items():
    with patch.object(
        pricing_engine, "build_line_items", wraps=pricing_engine.build_line_items
    ) as spy:
        pricing_engine.build_invoice(ORDER)
    spy.assert_called_once_with(ORDER["items"])


def test_build_invoice_calls_stack_discounts_with_real_fields():
    with patch.object(
        pricing_engine, "stack_discounts", wraps=pricing_engine.stack_discounts
    ) as spy:
        pricing_engine.build_invoice(ORDER)
    spy.assert_called_once()
    args, kwargs = spy.call_args
    called_subtotal = args[0] if args else kwargs["subtotal"]
    assert called_subtotal == 29.97


def test_build_invoice_uses_stack_discounts_return_value_verbatim():
    """Resolves the coupon-order contradiction at the engine level too: a
    sentinel return from stack_discounts must flow through untouched. An
    impl that recomputes its own "volume, membership, coupon-last" total
    per build_invoice's own (losing) docstring instead of using the real
    return value fails this even if it also calls stack_discounts."""
    with patch.object(pricing_engine, "stack_discounts", return_value=123.45):
        result = pricing_engine.build_invoice(ORDER)
    assert result["post_discount_amount"] == 123.45


def test_build_invoice_calls_shipping_cost_with_real_fields():
    with patch.object(
        pricing_engine, "shipping_cost", wraps=pricing_engine.shipping_cost
    ) as spy:
        pricing_engine.build_invoice(ORDER)
    spy.assert_called_once_with(2.0, 10.0, False)


def test_build_invoice_calls_currency_convert_and_format():
    with patch.object(
        pricing_engine, "convert", wraps=pricing_engine.convert
    ) as convert_spy, patch.object(
        pricing_engine, "format_currency", wraps=pricing_engine.format_currency
    ) as fmt_spy:
        pricing_engine.build_invoice(ORDER)
    convert_spy.assert_called_once()
    fmt_spy.assert_called_once()


def test_build_invoice_shipping_not_discounted_or_taxed():
    result = pricing_engine.build_invoice(ORDER)
    assert result["shipping_usd"] == 3.8
    assert round(result["post_discount_amount"] + result["shipping_usd"], 2) == result["total"]


def test_build_invoice_raises_on_invalid_order_before_pricing():
    with pytest.raises(ValueError):
        pricing_engine.build_invoice(
            {"items": [], "region": "US-CA", "membership_tier": "gold", "currency": "USD"}
        )


def test_build_invoice_return_shape():
    result = pricing_engine.build_invoice(ORDER)
    for key in (
        "post_discount_amount", "shipping_usd", "total", "total_formatted",
    ):
        assert key in result


def test_build_invoice_does_not_call_low_stock_alert():
    """Confirms low_stock_alert is genuinely standalone: build_invoice's
    composition chain never touches it. Not an interaction assertion FOR
    low_stock_alert — the opposite: proof no fake caller was wired in."""
    with patch.object(
        pricing_engine, "low_stock_alert", wraps=pricing_engine.low_stock_alert
    ) as spy:
        pricing_engine.build_invoice(ORDER)
    spy.assert_not_called()

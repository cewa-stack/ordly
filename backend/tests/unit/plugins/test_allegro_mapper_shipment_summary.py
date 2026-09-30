"""
Mapowanie `fulfillment.shipmentSummary.lineItemsSent` i niepełnych
odpowiedzi checkout-formu - kształt 1:1 ze schematem `CheckoutForm`
w oficjalnym swagger.yaml Allegro (CheckoutFormFulfillment ->
shipmentSummary -> lineItemsSent: NONE | SOME | ALL).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import SchedulerSettings
from app.infrastructure.plugins.allegro.mapper import map_checkout_form_to_order

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "allegro_responses"


def _raw() -> dict:
    return json.loads((_FIXTURES_DIR / "checkout_form_sample.json").read_text())


class TestShipmentSummary:
    def test_czyta_line_items_sent(self):
        raw = _raw()
        raw["fulfillment"] = {
            "status": "NEW",
            "shipmentSummary": {"lineItemsSent": "ALL"},
            "provider": {"id": "SELLER"},
        }

        order = map_checkout_form_to_order(raw)

        assert order.fulfillment_status == "NEW"
        assert order.line_items_sent == "ALL"

    def test_brak_shipment_summary_to_none(self):
        raw = _raw()
        raw["fulfillment"] = {"status": "PROCESSING"}

        assert map_checkout_form_to_order(raw).line_items_sent is None

    def test_brak_statusu_i_fulfillment_to_wartosci_nieznane(self):
        raw = _raw()
        raw.pop("status", None)
        raw.pop("fulfillment", None)

        order = map_checkout_form_to_order(raw)

        assert order.status == "UNKNOWN"
        assert order.fulfillment_status is None
        assert order.line_items_sent is None


def test_numery_przesylek_domyslnie_sprawdzane_co_minute(monkeypatch):
    monkeypatch.delenv("CHECK_WAYBILLS_INTERVAL_SECONDS", raising=False)
    settings = SchedulerSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.check_waybills_interval_seconds == 60

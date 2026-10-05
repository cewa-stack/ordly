"""
Testy HTTP `/api/v1/hub/wholesale/*` - kontrakt z aplikacją desktopową.

Desktop wysyła hurtownie i szablony dokładnie w formacie swoich plików
(`wholesalers.json`, `wholesaler_templates.json`: camelCase), więc test
pilnuje, że ten format przechodzi bez przeróbek, a zły adres hurtowni
jest odrzucany już tutaj - zanim trafi do maila z Huba.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container
from app.api.endpoints import hub_wholesale as endpoints
from app.api.errors import register_exception_handlers
from app.repositories.sqlite_hub_wholesale_repository import HubWholesaleOrder

DESKTOP_CATALOG: dict[str, Any] = {
    "wholesalers": [
        {
            "id": "0b6c2f1e-1111-4c7a-9d55-111111111111",
            "name": "Hurt-Pol",
            "email": "zamowienia@hurtpol.example",
            "contactPerson": "Panie Marku",
            "items": [{"name": "Kubek 300 ml", "quantity": 24}],
            "templateId": "tpl-std",
        },
        {
            "id": "0b6c2f1e-2222-4c7a-9d55-222222222222",
            "name": "Bez osoby",
            "email": "biuro@bez.example",
            "items": [],
        },
    ],
    "templates": [
        {
            "id": "tpl-std",
            "name": "Standardowe zamówienie",
            "subject": "Zamówienie - {produkty}",
            "body": "{lista_pozycji}",
            "inquirySubject": "Zapytanie",
            "inquiryBody": "Dzień dobry",
            "isDefault": True,
        }
    ],
}


class _StubWholesale:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def save_catalog(self, payload: dict[str, Any]) -> str:
        self.saved.append(payload)
        return "abc123"

    async def list_sent_orders(self, limit: int) -> list[HubWholesaleOrder]:
        return [
            HubWholesaleOrder(
                request_id="r1",
                wholesaler_id="w1",
                wholesaler_name="Hurt-Pol",
                to_email="zamowienia@hurtpol.example",
                subject="Zamówienie - Kubek",
                items_summary="Kubek x24",
                items_key="k",
                test_mode=False,
                status="sent",
                error=None,
                sent_at=datetime(2026, 10, 6, 6, 30),
                created_at=datetime(2026, 10, 6, 6, 30),
            )
        ][:limit]


class _StubContainer:
    def __init__(self) -> None:
        self.hub_wholesale = _StubWholesale()


@pytest.fixture
def container() -> _StubContainer:
    return _StubContainer()


@pytest.fixture
def client(container: _StubContainer) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as test_client:
        yield test_client


class TestKatalog:
    def test_format_plikow_desktopu_przechodzi_bez_zmian(
        self, client: TestClient, container: _StubContainer
    ):
        response = client.put("/api/v1/hub/wholesale/catalog", json=DESKTOP_CATALOG)

        assert response.status_code == 200
        assert response.json() == {"version": "abc123", "wholesalers": 2, "templates": 1}
        [saved] = container.hub_wholesale.saved
        assert saved["wholesalers"][0]["contactPerson"] == "Panie Marku"
        assert saved["wholesalers"][0]["templateId"] == "tpl-std"
        assert "templateId" not in saved["wholesalers"][1]
        assert saved["templates"][0]["inquiryBody"] == "Dzień dobry"

    @pytest.mark.parametrize("email", ["bez-malpy", "ktos@", "ktos@localhost"])
    def test_zly_adres_hurtowni_odrzucony(
        self, client: TestClient, container: _StubContainer, email: str
    ):
        bad = {
            **DESKTOP_CATALOG,
            "wholesalers": [{**DESKTOP_CATALOG["wholesalers"][0], "email": email}],
        }

        response = client.put("/api/v1/hub/wholesale/catalog", json=bad)

        assert response.status_code == 422
        assert container.hub_wholesale.saved == []

    def test_ilosc_ponizej_jednej_odrzucona(self, client: TestClient):
        bad = {
            **DESKTOP_CATALOG,
            "wholesalers": [
                {**DESKTOP_CATALOG["wholesalers"][0], "items": [{"name": "X", "quantity": 0}]}
            ],
        }

        assert client.put("/api/v1/hub/wholesale/catalog", json=bad).status_code == 422


class TestHistoria:
    def test_wyslane_z_huba_z_czasem_utc(self, client: TestClient):
        response = client.get("/api/v1/hub/wholesale/orders?limit=5")

        assert response.status_code == 200
        [order] = response.json()
        assert order["wholesaler_name"] == "Hurt-Pol"
        assert order["items_summary"] == "Kubek x24"
        assert order["sent_at"].startswith("2026-10-06T06:30:00")
        assert order["sent_at"].endswith(("Z", "+00:00"))

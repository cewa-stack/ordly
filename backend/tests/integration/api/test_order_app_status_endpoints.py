"""
Testy HTTP `POST /api/v1/orders/{id}/app-status` i historii statusu.

Kontrakt dla desktopu i telefonu: pola `app_status`, `app_status_label`,
`app_status_manual`, `app_status_changed_at` w `OrderOut`, `null` jako
"Przywróć status z Allegro" i 422 dla statusu spoza czterech z Notion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import orders as orders_endpoints
from app.api.errors import register_exception_handlers
from app.services.order_status_service import OrderStatusService
from tests.fakes.fake_order_repository import FakeOrderRepository


class _StubContainer:
    def __init__(self, repository: FakeOrderRepository) -> None:
        self.repository = repository

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[None]:
        yield None

    def order_status_service(self, _session=None) -> OrderStatusService:
        return OrderStatusService(self.repository)


@pytest.fixture
def repository(sample_order) -> FakeOrderRepository:
    repo = FakeOrderRepository()
    repo._orders.append(  # noqa: SLF001 - ziarno testowe
        replace(sample_order, status="READY_FOR_PROCESSING", fulfillment_status="NEW")
    )
    return repo


@pytest.fixture
def client(repository: FakeOrderRepository) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(orders_endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    container = _StubContainer(repository)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


class TestRecznyStatus:
    def test_ustawienie_statusu(self, client: TestClient, sample_order):
        response = client.post(
            f"/api/v1/orders/{sample_order.external_id}/app-status", json={"status": "DONE"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["app_status"] == "DONE"
        assert body["app_status_label"] == "Zrealizowane"
        assert body["app_status_manual"] is True
        assert body["app_status_changed_at"].endswith("Z")
        assert body["requires_packing"] is False
        # Etap z Allegro zostaje nietknięty.
        assert body["fulfillment_status"] == "NEW"

    def test_przywrocenie_z_allegro_i_historia(self, client: TestClient, sample_order):
        url = f"/api/v1/orders/{sample_order.external_id}/app-status"
        client.post(url, json={"status": "IN_PROGRESS"})

        restored = client.post(url, json={"status": None}).json()
        history = client.get(f"{url}/history").json()

        assert restored["app_status"] == "NEW"
        assert restored["app_status_manual"] is False
        assert [h["source"] for h in history] == ["restore_allegro", "manual"]
        assert history[1]["previous_label"] == "Nowe"
        assert history[1]["new_label"] == "W realizacji"

    def test_status_spoza_listy_to_422(self, client: TestClient, sample_order):
        response = client.post(
            f"/api/v1/orders/{sample_order.external_id}/app-status", json={"status": "SENT"}
        )
        assert response.status_code == 422

    def test_nieznane_zamowienie_to_404(self, client: TestClient):
        response = client.post("/api/v1/orders/BRAK/app-status", json={"status": "DONE"})
        assert response.status_code == 404

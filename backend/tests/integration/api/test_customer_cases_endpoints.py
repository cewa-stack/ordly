"""
Testy HTTP `/api/v1/customer-cases` - kontrakt dla desktopu i telefonu:
etykiety po polsku, puste pola jako null ("nieuzupełnione"), filtry,
PATCH powodu i statusu obsługi, 404 i 422.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import customer_cases as endpoints
from app.api.errors import register_exception_handlers
from app.domain.customer_cases import CustomerCase
from app.services.customer_case_service import CustomerCaseService
from tests.fakes.fake_customer_case_repository import FakeCustomerCaseRepository
from tests.fakes.fake_order_repository import FakeOrderRepository


class _StubContainer:
    def __init__(self) -> None:
        self.cases = FakeCustomerCaseRepository()
        self.orders = FakeOrderRepository()

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[None]:
        yield None

    def customer_case_service(self, _session=None) -> CustomerCaseService:
        return CustomerCaseService(self.cases, self.orders)


@pytest.fixture
def container() -> _StubContainer:
    return _StubContainer()


@pytest.fixture
def client(container: _StubContainer) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


def _seed(container: _StubContainer) -> None:
    import asyncio

    async def go() -> None:
        await container.cases.add(
            CustomerCase(
                marketplace="allegro",
                order_external_id="ORD-1",
                allegro_order_id="ORD-1",
                kind="CANCELLATION",
                source="ALLEGRO_ORDER",
                buyer_login="anna_k",
                cancelled_at=datetime(2026, 9, 10),
            )
        )
        await container.cases.add(
            CustomerCase(
                marketplace="allegro",
                order_external_id="ORD-2",
                kind="REFUND",
                source="ALLEGRO_RETURN",
                reason="OUT_OF_STOCK",
            )
        )

    asyncio.run(go())


class TestLista:
    def test_rekord_z_etykietami_i_nieuzupelnionymi_polami(self, client, container):
        _seed(container)

        body = client.get("/api/v1/customer-cases").json()

        assert [c["order_external_id"] for c in body] == ["ORD-2", "ORD-1"]
        first = body[1]
        assert first["kind_label"] == "Anulowanie zamówienia"
        assert first["reason"] is None and first["reason_label"] == "nieuzupełnione"
        assert first["handling_label"] == "Zgłoszony"
        assert first["source_label"] == "Allegro - anulowanie zamówienia"
        assert first["cancelled_at"] == "2026-09-10T00:00:00.000Z"
        assert "buyer_email" not in first and "buyer_phone" not in first

    def test_filtry(self, client, container):
        _seed(container)

        def ids(query: str) -> list[str]:
            return [c["order_external_id"] for c in client.get(f"/api/v1/customer-cases?{query}").json()]

        assert ids("reason=OUT_OF_STOCK") == ["ORD-2"]
        assert ids("reason=MISSING") == ["ORD-1"]
        assert ids("kind=CANCELLATION&kind=BOTH") == ["ORD-1"]
        assert ids("source=ALLEGRO_RETURN") == ["ORD-2"]
        assert client.get("/api/v1/customer-cases?reason=COKOLWIEK").status_code == 422


class TestEdycja:
    def test_powod_status_i_historia(self, client, container):
        _seed(container)

        patched = client.patch(
            "/api/v1/customer-cases/1",
            json={"reason": "OUT_OF_STOCK", "handling_status": "IN_PROGRESS"},
        ).json()
        history = client.get("/api/v1/customer-cases/1/reason-history").json()

        assert patched["reason_label"] == "Brak towaru"
        assert patched["handling_label"] == "W trakcie realizacji"
        assert history[0]["new_label"] == "Brak towaru" and history[0]["source"] == "manual"

    def test_null_czysci_powod_a_pominiete_pole_nie(self, client, container):
        _seed(container)

        kept = client.patch("/api/v1/customer-cases/2", json={"handling_status": "DONE"}).json()
        cleared = client.patch("/api/v1/customer-cases/2", json={"reason": None}).json()

        assert kept["reason"] == "OUT_OF_STOCK"
        assert cleared["reason"] is None

    def test_brak_rekordu_i_zla_wartosc(self, client, container):
        _seed(container)
        assert client.patch("/api/v1/customer-cases/99", json={"reason": "OTHER"}).status_code == 404
        assert client.patch("/api/v1/customer-cases/1", json={"reason": "ZLY"}).status_code == 422

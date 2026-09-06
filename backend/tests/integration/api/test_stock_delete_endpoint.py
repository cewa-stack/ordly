"""
Testy HTTP endpointu `DELETE /api/v1/stock/{sku}`.

Na warstwie HTTP łapie się dwie rzeczy, których nie widać w serwisie:
kolejność tras (DELETE `/stock/{sku}` sąsiaduje z DELETE
`/stock/links/...` i `/stock/offers/...`, więc źle ułożony router
kasowałby nie to, co trzeba) oraz kształt odpowiedzi - to kontrakt
potwierdzenia w aplikacji desktopowej, które musi PRZED usunięciem
powiedzieć, ile podproduktów się odwiąże i z ilu receptur produkt
wypadnie.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import stock as stock_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.inventory_item import InventoryItem
from app.services.inventory_service import InventoryService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository


class _StubContainer:
    """Kontener z magazynem w pamięci."""

    def __init__(self) -> None:
        self.inventory = FakeInventoryRepository()

    def inventory_service(self, _session=None) -> InventoryService:
        return InventoryService(self.inventory)


@pytest.fixture
def container() -> _StubContainer:
    stub = _StubContainer()
    for sku, name in [
        ("BUT10", "Butelka 10 ml"),
        ("NAK10", "Nakrętka 10 ml"),
        ("KARTON", "Karton zbiorczy"),
    ]:
        stub.inventory.items[sku] = InventoryItem(sku=sku, name=name, stock=120, min_stock=50)
    return stub


@pytest.fixture
def client(container: _StubContainer) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(stock_endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


class TestUsuwaniePozycji:
    def test_usuniecie_zwraca_podsumowanie(self, client: TestClient) -> None:
        response = client.delete("/api/v1/stock/BUT10")

        assert response.status_code == 200
        assert response.json() == {
            "sku": "BUT10",
            "name": "Butelka 10 ml",
            "stock": 120,
            "detached_sub_items": [],
            "removed_offer_links": 0,
        }

    def test_produkt_znika_z_listy(self, client: TestClient) -> None:
        client.delete("/api/v1/stock/BUT10")

        skus = [item["sku"] for item in client.get("/api/v1/stock").json()]

        assert skus == ["KARTON", "NAK10"]

    def test_podsumowanie_wymienia_odwiazane_podprodukty(self, client: TestClient) -> None:
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.delete("/api/v1/stock/BUT10")

        assert response.json()["detached_sub_items"] == ["NAK10"]
        assert client.get("/api/v1/stock/NAK10").json()["parent_sku"] is None

    def test_podsumowanie_liczy_receptury(self, client: TestClient) -> None:
        for offer in ["OFFER-1", "OFFER-2"]:
            client.post(
                "/api/v1/stock/links",
                json={"external_product_id": offer, "sku": "BUT10", "quantity": 1},
            )

        response = client.delete("/api/v1/stock/BUT10")

        assert response.json()["removed_offer_links"] == 2

    def test_nieistniejace_sku_to_404(self, client: TestClient) -> None:
        response = client.delete("/api/v1/stock/NIE-MA")

        assert response.status_code == 404

    def test_trasa_mapowan_nie_jest_przechwytywana(self, client: TestClient) -> None:
        """
        DELETE `/stock/links/...` ma dalej kasować mapowanie oferty,
        a nie produkt o SKU „links" - inaczej jedno usunięcie
        powiązania wyczyściłoby pozycję z magazynu.
        """
        client.post(
            "/api/v1/stock/links",
            json={"external_product_id": "OFFER-1", "sku": "BUT10", "quantity": 1},
        )

        response = client.delete("/api/v1/stock/links/allegro/OFFER-1")

        assert response.status_code == 200
        assert response.json() == {"removed": 1}
        assert client.get("/api/v1/stock/BUT10").status_code == 200

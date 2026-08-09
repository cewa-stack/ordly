"""
Testy HTTP endpointów `/api/v1/stock/offers/*`.

Dwie rzeczy da się złapać tylko na warstwie HTTP. Pierwsza to kolejność
tras: `/stock/offers` musi być zadeklarowane PRZED `/stock/{sku}`, bo
inaczej FastAPI potraktuje "offers" jako SKU i zwróci 404. Druga to
kształt JSON-a - to kontrakt aplikacji desktopowej, gdzie ekran
"Powiązania ofert" czyta te pola po nazwie.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import stock as stock_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.services.inventory_service import InventoryService
from app.services.offer_mapping_service import OfferMappingService
from app.utils.time import utc_now
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_order_repository import FakeOrderRepository

OFFER_ID = "16812345678"


class _StubContainer:
    """Kontener z magazynem i zamówieniami w pamięci."""

    def __init__(self) -> None:
        self.inventory = FakeInventoryRepository()
        self.orders = FakeOrderRepository()

    def inventory_service(self, _session=None) -> InventoryService:
        return InventoryService(self.inventory)

    def offer_mapping_service(self, _session=None) -> OfferMappingService:
        return OfferMappingService(self.inventory, self.orders)


@pytest.fixture
def container() -> _StubContainer:
    stub = _StubContainer()
    stub.inventory.items["PET60"] = InventoryItem(
        sku="PET60", name="Butelka PET 60 ml", stock=42, min_stock=10
    )
    stub.inventory.items["KROPL"] = InventoryItem(
        sku="KROPL", name="Kroplomierz", stock=42, min_stock=10
    )
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


async def _sell(container: _StubContainer, external_id: str, quantity: int) -> None:
    await container.orders.save(
        Order(
            external_id=external_id,
            marketplace="allegro",
            buyer=Customer(login="jan", email="jan@example.com"),
            products=[
                Product(
                    external_id=OFFER_ID,
                    name="Butelka PET 60 ml z kroplomierzem",
                    quantity=quantity,
                    unit_price=Decimal("4.90"),
                )
            ],
            total_amount=Decimal("100.00"),
            currency="PLN",
            status="NEW",
            order_date=utc_now() - timedelta(days=1),
        )
    )


def test_trasa_offers_nie_jest_lapana_jako_sku(client: TestClient) -> None:
    """Gdyby `/stock/{sku}` wyprzedzało `/stock/offers`, byłoby tu 404."""
    response = client.get("/api/v1/stock/offers")

    assert response.status_code == 200
    assert response.json() == []


def test_trasa_unmapped_nie_jest_lapana_jako_sku(client: TestClient) -> None:
    response = client.get("/api/v1/stock/offers/unmapped")

    assert response.status_code == 200


async def test_niepowiazana_oferta_ma_pelny_ksztalt_odpowiedzi(
    client: TestClient, container: _StubContainer
) -> None:
    await _sell(container, "ORDER-001", 25)
    await _sell(container, "ORDER-002", 10)

    response = client.get("/api/v1/stock/offers/unmapped")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["external_product_id"] == OFFER_ID
    assert body[0]["name"] == "Butelka PET 60 ml z kroplomierzem"
    assert body[0]["sold_quantity"] == 35
    assert body[0]["orders_count"] == 2
    assert body[0]["marketplace"] == "allegro"
    assert "last_sold_at" in body[0]


async def test_zapis_receptury_zwraca_skladniki_z_nazwami(
    client: TestClient, container: _StubContainer
) -> None:
    await _sell(container, "ORDER-001", 25)

    response = client.put(
        f"/api/v1/stock/offers/allegro/{OFFER_ID}",
        json={
            "components": [{"sku": "PET60", "quantity": 1}, {"sku": "KROPL", "quantity": 2}]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offer_name"] == "Butelka PET 60 ml z kroplomierzem"
    assert [(c["sku"], c["name"], c["quantity"]) for c in body["components"]] == [
        ("PET60", "Butelka PET 60 ml", 1),
        ("KROPL", "Kroplomierz", 2),
    ]


def test_receptura_z_nieznanym_sku_zwraca_404(client: TestClient) -> None:
    response = client.put(
        f"/api/v1/stock/offers/allegro/{OFFER_ID}",
        json={"components": [{"sku": "NIE-MA", "quantity": 1}]},
    )

    assert response.status_code == 404


def test_pusta_receptura_jest_odrzucana_przez_walidacje(client: TestClient) -> None:
    response = client.put(f"/api/v1/stock/offers/allegro/{OFFER_ID}", json={"components": []})

    assert response.status_code == 422


def test_korekta_bez_receptury_zwraca_czytelny_blad(client: TestClient) -> None:
    """422 zgodnie z `register_exception_handlers` - tam ValueError = 422."""
    response = client.get(f"/api/v1/stock/offers/allegro/{OFFER_ID}/backfill")

    assert response.status_code == 422
    assert "receptury" in response.json()["detail"]


async def test_podglad_i_wykonanie_korekty_wstecznej(
    client: TestClient, container: _StubContainer
) -> None:
    await _sell(container, "ORDER-001", 25)
    await _sell(container, "ORDER-002", 10)
    client.put(
        f"/api/v1/stock/offers/allegro/{OFFER_ID}",
        json={"components": [{"sku": "PET60", "quantity": 1}]},
    )

    preview = client.get(f"/api/v1/stock/offers/allegro/{OFFER_ID}/backfill")
    assert preview.status_code == 200
    assert preview.json()["pending_quantity"] == 35
    assert preview.json()["applied"] is False
    assert container.inventory.items["PET60"].stock == 42

    applied = client.post(f"/api/v1/stock/offers/allegro/{OFFER_ID}/backfill")
    assert applied.status_code == 200
    assert applied.json()["applied"] is True
    assert container.inventory.items["PET60"].stock == 7

    again = client.post(f"/api/v1/stock/offers/allegro/{OFFER_ID}/backfill")
    assert again.json()["pending_quantity"] == 0
    assert container.inventory.items["PET60"].stock == 7


async def test_usuniecie_receptury_zwraca_liczbe_skladnikow(
    client: TestClient, container: _StubContainer
) -> None:
    client.put(
        f"/api/v1/stock/offers/allegro/{OFFER_ID}",
        json={
            "components": [{"sku": "PET60", "quantity": 1}, {"sku": "KROPL", "quantity": 1}]
        },
    )

    response = client.delete(f"/api/v1/stock/offers/allegro/{OFFER_ID}")

    assert response.status_code == 200
    assert response.json() == {"removed": 2}

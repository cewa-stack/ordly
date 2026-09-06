"""
Testy HTTP endpointów `/api/v1/stock/catalog/*`.

Dwie rzeczy widać dopiero na warstwie HTTP.

Pierwsza to KOLEJNOŚĆ TRAS. `/stock/{sku:path}` kompiluje się do `.*`
i połyka wszystko, co stoi niżej - łącznie z `/stock/catalog`. Gdyby
trasy katalogu zjechały pod nią, `POST /stock/catalog/sync` trafiłby
w `StaticFiles` i wrócił jako 405, dokładnie tak jak kiedyś korekta
stanu dla SKU z ukośnikiem. Test wymusza więc ich wzajemne położenie.

Druga to KSZTAŁT JSON-a - kontrakt zakładki "Asortyment Allegro"
w aplikacji desktopowej, która czyta te pola po nazwie. Najważniejsze
jest `is_linked`: to na jego podstawie interfejs maluje zielone
"zdejmuje stan", więc nie może być prawdziwe dla oferty, której
sprzedaż magazynu nie rusza.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import stock as stock_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.services.inventory_service import InventoryService
from app.services.offer_catalog_service import OfferCatalogService
from app.utils.time import utc_now
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_offer_catalog_repository import FakeOfferCatalogRepository

OFFER_ID = "16812345678"


class _StubContainer:
    """Kontener z magazynem, katalogiem i pluginem w pamięci."""

    def __init__(self) -> None:
        self.inventory = FakeInventoryRepository()
        self.catalog = FakeOfferCatalogRepository()
        self.plugin = FakeMarketplacePlugin()

    def inventory_service(self, _session=None) -> InventoryService:
        return InventoryService(self.inventory)

    def offer_catalog_service(self, _session=None) -> OfferCatalogService:
        return OfferCatalogService(self.plugin, self.catalog, self.inventory)


@pytest.fixture
def container() -> _StubContainer:
    stub = _StubContainer()
    stub.inventory.items["PET60"] = InventoryItem(
        sku="PET60", name="Butelka PET 60 ml", stock=42, min_stock=10
    )
    stub.plugin.offers = [
        MarketplaceOffer(
            marketplace="allegro",
            external_id=OFFER_ID,
            name="Butelka PET 60 ml z kroplomierzem",
            signature="PET60",
            status="ACTIVE",
            available_stock=40,
            sold_count=118,
            price=Decimal("4.90"),
            image_url="https://a.allegroimg.com/original/aabbcc/butelka",
            synced_at=utc_now(),
        ),
        MarketplaceOffer(
            marketplace="allegro",
            external_id="99999999999",
            name="Zestaw startowy",
            signature=None,
            status="ACTIVE",
            available_stock=5,
            synced_at=utc_now(),
        ),
    ]
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


class TestKolejnoscTras:
    """`/stock/catalog` nie może zostać połknięte przez `/stock/{sku:path}`."""

    def test_katalog_nie_jest_traktowany_jako_sku(self, client: TestClient):
        """GET /stock/catalog trafia w katalog, nie w produkt o SKU 'catalog'."""
        response = client.get("/api/v1/stock/catalog")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_synchronizacja_odpowiada_na_post(self, client: TestClient):
        """
        POST /stock/catalog/sync musi mieć własną trasę.

        Gdyby jej brakowało, żądanie zjechałoby niżej i wróciło jako 405 -
        awaria wyglądająca w aplikacji jak "nie da się pobrać asortymentu".
        """
        response = client.post("/api/v1/stock/catalog/sync")

        assert response.status_code == 200

    def test_pozostale_trasy_katalogu_istnieja(self, client: TestClient):
        """Relink i import odpowiadają czymkolwiek innym niż 404/405."""
        assert client.post("/api/v1/stock/catalog/relink").status_code == 200
        assert (
            client.post(
                "/api/v1/stock/catalog/import", json={"external_ids": [OFFER_ID]}
            ).status_code
            == 200
        )


class TestKsztaltOdpowiedzi:
    """Kontrakt JSON dla zakładki 'Asortyment Allegro'."""

    def test_synchronizacja_zwraca_podsumowanie(self, client: TestClient):
        """Podsumowanie niesie liczby, które trafiają wprost do toastu."""
        body = client.post("/api/v1/stock/catalog/sync").json()

        assert body["marketplace"] == "allegro"
        assert body["fetched"] == 2
        # Sygnatura "PET60" trafia w istniejące SKU - dowiązanie idzie samo.
        assert body["auto_linked"] == 1
        assert body["unlinked"] == 1
        assert "synced_at" in body

    def test_oferta_katalogu_ma_wszystkie_pola_interfejsu(self, client: TestClient):
        """Brak pola po tej stronie to pusty wiersz w aplikacji."""
        client.post("/api/v1/stock/catalog/sync")

        offers = client.get("/api/v1/stock/catalog").json()
        linked = next(o for o in offers if o["external_id"] == OFFER_ID)

        assert linked["name"] == "Butelka PET 60 ml z kroplomierzem"
        assert linked["signature"] == "PET60"
        assert linked["status"] == "ACTIVE"
        assert linked["available_stock"] == 40
        assert linked["sold_count"] == 118
        # Liczba, NIE string. Gołe `Decimal` wychodzi z pydantica jako
        # "4.90", a JavaScript sklejał takie wartości zamiast je dodawać -
        # stąd dawne `NaN zł` w Statystykach. Każde pole pieniężne
        # w `schemas.py` musi być `Money`.
        assert linked["price"] == 4.90
        assert linked["image_url"].startswith("https://")
        assert linked["link_type"] == "recipe"
        assert linked["is_linked"] is True
        assert linked["components"] == [
            {"sku": "PET60", "name": "Butelka PET 60 ml", "quantity": 1}
        ]

    def test_oferta_bez_powiazania_jest_oznaczona_wprost(self, client: TestClient):
        """Oferta nieruszająca magazynu ma `is_linked: false` i pusty skład."""
        client.post("/api/v1/stock/catalog/sync")

        offers = client.get("/api/v1/stock/catalog").json()
        loose = next(o for o in offers if o["external_id"] == "99999999999")

        assert loose["link_type"] == "none"
        assert loose["is_linked"] is False
        assert loose["components"] == []

    def test_filtr_zwraca_tylko_oferty_bez_powiazania(self, client: TestClient):
        """`only_unlinked=true` zasila zakładkę 'Bez powiązania'."""
        client.post("/api/v1/stock/catalog/sync")

        offers = client.get("/api/v1/stock/catalog?only_unlinked=true").json()

        assert [o["external_id"] for o in offers] == ["99999999999"]

    def test_import_zaklada_produkt_i_zdejmuje_ostrzezenie(self, client: TestClient):
        """
        Po imporcie oferta znika z listy niepowiązanych - to jest cała
        odpowiedź na "ciągły komunikat braku powiązania".
        """
        client.post("/api/v1/stock/catalog/sync")
        assert len(client.get("/api/v1/stock/catalog?only_unlinked=true").json()) == 1

        body = client.post(
            "/api/v1/stock/catalog/import", json={"external_ids": ["99999999999"]}
        ).json()

        assert body["created"] == ["99999999999"]
        assert body["linked"] == ["99999999999"]
        assert body["skipped"] == []
        assert client.get("/api/v1/stock/catalog?only_unlinked=true").json() == []

    def test_import_bez_ofert_jest_odrzucany(self, client: TestClient):
        """Pusta lista to błąd walidacji, nie cicha operacja bez skutku."""
        response = client.post("/api/v1/stock/catalog/import", json={"external_ids": []})

        assert response.status_code == 422

    def test_awaria_allegro_wraca_jako_503(self, client: TestClient, container):
        """
        Niedostępne API marketplace to 503, a nie 500 - aplikacja pokazuje
        wtedy "spróbuj później", zamiast sugerować błąd ORDLY.
        """
        container.plugin.should_raise_offers_api_error = True

        response = client.post("/api/v1/stock/catalog/sync")

        assert response.status_code == 503

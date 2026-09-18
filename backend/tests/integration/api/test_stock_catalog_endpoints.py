"""
Testy HTTP endpointów magazynu `/api/v1/stock/*`.

Sprawdzany jest KSZTAŁT JSON-a - kontrakt ekranu Magazyn w aplikacji
mobilnej i desktopowej, które czytają te pola po nazwie. Dwa pola są
wrażliwe: `price` musi być liczbą (gołe `Decimal` wychodzi z pydantica
jako string i JavaScript sklejał takie wartości zamiast je dodawać),
a `quantity_on_hand` musi umieć być `null` - "nigdy nie liczyłem" to co
innego niż "policzyłem, nie ma".

Kolejność tras pilnuje osobno `test_stock_slash_sku.py`.
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
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.services.offer_catalog_service import OfferCatalogService
from app.utils.time import utc_now
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_offer_catalog_repository import FakeOfferCatalogRepository

OFFER_ID = "16812345678"


class _StubContainer:
    """Kontener z katalogiem ofert i pluginem w pamięci."""

    def __init__(self) -> None:
        self.catalog = FakeOfferCatalogRepository()
        self.plugin = FakeMarketplacePlugin()

    def offer_catalog_service(self, _session=None) -> OfferCatalogService:
        return OfferCatalogService(plugin=self.plugin, catalog_repository=self.catalog)


@pytest.fixture
def container() -> _StubContainer:
    stub = _StubContainer()
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


class TestSynchronizacja:
    """Przycisk synchronizacji w obu aplikacjach."""

    def test_synchronizacja_zwraca_podsumowanie(self, client: TestClient):
        """Podsumowanie niesie liczby, które trafiają wprost do toastu."""
        body = client.post("/api/v1/stock/sync").json()

        assert body["marketplace"] == "allegro"
        assert body["fetched"] == 2
        assert body["added"] == 2
        assert body["removed"] == 0
        assert "synced_at" in body

    def test_awaria_allegro_wraca_jako_503(self, client: TestClient, container):
        """
        Niedostępne API marketplace to 503, a nie 500 - aplikacja pokazuje
        wtedy "spróbuj później", zamiast sugerować błąd ORDLY.
        """
        container.plugin.should_raise_offers_api_error = True

        response = client.post("/api/v1/stock/sync")

        assert response.status_code == 503


class TestKsztaltOferty:
    """Kontrakt JSON dla listy magazynu."""

    def test_oferta_ma_wszystkie_pola_interfejsu(self, client: TestClient):
        """Brak pola po tej stronie to pusty wiersz w aplikacji."""
        client.post("/api/v1/stock/sync")

        offers = client.get("/api/v1/stock/offers").json()
        offer = next(o for o in offers if o["external_id"] == OFFER_ID)

        assert offer["marketplace"] == "allegro"
        assert offer["name"] == "Butelka PET 60 ml z kroplomierzem"
        assert offer["signature"] == "PET60"
        assert offer["status"] == "ACTIVE"
        assert offer["available_stock"] == 40
        assert offer["sold_count"] == 118
        # Liczba, NIE string. Gołe `Decimal` wychodzi z pydantica jako
        # "4.90", a JavaScript sklejał takie wartości zamiast je dodawać -
        # stąd dawne `NaN zł` w Statystykach. Każde pole pieniężne
        # w `schemas.py` musi być `Money`.
        assert offer["price"] == 4.90
        assert offer["image_url"].startswith("https://")

    def test_nigdy_nieliczona_oferta_ma_null_a_nie_zero(self, client: TestClient):
        """
        `null` znaczy "nigdy nie liczyłem", `0` znaczy "policzyłem, nie ma".
        Zamiana jednego na drugie każe człowiekowi szukać towaru, którego
        nikt nie liczył.
        """
        client.post("/api/v1/stock/sync")

        offers = client.get("/api/v1/stock/offers").json()

        assert all(o["quantity_on_hand"] is None for o in offers)


class TestRecznaIlosc:
    """Wpisywanie ilości z aplikacji desktopowej."""

    def test_zapis_ilosci_zwraca_zaktualizowana_oferte(self, client: TestClient):
        client.post("/api/v1/stock/sync")

        body = client.put(
            f"/api/v1/stock/offers/allegro/{OFFER_ID}/quantity",
            json={"quantity": 12, "reason": "Inwentaryzacja"},
        ).json()

        assert body["quantity_on_hand"] == 12
        assert body["external_id"] == OFFER_ID

    def test_ilosc_przezywa_ponowna_synchronizacje(self, client: TestClient):
        """
        Ilość nie ma źródła w API - gdyby znikała przy odświeżeniu listy,
        jedynym sposobem odtworzenia byłoby ponowne liczenie towaru.
        """
        client.post("/api/v1/stock/sync")
        client.put(
            f"/api/v1/stock/offers/allegro/{OFFER_ID}/quantity",
            json={"quantity": 12, "reason": "Inwentaryzacja"},
        )

        client.post("/api/v1/stock/sync")

        offers = client.get("/api/v1/stock/offers").json()
        assert next(o for o in offers if o["external_id"] == OFFER_ID)["quantity_on_hand"] == 12

    def test_ujemna_ilosc_jest_odrzucana(self, client: TestClient):
        """Na półce nie da się mieć mniej niż zero sztuk."""
        client.post("/api/v1/stock/sync")

        response = client.put(
            f"/api/v1/stock/offers/allegro/{OFFER_ID}/quantity",
            json={"quantity": -1, "reason": "Inwentaryzacja"},
        )

        assert response.status_code == 422

    def test_nieznana_oferta_to_404(self, client: TestClient):
        response = client.put(
            "/api/v1/stock/offers/allegro/nie-ma-takiej/quantity",
            json={"quantity": 1, "reason": "Inwentaryzacja"},
        )

        assert response.status_code == 404


class TestHistoria:
    """Historia ręcznych wpisów, czytana na ekranie desktopowym."""

    def test_historia_ma_delte_stan_koncowy_i_powod(self, client: TestClient):
        client.post("/api/v1/stock/sync")
        client.put(
            f"/api/v1/stock/offers/allegro/{OFFER_ID}/quantity",
            json={"quantity": 10, "reason": "Inwentaryzacja"},
        )
        client.put(
            f"/api/v1/stock/offers/allegro/{OFFER_ID}/quantity",
            json={"quantity": 4, "reason": "Sprzedaż na targu"},
        )

        history = client.get(f"/api/v1/stock/offers/allegro/{OFFER_ID}/history").json()

        assert [(m["change"], m["quantity_after"], m["reason"]) for m in history] == [
            (-6, 4, "Sprzedaż na targu"),
            (10, 10, "Inwentaryzacja"),
        ]
        assert history[0]["occurred_at"].endswith("Z")

    def test_limit_spoza_zakresu_jest_odrzucany(self, client: TestClient):
        client.post("/api/v1/stock/sync")

        response = client.get(f"/api/v1/stock/offers/allegro/{OFFER_ID}/history?limit=500")

        assert response.status_code == 422

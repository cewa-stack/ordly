"""
Testy HTTP dla identyfikatorów oferty z ukośnikiem, np. "OFFER/1".

Bug z 6 września 2026: zapis do zasobu, którego identyfikator zawierał
ukośnik, wracał z aplikacji desktopowej jako "Method Not Allowed".
Ukośnik trafia do URL jako `%2F`, ale serwer ASGI dekoduje ścieżkę PRZED
dopasowaniem trasy (`unquote(raw_path)` - tak samo w uvicornie i w
`TestClient`). Router widział więc `/stock/offers/allegro/OFFER/1/quantity`,
nie dopasowywał żadnej trasy i żądanie spadało do `StaticFiles("/")`
serwującego PWA, a ten na PUT odpowiada `405 Method Not Allowed`.

Dlatego aplikacja w tym module montuje pliki statyczne dokładnie tak jak
produkcja (`app/main.py`): bez tego montowania nieudane dopasowanie
dawałoby czyste 404 i test przestałby opisywać prawdziwy objaw.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import stock as stock_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.services.offer_catalog_service import OfferCatalogService
from app.utils.time import utc_now
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_offer_catalog_repository import FakeOfferCatalogRepository

#: Identyfikator oferty z ukośnikiem - klient koduje go jako `%2F`.
OFFER_ID = "OFFER/1"


class _StubContainer:
    """Kontener z katalogiem ofert w pamięci."""

    def __init__(self) -> None:
        self.catalog = FakeOfferCatalogRepository()
        self.plugin = FakeMarketplacePlugin()

    def offer_catalog_service(self, _session=None) -> OfferCatalogService:
        return OfferCatalogService(plugin=self.plugin, catalog_repository=self.catalog)


@pytest.fixture
def container() -> _StubContainer:
    stub = _StubContainer()
    for external_id, name in [(OFFER_ID, "Kroplomierz 10ml/30ml"), ("OFFER-2", "Butelka")]:
        stub.catalog.offers[("allegro", external_id)] = MarketplaceOffer(
            marketplace="allegro",
            external_id=external_id,
            name=name,
            signature=None,
            available_stock=3,
            price=Decimal("19.99"),
            synced_at=utc_now(),
        )
    return stub


@pytest.fixture
def client(container: _StubContainer, tmp_path: Path) -> Iterator[TestClient]:
    dist = tmp_path / "webapp_dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>ORDLY</h1>", encoding="utf-8")

    app = FastAPI()
    app.include_router(stock_endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.mount("/", StaticFiles(directory=dist, html=True), name="webapp")
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


class TestOfertaZUkosnikiem:
    """Trasy per-ofertę muszą działać dla "OFFER/1" tak samo jak dla "OFFER-2"."""

    def test_zapis_ilosci_przechodzi(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/stock/offers/allegro/OFFER%2F1/quantity",
            json={"quantity": 12, "reason": "Inwentaryzacja"},
        )

        assert response.status_code == 200
        assert response.json()["external_id"] == OFFER_ID
        assert response.json()["quantity_on_hand"] == 12

    def test_historia_zmian(self, client: TestClient) -> None:
        client.put(
            "/api/v1/stock/offers/allegro/OFFER%2F1/quantity",
            json={"quantity": 7, "reason": "Inwentaryzacja"},
        )

        response = client.get("/api/v1/stock/offers/allegro/OFFER%2F1/history")

        assert response.status_code == 200
        assert [m["change"] for m in response.json()] == [7]

    def test_nieistniejaca_oferta_z_ukosnikiem_to_404(self, client: TestClient) -> None:
        """404 z API, a nie 405 od plików statycznych - to dwie różne diagnozy."""
        response = client.put(
            "/api/v1/stock/offers/allegro/NIE%2FMA/quantity",
            json={"quantity": 1, "reason": "Inwentaryzacja"},
        )

        assert response.status_code == 404


class TestKolejnoscTras:
    """
    `{external_id:path}` kompiluje się do `.*`, więc połyka wszystko.

    Te testy pilnują, że trasy z literałem dalej stoją tam, gdzie trzeba -
    przestawienie ich w pliku nie wysypie żadnego innego testu, tylko
    cicho przekieruje żądania na złą funkcję.
    """

    def test_lista_ofert_nie_jest_traktowana_jak_identyfikator(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/stock/offers")

        assert response.status_code == 200
        assert {o["external_id"] for o in response.json()} == {OFFER_ID, "OFFER-2"}

    def test_quantity_nie_jest_czescia_identyfikatora_oferty(self, client: TestClient) -> None:
        """Bez tej kolejności `{...:path}` zjadłby końcówkę "/quantity"."""
        response = client.put(
            "/api/v1/stock/offers/allegro/OFFER-2/quantity",
            json={"quantity": 4, "reason": "Inwentaryzacja"},
        )

        assert response.status_code == 200
        assert response.json()["external_id"] == "OFFER-2"

    def test_history_nie_jest_czescia_identyfikatora_oferty(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/offers/allegro/OFFER-2/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_sciezka_spoza_api_dalej_trafia_do_pwa(self, client: TestClient) -> None:
        """
        Fallback na pliki statyczne jest żywy - i to on odpowiadał 405 na
        żądanie, gdy trasa API nie pasowała. Gdyby zniknął, testy powyżej
        przestałyby dotyczyć prawdziwego objawu.
        """
        assert client.get("/").status_code == 200
        assert client.post("/api/v1/nie-ma-takiej-trasy").status_code == 405

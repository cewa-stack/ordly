"""
Testy HTTP dla identyfikatorów z ukośnikiem: SKU "KRO10/30", oferta
"OFFER/1".

Bug z 6 września 2026: korekta stanu takiego produktu wracała z aplikacji
desktopowej jako "Korekta nie przeszła - Method Not Allowed". Ukośnik
w SKU trafia do URL jako `%2F`, ale serwer ASGI dekoduje ścieżkę PRZED
dopasowaniem trasy (`unquote(raw_path)` - tak samo w uvicornie i w
`TestClient`). Router widział więc `/stock/KRO10/30/adjust`, nie
dopasowywał żadnej trasy i żądanie spadało do `StaticFiles("/")`
serwującego PWA, a ten na POST odpowiada `405 Method Not Allowed`.

Dlatego aplikacja w tym module montuje pliki statyczne dokładnie tak jak
produkcja (`app/main.py`): bez tego montowania nieudane dopasowanie
dawałoby czyste 404 i test przestałby opisywać prawdziwy objaw.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import stock as stock_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.inventory_item import InventoryItem
from app.services.inventory_service import InventoryService
from app.services.offer_mapping_service import OfferMappingService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_order_repository import FakeOrderRepository

#: SKU tak, jak nazwał je użytkownik: kroplomierz i nakrętka pasujące
#: do butelek 10 i 30 ml.
KROPLOMIERZ = "KRO10/30"
NAKRETKA = "NAK10/30"

#: Identyfikator oferty też bywa ze ukośnikiem - klient desktopowy
#: koduje go tą samą funkcją co SKU.
OFFER_ID = "OFFER/1"


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
    for sku, name in [
        (KROPLOMIERZ, "Kroplomierz 10ml/30ml"),
        (NAKRETKA, "Nakrętka 10ml/30ml"),
        ("PET60", "Butelka PET 60 ml"),
    ]:
        stub.inventory.items[sku] = InventoryItem(sku=sku, name=name, stock=0, min_stock=25)
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


class TestSkuZUkosnikiem:
    """Każda trasa per-SKU musi działać dla "KRO10/30" tak samo jak dla "PET60"."""

    def test_korekta_stanu_przechodzi(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/stock/KRO10%2F30/adjust",
            json={"op": "add", "quantity": 500, "reason": "Dostawa"},
        )

        assert response.status_code == 200
        assert response.json()["sku"] == KROPLOMIERZ
        assert response.json()["stock"] == 500

    def test_ustawienie_stanu_przechodzi(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/stock/KRO10%2F30/adjust", json={"op": "set", "quantity": 120}
        )

        assert response.status_code == 200
        assert response.json()["stock"] == 120

    def test_podglad_produktu(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/KRO10%2F30")

        assert response.status_code == 200
        assert response.json()["name"] == "Kroplomierz 10ml/30ml"

    def test_historia_zmian(self, client: TestClient) -> None:
        client.post("/api/v1/stock/KRO10%2F30/adjust", json={"op": "add", "quantity": 7})

        response = client.get("/api/v1/stock/KRO10%2F30/history")

        assert response.status_code == 200
        assert [m["change"] for m in response.json()] == [7]

    def test_produkt_glowny_i_podprodukty(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/stock/NAK10%2F30/parent", json={"parent_sku": KROPLOMIERZ}
        )

        assert response.status_code == 200
        assert response.json()["parent_sku"] == KROPLOMIERZ

        sub_items = client.get("/api/v1/stock/KRO10%2F30/sub-items")
        assert [i["sku"] for i in sub_items.json()] == [NAKRETKA]

    def test_usuniecie_produktu(self, client: TestClient) -> None:
        response = client.delete("/api/v1/stock/KRO10%2F30")

        assert response.status_code == 200
        assert response.json()["sku"] == KROPLOMIERZ
        assert client.get("/api/v1/stock/KRO10%2F30").status_code == 404

    def test_nieistniejace_sku_z_ukosnikiem_to_404(self, client: TestClient) -> None:
        """404 z API, a nie 405 od plików statycznych - to dwie różne diagnozy."""
        response = client.post(
            "/api/v1/stock/NIE%2FMA/adjust", json={"op": "add", "quantity": 1}
        )

        assert response.status_code == 404


class TestOfertaZUkosnikiem:
    def test_zapis_receptury(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/stock/offers/allegro/OFFER%2F1",
            json={"components": [{"sku": KROPLOMIERZ, "quantity": 1}]},
        )

        assert response.status_code == 200
        assert response.json()["external_product_id"] == OFFER_ID

    def test_podglad_korekty_wstecznej(self, client: TestClient) -> None:
        client.put(
            "/api/v1/stock/offers/allegro/OFFER%2F1",
            json={"components": [{"sku": KROPLOMIERZ, "quantity": 1}]},
        )

        response = client.get("/api/v1/stock/offers/allegro/OFFER%2F1/backfill")

        assert response.status_code == 200
        assert response.json()["external_product_id"] == OFFER_ID

    def test_usuniecie_receptury(self, client: TestClient) -> None:
        client.put(
            "/api/v1/stock/offers/allegro/OFFER%2F1",
            json={"components": [{"sku": KROPLOMIERZ, "quantity": 1}]},
        )

        response = client.delete("/api/v1/stock/offers/allegro/OFFER%2F1")

        assert response.status_code == 200
        assert response.json() == {"removed": 1}

    def test_usuniecie_mapowania(self, client: TestClient) -> None:
        client.post(
            "/api/v1/stock/links",
            json={"external_product_id": OFFER_ID, "sku": KROPLOMIERZ, "quantity": 1},
        )

        response = client.delete("/api/v1/stock/links/allegro/OFFER%2F1")

        assert response.status_code == 200
        assert response.json() == {"removed": 1}


class TestKolejnoscTras:
    """
    `{sku:path}` kompiluje się do `.*`, więc połyka wszystko, co pasuje.

    Te testy pilnują, że trasy o dłuższym wzorcu dalej stoją wyżej -
    przestawienie ich w pliku nie wysypie żadnego innego testu, tylko
    cicho przekieruje żądania na złą funkcję.
    """

    def test_report_nie_jest_traktowany_jak_sku(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/report")

        assert response.status_code == 200
        assert "total_stock_value" in response.json()

    def test_shopping_list_nie_jest_traktowana_jak_sku(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/shopping-list")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_offers_nie_jest_traktowane_jak_sku(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/offers")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_unmapped_nie_jest_traktowane_jak_oferta(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/offers/unmapped")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_backfill_nie_jest_czescia_identyfikatora_oferty(self, client: TestClient) -> None:
        """Bez tej kolejności `{...:path}` zjadłby końcówkę "/backfill"."""
        client.put(
            "/api/v1/stock/offers/allegro/OFFER-1",
            json={"components": [{"sku": KROPLOMIERZ, "quantity": 1}]},
        )

        response = client.get("/api/v1/stock/offers/allegro/OFFER-1/backfill")

        assert response.status_code == 200
        # Kształt planu korekty, a nie receptury - czyli trafiło we
        # właściwą funkcję, a `external_product_id` nie urósł o "/backfill".
        assert response.json()["external_product_id"] == "OFFER-1"
        assert response.json()["applied"] is False
        assert "pending_quantity" in response.json()

    def test_sciezka_spoza_api_dalej_trafia_do_pwa(self, client: TestClient) -> None:
        """
        Fallback na pliki statyczne jest żywy - i to on odpowiadał 405 na
        POST-a, gdy trasa API nie pasowała. Gdyby zniknął, testy powyżej
        przestałyby dotyczyć prawdziwego objawu.
        """
        assert client.get("/").status_code == 200
        assert client.post("/api/v1/nie-ma-takiej-trasy").status_code == 405

"""
Testy HTTP endpointów produktu głównego i podproduktów.

Na warstwie HTTP łapie się trzy rzeczy, których nie widać w serwisie:
kolejność tras (FastAPI mógłby potraktować "sub-items" jako część SKU),
kod odpowiedzi przy złamaniu reguły zagnieżdżenia (ma być czytelny błąd
klienta, nie 500) oraz kształt JSON-a - to kontrakt aplikacji
desktopowej, która grupuje listę magazynową po polu `parent_sku`.
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
    for sku, name, stock in [
        ("BUT10", "Butelka 10 ml", 500),
        ("NAK10", "Nakrętka 10 ml", 500),
        ("KRO10", "Kroplomierz 10 ml", 500),
        ("KARTON", "Karton zbiorczy", 40),
    ]:
        stub.inventory.items[sku] = InventoryItem(
            sku=sku, name=name, stock=stock, min_stock=50
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


class TestUstawianieProduktuGlownego:
    def test_put_parent_zwraca_zaktualizowany_produkt(self, client: TestClient) -> None:
        response = client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        assert response.status_code == 200
        assert response.json()["parent_sku"] == "BUT10"
        assert response.json()["sku"] == "NAK10"

    def test_put_parent_null_zdejmuje_powiazanie(self, client: TestClient) -> None:
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": None})

        assert response.status_code == 200
        assert response.json()["parent_sku"] is None

    def test_puste_cialo_tez_zdejmuje_powiazanie(self, client: TestClient) -> None:
        """Desktop wysyła `{}` przy „Odłącz" - to ma znaczyć to samo co null."""
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.put("/api/v1/stock/NAK10/parent", json={})

        assert response.status_code == 200
        assert response.json()["parent_sku"] is None

    def test_nieistniejacy_produkt_to_404(self, client: TestClient) -> None:
        response = client.put("/api/v1/stock/NIE-MA/parent", json={"parent_sku": "BUT10"})

        assert response.status_code == 404

    def test_nieistniejacy_produkt_glowny_to_404(self, client: TestClient) -> None:
        response = client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "NIE-MA"})

        assert response.status_code == 404


class TestReguleJednegoPoziomu:
    """
    Kryterium akceptacji nr 4: czytelny błąd klienta, nigdy 500.

    ORDLY mapuje `ValueError` na 422 - tak samo jak przy „Stan magazynowy
    nie może być ujemny" i każdej innej walidacji. Osobny kod tylko dla
    tego endpointu rozjechałby się z resztą API.
    """

    def test_wlasny_rodzic_jest_odrzucany(self, client: TestClient) -> None:
        response = client.put("/api/v1/stock/BUT10/parent", json={"parent_sku": "BUT10"})

        assert response.status_code == 422
        assert "własnym" in response.json()["detail"]

    def test_drugi_poziom_zagniezdzenia_jest_odrzucany(self, client: TestClient) -> None:
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.put("/api/v1/stock/KRO10/parent", json={"parent_sku": "NAK10"})

        assert response.status_code == 422
        assert "jednopoziomowe" in response.json()["detail"]

    def test_produkt_z_podproduktami_nie_moze_stac_sie_podproduktem(
        self, client: TestClient
    ) -> None:
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.put("/api/v1/stock/BUT10/parent", json={"parent_sku": "KARTON"})

        assert response.status_code == 422
        assert "podprodukty" in response.json()["detail"]


class TestOdczytPodproduktow:
    def test_lista_podproduktow(self, client: TestClient) -> None:
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})
        client.put("/api/v1/stock/KRO10/parent", json={"parent_sku": "BUT10"})

        response = client.get("/api/v1/stock/BUT10/sub-items")

        assert response.status_code == 200
        assert [i["sku"] for i in response.json()] == ["KRO10", "NAK10"]

    def test_produkt_bez_podproduktow_zwraca_pusta_liste(self, client: TestClient) -> None:
        response = client.get("/api/v1/stock/BUT10/sub-items")

        assert response.status_code == 200
        assert response.json() == []

    def test_nieistniejacy_produkt_to_404(self, client: TestClient) -> None:
        """Pusta lista udawałaby, że produkt istnieje, tylko nic nie ma."""
        response = client.get("/api/v1/stock/NIE-MA/sub-items")

        assert response.status_code == 404

    def test_sub_items_nie_koliduje_z_trasa_pojedynczego_produktu(
        self, client: TestClient
    ) -> None:
        """FastAPI nie może potraktować "sub-items" jako części SKU."""
        pojedynczy = client.get("/api/v1/stock/BUT10")

        assert pojedynczy.status_code == 200
        assert pojedynczy.json()["sku"] == "BUT10"


class TestKontraktJson:
    def test_lista_magazynowa_niesie_parent_sku(self, client: TestClient) -> None:
        """Desktop grupuje wiersze po tym polu - bez niego chowa wszystko."""
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})

        response = client.get("/api/v1/stock")

        po_sku = {i["sku"]: i["parent_sku"] for i in response.json()}
        assert po_sku["NAK10"] == "BUT10"
        assert po_sku["BUT10"] is None

    def test_lista_zakupow_pokazuje_konczace_sie_podprodukty(
        self, client: TestClient, container: _StubContainer
    ) -> None:
        """
        Lista magazynowa chowa nakrętki pod butelką, ale lista zakupów
        musi je pokazać - inaczej skończyłyby się bez ostrzeżenia.
        """
        client.put("/api/v1/stock/NAK10/parent", json={"parent_sku": "BUT10"})
        container.inventory.items["NAK10"] = InventoryItem(
            sku="NAK10", name="Nakrętka 10 ml", stock=10, min_stock=50, parent_sku="BUT10"
        )

        response = client.get("/api/v1/stock/shopping-list")

        po_sku = {i["sku"]: i["parent_sku"] for i in response.json()}
        assert po_sku["NAK10"] == "BUT10"
        assert "KARTON" in po_sku

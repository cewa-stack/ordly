"""Testy jednostkowe InventoryService (IMS)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.inventory_item import InventoryItem
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InsufficientStockError,
    InventoryItemNotFoundError,
)
from app.services.inventory_service import InventoryService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository


@pytest.fixture
def repository() -> FakeInventoryRepository:
    return FakeInventoryRepository()


@pytest.fixture
def service(repository: FakeInventoryRepository) -> InventoryService:
    return InventoryService(repository)


async def test_create_item_starts_with_zero_stock(service: InventoryService) -> None:
    item = await service.create_item("PET60", "Butelka PET 60 ml")

    assert item.sku == "PET60"
    assert item.stock == 0
    assert item.min_stock == 0


async def test_create_duplicate_sku_raises(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    with pytest.raises(DuplicateInventoryItemError):
        await service.create_item("PET60", "Inna butelka")


async def test_set_stock_records_movement(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    item = await service.set_stock("PET60", 500)

    assert item.stock == 500
    assert len(repository.movements) == 1
    movement = repository.movements[0]
    assert movement.change == 500
    assert movement.stock_after == 500
    assert movement.source == "manual"


async def test_add_and_remove_stock(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 100)

    after_add = await service.add_stock("PET60", 200)
    after_remove = await service.remove_stock("PET60", 15)

    assert after_add.stock == 300
    assert after_remove.stock == 285
    changes = [m.change for m in repository.movements]
    assert changes == [100, 200, -15]


async def test_remove_below_zero_raises(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 10)

    with pytest.raises(InsufficientStockError):
        await service.remove_stock("PET60", 11)


async def test_unknown_sku_raises(service: InventoryService) -> None:
    with pytest.raises(InventoryItemNotFoundError):
        await service.set_stock("NOPE", 10)


async def test_negative_set_raises_value_error(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    with pytest.raises(ValueError):
        await service.set_stock("PET60", -5)


async def test_shopping_list_contains_low_stock_items(
    service: InventoryService,
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 100)
    await service.create_item("CAP", "Nakrętka czarna", min_stock=20)
    await service.set_stock("CAP", 7)

    shopping_list = await service.get_shopping_list()

    assert [item.sku for item in shopping_list] == ["CAP"]


async def test_report_totals_and_forecast(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    repository.items["PET60"] = InventoryItem(
        sku="PET60",
        name="Butelka PET 60 ml",
        stock=240,
        min_stock=50,
        purchase_cost=Decimal("1.50"),
    )
    # 360 szt. sprzedane w oknie 30 dni -> 12 szt./dzień -> zapas na 20 dni
    await service.remove_stock("PET60", 1)  # ruch manualny, nie wpływa na prognozę
    from app.domain.entities.inventory_movement import (
        MOVEMENT_SOURCE_ORDER,
        InventoryMovement,
    )
    from app.utils.time import utc_now

    repository.movements.append(
        InventoryMovement(
            item_sku="PET60",
            item_name="Butelka PET 60 ml",
            change=-360,
            stock_after=239,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference="123",
            occurred_at=utc_now(),
        )
    )
    await service.set_stock("PET60", 240)

    report = await service.get_report()

    assert report.total_items == 1
    assert report.total_stock_value == Decimal("360.00")
    assert len(report.forecasts) == 1
    forecast = report.forecasts[0]
    assert forecast.avg_daily_sales == pytest.approx(12.0)
    assert forecast.days_left == 20
    assert report.items_without_sales == ()


async def test_report_marks_items_without_sales(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    report = await service.get_report()

    assert [i.sku for i in report.items_without_sales] == ["PET60"]
    assert report.forecasts == ()


class TestProduktGlownyIPodprodukty:
    """
    Reguły relacji produkt główny -> podprodukt.

    Walidacje siedzą w serwisie, nie w interfejsie: desktop może tylko
    schować niedozwolone opcje w liście wyboru, ale API stoi otworem
    dla bota, skryptów i przyszłych ekranów.
    """

    @staticmethod
    async def _trzy_produkty(service: InventoryService) -> None:
        await service.create_item("BUT10", "Butelka 10 ml")
        await service.create_item("NAK10", "Nakrętka 10 ml")
        await service.create_item("KRO10", "Kroplomierz 10 ml")

    async def test_przypisanie_produktu_glownego(self, service: InventoryService) -> None:
        await self._trzy_produkty(service)

        item = await service.set_parent("NAK10", "BUT10")

        assert item.parent_sku == "BUT10"
        assert [i.sku for i in await service.get_sub_items("BUT10")] == ["NAK10"]

    async def test_zdjecie_powiazania(self, service: InventoryService) -> None:
        await self._trzy_produkty(service)
        await service.set_parent("NAK10", "BUT10")

        item = await service.set_parent("NAK10", None)

        assert item.parent_sku is None
        assert await service.get_sub_items("BUT10") == []

    async def test_produkt_nie_moze_byc_swoim_rodzicem(
        self, service: InventoryService
    ) -> None:
        await self._trzy_produkty(service)

        with pytest.raises(ValueError, match="swoim własnym"):
            await service.set_parent("BUT10", "BUT10")

    async def test_podprodukt_nie_moze_byc_produktem_glownym(
        self, service: InventoryService
    ) -> None:
        """Drugi poziom zagnieżdżenia: nakrętka -> butelka -> karton."""
        await self._trzy_produkty(service)
        await service.set_parent("NAK10", "BUT10")

        with pytest.raises(ValueError, match="jednopoziomowe"):
            await service.set_parent("KRO10", "NAK10")

    async def test_produkt_z_podproduktami_nie_moze_stac_sie_podproduktem(
        self, service: InventoryService
    ) -> None:
        """Ta sama reguła od drugiej strony."""
        await self._trzy_produkty(service)
        await service.create_item("KARTON", "Karton zbiorczy")
        await service.set_parent("NAK10", "BUT10")

        with pytest.raises(ValueError, match="własne podprodukty"):
            await service.set_parent("BUT10", "KARTON")

    async def test_nieistniejacy_produkt_glowny(self, service: InventoryService) -> None:
        await self._trzy_produkty(service)

        with pytest.raises(InventoryItemNotFoundError):
            await service.set_parent("NAK10", "NIE-MA")

    async def test_podprodukty_nieistniejacego_produktu(
        self, service: InventoryService
    ) -> None:
        with pytest.raises(InventoryItemNotFoundError):
            await service.get_sub_items("NIE-MA")

    async def test_reczna_korekta_nie_rusza_podproduktow(
        self, service: InventoryService, repository: FakeInventoryRepository
    ) -> None:
        """
        REGRESJA ŚWIADOMEJ DECYZJI, nie przeoczenie.

        Do magazynu przyjeżdżają osobne kartony butelek i osobne kartony
        nakrętek, więc dostawę i inwentaryzację wpisuje się osobno dla
        każdego SKU. Gdyby `/stock add` kaskadowało, każde przyjęcie
        dostawy butelek dopisywałoby nieistniejące nakrętki.
        """
        await self._trzy_produkty(service)
        await service.set_parent("NAK10", "BUT10")
        await service.set_parent("KRO10", "BUT10")

        await service.add_stock("BUT10", 50, "Dostawa")

        assert repository.items["BUT10"].stock == 50
        assert repository.items["NAK10"].stock == 0
        assert repository.items["KRO10"].stock == 0

    async def test_reczne_zdjecie_stanu_tez_nie_kaskaduje(
        self, service: InventoryService, repository: FakeInventoryRepository
    ) -> None:
        await self._trzy_produkty(service)
        await service.set_parent("NAK10", "BUT10")
        await service.add_stock("BUT10", 50)
        await service.add_stock("NAK10", 50)

        await service.remove_stock("BUT10", 10)

        assert repository.items["BUT10"].stock == 40
        assert repository.items["NAK10"].stock == 50

    async def test_podprodukt_z_niskim_stanem_jest_na_liscie_zakupow(
        self, service: InventoryService, repository: FakeInventoryRepository
    ) -> None:
        """
        Lista magazynowa chowa nakrętki pod butelką, ale lista zakupów
        musi je pokazać - kończące się nakrętki trzeba dokupić.
        """
        repository.items["BUT10"] = InventoryItem(
            sku="BUT10", name="Butelka 10 ml", stock=500, min_stock=50
        )
        repository.items["NAK10"] = InventoryItem(
            sku="NAK10", name="Nakrętka 10 ml", stock=10, min_stock=50, parent_sku="BUT10"
        )

        lista = await service.get_shopping_list()

        assert [i.sku for i in lista] == ["NAK10"]


class TestUsuwanieProduktu:
    """
    Usuwanie pozycji z magazynu (przycisk "Usuń" w aplikacji desktopowej).

    Usunięcie jest jedyną operacją magazynową bez śladu w historii -
    wpisy ruchów znikają razem z produktem, bo wiszą na jego SKU.
    Dlatego serwis oddaje podsumowanie tego, co zniknęło i co się
    odwiązało: to jedyny moment, w którym można o tym powiedzieć.
    """

    @staticmethod
    async def _butelka_z_nakretka(service: InventoryService) -> None:
        await service.create_item("BUT10", "Butelka 10 ml")
        await service.create_item("NAK10", "Nakrętka 10 ml")
        await service.set_parent("NAK10", "BUT10")

    async def test_produkt_znika_z_magazynu(self, service: InventoryService) -> None:
        await service.create_item("PET60", "Butelka PET 60 ml")
        await service.add_stock("PET60", 12)

        deletion = await service.delete_item("PET60")

        assert deletion.sku == "PET60"
        assert deletion.stock == 12
        assert await service.get_stock_overview() == []
        with pytest.raises(InventoryItemNotFoundError):
            await service.get_item("PET60")

    async def test_historia_ruchow_znika_razem_z_produktem(
        self, service: InventoryService, repository: FakeInventoryRepository
    ) -> None:
        await service.create_item("PET60", "Butelka PET 60 ml")
        await service.add_stock("PET60", 5)
        assert repository.movements != []

        await service.delete_item("PET60")

        assert repository.movements == []

    async def test_podprodukty_zostaja_i_wracaja_na_liste(
        self, service: InventoryService
    ) -> None:
        await self._butelka_z_nakretka(service)

        deletion = await service.delete_item("BUT10")

        assert deletion.detached_sub_items == ("NAK10",)
        nakretka = await service.get_item("NAK10")
        assert nakretka.parent_sku is None

    async def test_usuniecie_podproduktu_nie_rusza_produktu_glownego(
        self, service: InventoryService
    ) -> None:
        await self._butelka_z_nakretka(service)

        await service.delete_item("NAK10")

        assert await service.get_sub_items("BUT10") == []
        assert (await service.get_item("BUT10")).sku == "BUT10"

    async def test_produkt_wypada_z_receptur_ofert(
        self, service: InventoryService, repository: FakeInventoryRepository
    ) -> None:
        await service.create_item("BUT10", "Butelka 10 ml")
        await service.create_item("KARTON", "Karton zbiorczy")
        await service.link_offer("allegro", "OFFER-1", "BUT10", 1)
        await service.link_offer("allegro", "OFFER-1", "KARTON", 1)
        await service.link_offer("allegro", "OFFER-2", "BUT10", 3)

        deletion = await service.delete_item("BUT10")

        assert deletion.removed_offer_links == 2
        pozostale = {
            component.sku
            for components in repository.links.values()
            for component in components
        }
        assert pozostale == {"KARTON"}

    async def test_nieistniejace_sku(self, service: InventoryService) -> None:
        with pytest.raises(InventoryItemNotFoundError):
            await service.delete_item("NIE-MA")

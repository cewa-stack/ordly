"""
Testy kaskady na podprodukty (butelka -> nakrętka, kroplomierz).

Kaskada jest cicha: nie ma własnego ekranu ani powiadomienia, a jej
błąd objawia się dopiero rozjazdem stanu na półce. Dlatego sprawdzana
jest tu proporcja 1:1, kierunek zmiany i granica "tylko sprzedaż".
"""

from __future__ import annotations

import pytest

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import MOVEMENT_SOURCE_ORDER
from app.services.sub_item_cascade import cascade_to_sub_items
from tests.fakes.fake_inventory_repository import FakeInventoryRepository


@pytest.fixture
def inventory() -> FakeInventoryRepository:
    repository = FakeInventoryRepository()
    repository.items["BUT10"] = InventoryItem(
        sku="BUT10", name="Butelka 10 ml", stock=500, min_stock=50
    )
    repository.items["NAK10"] = InventoryItem(
        sku="NAK10", name="Nakrętka 10 ml", stock=500, min_stock=50, parent_sku="BUT10"
    )
    repository.items["KRO10"] = InventoryItem(
        sku="KRO10", name="Kroplomierz 10 ml", stock=120, min_stock=50, parent_sku="BUT10"
    )
    return repository


async def _cascade(
    inventory: FakeInventoryRepository, change: int, **kwargs
) -> list[InventoryItem]:
    return await cascade_to_sub_items(
        inventory=inventory,
        parent_sku="BUT10",
        change=change,
        reason="Nowe zamówienie",
        source=MOVEMENT_SOURCE_ORDER,
        reference="ORDER-1",
        **kwargs,
    )


class TestProporcja:
    async def test_kazdy_podprodukt_schodzi_o_tyle_samo(
        self, inventory: FakeInventoryRepository
    ) -> None:
        updated = await _cascade(inventory, -100)

        assert inventory.items["NAK10"].stock == 400
        assert inventory.items["KRO10"].stock == 20
        assert {item.sku for item in updated} == {"NAK10", "KRO10"}

    async def test_zwrot_przywraca_podprodukty(
        self, inventory: FakeInventoryRepository
    ) -> None:
        """Kaskada jest symetryczna - inaczej zwrot rozjechałby magazyn."""
        await _cascade(inventory, 30)

        assert inventory.items["NAK10"].stock == 530
        assert inventory.items["KRO10"].stock == 150

    async def test_produkt_bez_podproduktow_nic_nie_rusza(
        self, inventory: FakeInventoryRepository
    ) -> None:
        updated = await cascade_to_sub_items(
            inventory=inventory,
            parent_sku="NAK10",
            change=-10,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference="ORDER-1",
        )

        assert updated == []
        assert inventory.items["BUT10"].stock == 500


class TestHistoria:
    async def test_ruch_podproduktu_wskazuje_ten_sam_dokument(
        self, inventory: FakeInventoryRepository
    ) -> None:
        """
        Bez wspólnego `reference` nie dałoby się odpowiedzieć na pytanie
        „skąd zniknęło 100 nakrętek" - w historii byłby ruch bez powodu.
        """
        await _cascade(inventory, -100)

        ruchy = {m.item_sku: m for m in inventory.movements}
        assert ruchy["NAK10"].reference == "ORDER-1"
        assert ruchy["NAK10"].source == MOVEMENT_SOURCE_ORDER
        assert "podprodukt: BUT10" in ruchy["NAK10"].reason

    async def test_podprodukt_ma_wlasny_wpis_a_nie_dopisek_do_rodzica(
        self, inventory: FakeInventoryRepository
    ) -> None:
        await _cascade(inventory, -100)

        assert sorted(m.item_sku for m in inventory.movements) == ["KRO10", "NAK10"]


class TestGranice:
    async def test_stan_nie_schodzi_ponizej_zera(
        self, inventory: FakeInventoryRepository
    ) -> None:
        """
        Kroplomierzy jest 120, a sprzedaż mówi o 200. Ujemny stan nie
        opisuje niczego, co da się policzyć na półce.
        """
        await _cascade(inventory, -200)

        assert inventory.items["KRO10"].stock == 0
        assert inventory.items["NAK10"].stock == 300

    async def test_skip_skus_chroni_przed_podwojnym_odjeciem(
        self, inventory: FakeInventoryRepository
    ) -> None:
        """
        Stara receptura wymienia butelkę i nakrętkę osobno. Nakrętkę
        odjęła już receptura, więc kaskada musi ją pominąć - inaczej
        każda sprzedaż zdejmowałaby ją dwa razy.
        """
        await _cascade(inventory, -100, skip_skus={"BUT10", "NAK10"})

        assert inventory.items["NAK10"].stock == 500
        assert inventory.items["KRO10"].stock == 20

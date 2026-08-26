"""
Pełna integracja Allegro Lokalnie: mail -> zamówienie -> magazyn.

To jest test, który rozstrzyga, czy „pełna integracja" naprawdę działa:
bierze PRAWDZIWY mail sprzedażowy, przepuszcza go przez parser i serwis
zamówień, a potem przez `StockSyncService` - ten sam, którego używa
Allegro.pl. Jeśli ta ścieżka się rozjedzie, stany magazynowe przestaną
się zgadzać po cichu, a to najgorszy możliwy rodzaj błędu w tej aplikacji.

Sprawdzane są obie strony: powiązana oferta ZDEJMUJE właściwą liczbę
sztuk, a niepowiązana zgłasza się jako `unmatched_products` (czyli głośno,
powiadomieniem „Sprzedaż poza magazynem"), zamiast milczeć.
"""

from __future__ import annotations

import pathlib
from decimal import Decimal
from email import message_from_bytes

import pytest

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.offer_component import OfferComponent
from app.infrastructure.mail.allegro_lokalnie import offer_external_id, parse_event
from app.infrastructure.mail.imap_watcher import _parse_message
from app.infrastructure.mail.mime import extract_bodies
from app.services.allegro_lokalnie_orders_service import (
    MARKETPLACE_ALLEGRO_LOKALNIE,
    AllegroLokalnieOrdersService,
)
from app.services.offer_mapping_service import OfferMappingService
from app.services.stock_sync_service import StockSyncService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_order_repository import FakeOrderRepository
from tests.fakes.fake_stock_sync_repository import FakeStockSyncRepository

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_lokalnie"
SPRZEDANO_100 = (
    "Sprzedano 100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
TYTUL_OGLOSZENIA = "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"


async def zamowienie_z_maila():
    """Mail -> zdarzenie -> zamówienie, dokładnie jak w produkcji."""
    raw = (FIXTURES / SPRZEDANO_100).read_bytes()
    message = _parse_message(raw)
    assert message is not None
    event = parse_event(message, extract_bodies(message_from_bytes(raw)))
    order = await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(event)
    assert order is not None
    return order


def magazyn_z_powiazaniem(sztuk_w_ofercie: int = 100) -> FakeInventoryRepository:
    """
    Magazyn z butelkami i recepturą oferty.

    Ogłoszenie „100szt. Butelka Gorilla 10ml" to sto butelek w jednej
    paczce, więc jedna sprzedana sztuka OFERTY zdejmuje sto sztuk
    z magazynu - dokładnie po to istnieją receptury.
    """
    inventory = FakeInventoryRepository()
    inventory.items["BUT-GOR-10"] = InventoryItem(
        sku="BUT-GOR-10", name="Butelka Gorilla 10 ml", stock=1000, min_stock=200
    )
    inventory.links[(MARKETPLACE_ALLEGRO_LOKALNIE, offer_external_id(TYTUL_OGLOSZENIA))] = [
        OfferComponent(sku="BUT-GOR-10", quantity=sztuk_w_ofercie)
    ]
    return inventory


class TestSprzedazZdejmujeStany:
    @pytest.mark.asyncio
    async def test_powiazana_oferta_odejmuje_wlasciwa_liczbe_sztuk(self):
        """
        4 sprzedane sztuki oferty × 100 butelek w ofercie = 400 butelek.
        Z 1000 zostaje 600.
        """
        order = await zamowienie_z_maila()
        inventory = magazyn_z_powiazaniem()
        service = StockSyncService(inventory, FakeStockSyncRepository())

        outcome = await service.process_order_created(order)

        assert outcome.processed is True
        assert outcome.unmatched_products == ()
        assert inventory.items["BUT-GOR-10"].stock == 600

    @pytest.mark.asyncio
    async def test_ruch_magazynowy_wskazuje_na_zamowienie_z_lokalnie(self):
        """Historia magazynu ma prowadzić do konkretnej sprzedaży, nie do „skądś"."""
        order = await zamowienie_z_maila()
        inventory = magazyn_z_powiazaniem()

        await StockSyncService(inventory, FakeStockSyncRepository()).process_order_created(
            order
        )

        assert len(inventory.movements) == 1
        ruch = inventory.movements[0]
        assert ruch.item_sku == "BUT-GOR-10"
        assert ruch.change == -400
        assert ruch.reference == order.external_id

    @pytest.mark.asyncio
    async def test_drugie_przetworzenie_nie_odejmuje_ponownie(self):
        """
        Znacznik synchronizacji `(marketplace, reference, operation)` to
        ochrona przed podwójnym odjęciem, gdy ten sam mail przejdzie
        ścieżkę dwa razy.
        """
        order = await zamowienie_z_maila()
        inventory = magazyn_z_powiazaniem()
        markers = FakeStockSyncRepository()
        service = StockSyncService(inventory, markers)

        await service.process_order_created(order)
        drugie = await service.process_order_created(order)

        assert drugie.processed is False
        assert inventory.items["BUT-GOR-10"].stock == 600

    @pytest.mark.asyncio
    async def test_niepowiazana_oferta_zglasza_sie_glosno(self):
        """
        Bez receptury stan magazynu stoi w miejscu - i to jest poprawne
        zachowanie, ale MUSI być widoczne. `unmatched_products` zamienia
        się w powiadomienie „Sprzedaż poza magazynem" z nazwą oferty do
        powiązania.
        """
        order = await zamowienie_z_maila()
        pusty_magazyn = FakeInventoryRepository()
        service = StockSyncService(pusty_magazyn, FakeStockSyncRepository())

        outcome = await service.process_order_created(order)

        assert len(outcome.unmatched_products) == 1
        zgloszona = outcome.unmatched_products[0]
        assert TYTUL_OGLOSZENIA in zgloszona
        # Identyfikator oferty jest w treści ostrzeżenia po to, żeby dało
        # się go wprost przepisać do `/stock link` - bez niego użytkownik
        # wiedziałby, że coś nie działa, ale nie CO powiązać.
        assert offer_external_id(TYTUL_OGLOSZENIA) in zgloszona
        assert pusty_magazyn.movements == []

    @pytest.mark.asyncio
    async def test_niski_stan_po_sprzedazy_jest_wykryty(self):
        """
        Sprzedaż z Lokalnie ma uruchamiać te same alarmy co z Allegro.pl -
        inaczej magazyn zszedłby poniżej progu bez ostrzeżenia.
        """
        order = await zamowienie_z_maila()
        inventory = magazyn_z_powiazaniem()
        inventory.items["BUT-GOR-10"] = InventoryItem(
            sku="BUT-GOR-10", name="Butelka Gorilla 10 ml", stock=450, min_stock=200
        )
        service = StockSyncService(inventory, FakeStockSyncRepository())

        outcome = await service.process_order_created(order)

        assert inventory.items["BUT-GOR-10"].stock == 50
        assert [item.sku for item in outcome.low_stock_items] == ["BUT-GOR-10"]


class TestPrzychodILista:
    """Zamówienie ma się liczyć tam, gdzie liczy się sprzedaż z Allegro.pl."""

    @pytest.mark.asyncio
    async def test_kwota_zamowienia_to_kwota_zaplacona_przez_kupujacego(self):
        """
        Statystyki sumują `total_amount`. Cena jednostkowa oferty
        (71,98 zł) zaniżyłaby przychód czterokrotnie.
        """
        order = await zamowienie_z_maila()

        assert order.total_amount == Decimal("287.92")

    @pytest.mark.asyncio
    async def test_zamowienie_jest_widoczne_jako_do_spakowania(self):
        repository = FakeOrderRepository()
        raw = (FIXTURES / SPRZEDANO_100).read_bytes()
        message = _parse_message(raw)
        assert message is not None
        event = parse_event(message, extract_bodies(message_from_bytes(raw)))

        await AllegroLokalnieOrdersService(repository).create_from_event(event)

        nowe = await repository.get_new_status()
        assert [o.marketplace for o in nowe] == [MARKETPLACE_ALLEGRO_LOKALNIE]


class TestPowiazanieOferty:
    """
    Droga użytkownika po pierwszej sprzedaży: oferta ma się sama zgłosić
    w „Powiązania ofert", z identyfikatorem gotowym do wpisania.
    """

    @pytest.mark.asyncio
    async def test_niepowiazana_oferta_pojawia_sie_na_liscie_do_powiazania(self):
        repository = FakeOrderRepository()
        raw = (FIXTURES / SPRZEDANO_100).read_bytes()
        message = _parse_message(raw)
        assert message is not None
        event = parse_event(message, extract_bodies(message_from_bytes(raw)))
        await AllegroLokalnieOrdersService(repository).create_from_event(event)
        service = OfferMappingService(FakeInventoryRepository(), repository)

        niepowiazane = await service.get_unmapped_offers()

        assert len(niepowiazane) == 1
        oferta = niepowiazane[0]
        assert oferta.marketplace == MARKETPLACE_ALLEGRO_LOKALNIE
        assert oferta.external_product_id == offer_external_id(TYTUL_OGLOSZENIA)
        assert oferta.name == TYTUL_OGLOSZENIA
        assert oferta.sold_quantity == 4

    @pytest.mark.asyncio
    async def test_po_powiazaniu_oferta_znika_z_listy(self):
        repository = FakeOrderRepository()
        raw = (FIXTURES / SPRZEDANO_100).read_bytes()
        message = _parse_message(raw)
        assert message is not None
        event = parse_event(message, extract_bodies(message_from_bytes(raw)))
        await AllegroLokalnieOrdersService(repository).create_from_event(event)
        service = OfferMappingService(magazyn_z_powiazaniem(), repository)

        assert await service.get_unmapped_offers() == []

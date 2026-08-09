"""
Testy jednostkowe OfferMappingService.

Scenariusz przewodni jest dokładnie tym, który wyszedł na produkcji:
oferta butelki 60 ml sprzedaje się od tygodni, magazyn stoi w miejscu,
bo oferta nie ma receptury. Testy sprawdzają, że taką ofertę widać,
że recepturę da się zapisać i że korekta wsteczna nadrabia stany
dokładnie raz.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.offer_component import OfferComponent
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.exceptions.domain_exceptions import InventoryItemNotFoundError
from app.services.offer_mapping_service import OfferMappingService
from app.utils.time import utc_now
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_order_repository import FakeOrderRepository

OFFER_ID = "16812345678"
MARKETPLACE = "allegro"


def _make_order(external_id: str, quantity: int, days_ago: int, status: str = "NEW") -> Order:
    return Order(
        external_id=external_id,
        marketplace=MARKETPLACE,
        buyer=Customer(login="jan_kowalski", email="jan@example.com"),
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
        status=status,
        order_date=utc_now() - timedelta(days=days_ago),
    )


@pytest.fixture
def inventory() -> FakeInventoryRepository:
    repository = FakeInventoryRepository()
    repository.items["PET60"] = InventoryItem(
        sku="PET60", name="Butelka PET 60 ml", stock=42, min_stock=10
    )
    repository.items["KROPL"] = InventoryItem(
        sku="KROPL", name="Kroplomierz", stock=42, min_stock=10
    )
    repository.items["CAP"] = InventoryItem(sku="CAP", name="Nakrętka", stock=42, min_stock=10)
    return repository


@pytest.fixture
def orders() -> FakeOrderRepository:
    return FakeOrderRepository()


@pytest.fixture
def service(
    inventory: FakeInventoryRepository, orders: FakeOrderRepository
) -> OfferMappingService:
    return OfferMappingService(inventory, orders)


async def _save_the_two_sales(orders: FakeOrderRepository) -> None:
    """Odtwarza sytuację z produkcji: sprzedaż 25 szt., potem 10 szt."""
    await orders.save(_make_order("ORDER-001", quantity=25, days_ago=6))
    await orders.save(_make_order("ORDER-002", quantity=10, days_ago=2))


async def test_sprzedana_oferta_bez_receptury_trafia_na_liste_niepowiazanych(
    service: OfferMappingService, orders: FakeOrderRepository
) -> None:
    await _save_the_two_sales(orders)

    unmapped = await service.get_unmapped_offers()

    assert len(unmapped) == 1
    assert unmapped[0].external_product_id == OFFER_ID
    assert unmapped[0].sold_quantity == 35
    assert unmapped[0].orders_count == 2


async def test_oferta_z_receptura_znika_z_listy_niepowiazanych(
    service: OfferMappingService, orders: FakeOrderRepository
) -> None:
    await _save_the_two_sales(orders)
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])

    assert await service.get_unmapped_offers() == []


async def test_oferta_o_sku_rownym_id_oferty_nie_jest_niepowiazana(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    """Fallback ComponentResolver: SKU = identyfikator oferty też wystarcza."""
    await _save_the_two_sales(orders)
    inventory.items[OFFER_ID] = InventoryItem(
        sku=OFFER_ID, name="Butelka", stock=5, min_stock=0
    )

    assert await service.get_unmapped_offers() == []


async def test_anulowane_zamowienie_nie_zglasza_braku_receptury(
    service: OfferMappingService, orders: FakeOrderRepository
) -> None:
    await orders.save(_make_order("ORDER-003", quantity=5, days_ago=1, status="CANCELLED"))

    assert await service.get_unmapped_offers() == []


async def test_receptura_zapisuje_wszystkie_skladniki(
    service: OfferMappingService, orders: FakeOrderRepository
) -> None:
    await _save_the_two_sales(orders)

    recipe = await service.set_recipe(
        MARKETPLACE,
        OFFER_ID,
        [
            OfferComponent(sku="PET60", quantity=1),
            OfferComponent(sku="KROPL", quantity=1),
            OfferComponent(sku="CAP", quantity=1),
        ],
    )

    assert {c.sku for c in recipe.components} == {"PET60", "KROPL", "CAP"}
    assert recipe.offer_name == "Butelka PET 60 ml z kroplomierzem"


async def test_receptura_zastepuje_poprzednia_zamiast_dokladac(
    service: OfferMappingService,
) -> None:
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])
    recipe = await service.set_recipe(
        MARKETPLACE, OFFER_ID, [OfferComponent(sku="KROPL", quantity=2)]
    )

    assert [(c.sku, c.quantity) for c in recipe.components] == [("KROPL", 2)]


async def test_receptura_odrzuca_powtorzone_sku(service: OfferMappingService) -> None:
    with pytest.raises(ValueError, match="dwa razy"):
        await service.set_recipe(
            MARKETPLACE,
            OFFER_ID,
            [OfferComponent(sku="PET60", quantity=1), OfferComponent(sku="PET60", quantity=2)],
        )


async def test_receptura_odrzuca_nieznane_sku(service: OfferMappingService) -> None:
    with pytest.raises(InventoryItemNotFoundError):
        await service.set_recipe(
            MARKETPLACE, OFFER_ID, [OfferComponent(sku="NIE-MA", quantity=1)]
        )


async def test_podglad_korekty_nie_zmienia_stanow(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    await _save_the_two_sales(orders)
    await service.set_recipe(
        MARKETPLACE,
        OFFER_ID,
        [OfferComponent(sku="PET60", quantity=1), OfferComponent(sku="KROPL", quantity=1)],
    )

    plan = await service.plan_backfill(MARKETPLACE, OFFER_ID)

    assert plan.applied is False
    assert plan.pending_quantity == 35
    assert inventory.items["PET60"].stock == 42
    assert {c.sku: (c.quantity, c.stock_after) for c in plan.components} == {
        "PET60": (35, 7),
        "KROPL": (35, 7),
    }


async def test_korekta_wsteczna_odejmuje_zaleglosc_ze_wszystkich_skladnikow(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    await _save_the_two_sales(orders)
    await service.set_recipe(
        MARKETPLACE,
        OFFER_ID,
        [
            OfferComponent(sku="PET60", quantity=1),
            OfferComponent(sku="KROPL", quantity=1),
            OfferComponent(sku="CAP", quantity=1),
        ],
    )

    plan = await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert plan.applied is True
    assert inventory.items["PET60"].stock == 7
    assert inventory.items["KROPL"].stock == 7
    assert inventory.items["CAP"].stock == 7


async def test_powtorzona_korekta_nie_odejmuje_drugi_raz(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    await _save_the_two_sales(orders)
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])

    await service.apply_backfill(MARKETPLACE, OFFER_ID)
    second = await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert inventory.items["PET60"].stock == 7
    assert second.pending_quantity == 0
    assert all(line.already_applied for line in second.lines)


async def test_korekta_uwzglednia_ilosc_skladnika_w_zestawie(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    """Zestaw 2 nakrętek na sztukę oferty odejmuje 2× więcej nakrętek."""
    await orders.save(_make_order("ORDER-010", quantity=10, days_ago=1))
    inventory.items["CAP"] = InventoryItem(sku="CAP", name="Nakrętka", stock=100, min_stock=0)
    await service.set_recipe(
        MARKETPLACE,
        OFFER_ID,
        [OfferComponent(sku="PET60", quantity=1), OfferComponent(sku="CAP", quantity=2)],
    )

    await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert inventory.items["PET60"].stock == 32
    assert inventory.items["CAP"].stock == 80


async def test_skladnik_dodany_pozniej_dostaje_swoja_zaleglosc(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    """
    Częściowo rozliczone zamówienie trzeba dokończyć, nie pominąć - inaczej
    składnik dopisany do receptury po korekcie zostałby z zawyżonym stanem.
    """
    await _save_the_two_sales(orders)
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])
    await service.apply_backfill(MARKETPLACE, OFFER_ID)

    await service.set_recipe(
        MARKETPLACE,
        OFFER_ID,
        [OfferComponent(sku="PET60", quantity=1), OfferComponent(sku="KROPL", quantity=1)],
    )
    await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert inventory.items["PET60"].stock == 7
    assert inventory.items["KROPL"].stock == 7


async def test_dwie_oferty_z_tym_samym_skladnikiem_rozliczaja_sie_osobno(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    """
    Jedno zamówienie, dwie oferty (30 ml i 60 ml) dzielące nakrętkę.
    Korekta drugiej oferty nie może uznać zamówienia za rozliczone
    tylko dlatego, że pierwsza zdjęła już nakrętki pod tym numerem.
    """
    other_offer = "16899999999"
    order = Order(
        external_id="ORDER-100",
        marketplace=MARKETPLACE,
        buyer=Customer(login="jan_kowalski", email="jan@example.com"),
        products=[
            Product(
                external_id=OFFER_ID,
                name="Butelka 60 ml",
                quantity=4,
                unit_price=Decimal("4.90"),
            ),
            Product(
                external_id=other_offer,
                name="Butelka 30 ml",
                quantity=6,
                unit_price=Decimal("3.90"),
            ),
        ],
        total_amount=Decimal("100.00"),
        currency="PLN",
        status="NEW",
        order_date=utc_now() - timedelta(days=1),
    )
    await orders.save(order)

    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="CAP", quantity=1)])
    await service.apply_backfill(MARKETPLACE, OFFER_ID)
    assert inventory.items["CAP"].stock == 38

    await service.set_recipe(MARKETPLACE, other_offer, [OfferComponent(sku="CAP", quantity=1)])
    await service.apply_backfill(MARKETPLACE, other_offer)

    assert inventory.items["CAP"].stock == 32


async def test_korekta_nie_schodzi_ponizej_zera(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    await orders.save(_make_order("ORDER-020", quantity=100, days_ago=1))
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])

    await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert inventory.items["PET60"].stock == 0


async def test_korekta_bez_receptury_jest_odrzucana(service: OfferMappingService) -> None:
    with pytest.raises(ValueError, match="receptury"):
        await service.plan_backfill(MARKETPLACE, OFFER_ID)


async def test_korekta_pomija_sprzedaz_juz_rozliczona_przez_synchronizacje(
    service: OfferMappingService,
    orders: FakeOrderRepository,
    inventory: FakeInventoryRepository,
) -> None:
    """
    Zamówienie odjęte na bieżąco przez StockSyncService ma już ruch
    z numerem zamówienia - korekta wsteczna musi je zostawić w spokoju.
    """
    from app.domain.entities.inventory_movement import (
        MOVEMENT_SOURCE_ORDER,
        InventoryMovement,
    )

    await _save_the_two_sales(orders)
    await service.set_recipe(MARKETPLACE, OFFER_ID, [OfferComponent(sku="PET60", quantity=1)])
    await inventory.record_movement(
        InventoryMovement(
            item_sku="PET60",
            item_name="Butelka PET 60 ml",
            change=-25,
            stock_after=17,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference="ORDER-001",
            occurred_at=utc_now(),
        )
    )
    await inventory.set_stock("PET60", 17)

    await service.apply_backfill(MARKETPLACE, OFFER_ID)

    assert inventory.items["PET60"].stock == 7

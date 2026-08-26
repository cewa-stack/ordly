"""
Scenariusz akceptacyjny produktów głównych i podproduktów.

Cała droga na PRAWDZIWEJ bazie: relacja zapisana przez serwis, sprzedaż
przez `StockSyncService` z prawdziwą recepturą oferty, a na końcu
historia ruchów - bo to ona odpowiada użytkownikowi na pytanie „skąd
zniknęło 100 nakrętek".

Testy jednostkowe kaskady chodzą po fake repozytorium, które trzyma
`parent_sku` wprost w encji. Tu relacja jest tym, czym jest naprawdę:
kluczem obcym `parent_item_id` i joinem po nim.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.repositories.sqlite_inventory_repository import SqliteInventoryRepository
from app.repositories.sqlite_stock_sync_repository import SqliteStockSyncRepository
from app.services.inventory_service import InventoryService
from app.services.stock_sync_service import StockSyncService

OFERTA = "18752263792"


async def _magazyn_z_podproduktami(session: AsyncSession) -> SqliteInventoryRepository:
    """Butelka 10 ml z nakrętką i kroplomierzem, po 1000 sztuk każdego."""
    repository = SqliteInventoryRepository(session)
    service = InventoryService(repository)
    for sku, name in [
        ("BUT10", "Butelka 10 ml"),
        ("NAK10", "Nakrętka 10 ml"),
        ("KRO10", "Kroplomierz 10 ml"),
    ]:
        await repository.create(InventoryItem(sku=sku, name=name, stock=1000, min_stock=100))
    await service.set_parent("NAK10", "BUT10")
    await service.set_parent("KRO10", "BUT10")

    # Receptura po nowemu: JEDEN składnik, ilość 1 - resztę robi kaskada.
    await repository.add_offer_link("allegro", OFERTA, "BUT10", 1)
    return repository


def _zamowienie(ilosc: int = 100) -> Order:
    return Order(
        external_id="ORDER-100",
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski"),
        products=[Product(OFERTA, "Butelka 10 ml z zakrętką", ilosc, Decimal("1.99"))],
        total_amount=Decimal("199.00"),
        currency="PLN",
        status="READY_FOR_PROCESSING",
        order_date=datetime(2026, 8, 26, 10, 0, 0),
    )


async def test_sprzedaz_stu_sztuk_zdejmuje_sto_z_kazdego_skladnika(
    in_memory_session: AsyncSession,
) -> None:
    """Kryterium akceptacji nr 1."""
    repository = await _magazyn_z_podproduktami(in_memory_session)
    service = StockSyncService(repository, SqliteStockSyncRepository(in_memory_session))

    await service.process_order_created(_zamowienie(100))

    stany = {i.sku: i.stock for i in await repository.get_all()}
    assert stany == {"BUT10": 900, "NAK10": 900, "KRO10": 900}


async def test_kazdy_skladnik_ma_wlasny_wpis_w_historii(
    in_memory_session: AsyncSession,
) -> None:
    """
    Kryterium akceptacji nr 1, druga połowa: `/stock/{sku}/history`
    musi pokazać ruch osobno dla nakrętki, a nie tylko dla butelki.
    """
    repository = await _magazyn_z_podproduktami(in_memory_session)
    service = StockSyncService(repository, SqliteStockSyncRepository(in_memory_session))

    await service.process_order_created(_zamowienie(100))

    for sku in ("BUT10", "NAK10", "KRO10"):
        ruchy = await repository.get_movements(sku, limit=10)
        assert len(ruchy) == 1, sku
        assert ruchy[0].change == -100
        assert ruchy[0].stock_after == 900
        assert ruchy[0].reference == "ORDER-100"

    nakretka = (await repository.get_movements("NAK10", limit=1))[0]
    assert "podprodukt: BUT10" in nakretka.reason


async def test_anulowanie_przywraca_wszystkie_trzy_stany(
    in_memory_session: AsyncSession,
) -> None:
    """Kryterium akceptacji nr 2 (anulowanie)."""
    repository = await _magazyn_z_podproduktami(in_memory_session)
    service = StockSyncService(repository, SqliteStockSyncRepository(in_memory_session))
    order = _zamowienie(100)

    await service.process_order_created(order)
    await service.process_order_cancelled(order)

    stany = {i.sku: i.stock for i in await repository.get_all()}
    assert stany == {"BUT10": 1000, "NAK10": 1000, "KRO10": 1000}


async def test_zwrot_przywraca_wszystkie_trzy_stany(
    in_memory_session: AsyncSession,
) -> None:
    """Kryterium akceptacji nr 2 (zwrot)."""
    repository = await _magazyn_z_podproduktami(in_memory_session)
    sync_repository = SqliteStockSyncRepository(in_memory_session)
    service = StockSyncService(repository, sync_repository)

    await service.process_order_created(_zamowienie(100))
    await service.process_return(
        OrderReturn(
            external_id="ZWROT-1",
            order_external_id="ORDER-100",
            marketplace="allegro",
            buyer_login="jan_kowalski",
            products=[Product(OFERTA, "Butelka 10 ml z zakrętką", 40, Decimal("1.99"))],
            status="CREATED",
            created_at=datetime(2026, 8, 27, 10, 0, 0),
        )
    )

    stany = {i.sku: i.stock for i in await repository.get_all()}
    assert stany == {"BUT10": 940, "NAK10": 940, "KRO10": 940}


async def test_reczna_korekta_rusza_tylko_produkt_glowny(
    in_memory_session: AsyncSession,
) -> None:
    """
    Kryterium akceptacji nr 3 - regresja świadomej decyzji.

    Dostawa 50 butelek nie oznacza 50 nakrętek: przyjeżdżają w osobnych
    kartonach i liczy się je osobno.
    """
    repository = await _magazyn_z_podproduktami(in_memory_session)
    service = InventoryService(repository)

    await service.add_stock("BUT10", 50, "Dostawa")

    stany = {i.sku: i.stock for i in await repository.get_all()}
    assert stany == {"BUT10": 1050, "NAK10": 1000, "KRO10": 1000}
    assert await repository.get_movements("NAK10", limit=10) == []

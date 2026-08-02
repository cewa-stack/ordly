"""
Test integracyjny transakcyjności odejmowania komponentów (funkcja 04).

Weryfikuje wymaganie bezpieczeństwa ze specyfikacji: jeżeli aktualizacja
któregokolwiek składnika zestawu zakończy się błędem, CAŁA operacja
magazynowa zostaje wycofana (żaden składnik nie zostaje odjęty, znacznik
synchronizacji nie zostaje ustawiony - możliwa jest ponowna próba).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.repositories.sqlite_inventory_repository import SqliteInventoryRepository
from app.repositories.sqlite_stock_sync_repository import SqliteStockSyncRepository
from app.services.stock_sync_service import OPERATION_DEDUCT, StockSyncService


class _FailingInventoryRepository(SqliteInventoryRepository):
    """Repozytorium, które celowo zawodzi przy ustawianiu stanu jednego SKU."""

    def __init__(self, session: AsyncSession, failing_sku: str) -> None:
        super().__init__(session)
        self._failing_sku = failing_sku

    async def set_stock(self, sku: str, new_stock: int) -> None:
        if sku == self._failing_sku:
            raise RuntimeError("Symulowany błąd aktualizacji składnika")
        await super().set_stock(sku, new_stock)


def _make_kit_order() -> Order:
    return Order(
        external_id="KIT-ORDER",
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski"),
        products=[Product("KIT-1", "Zestaw Premium", 1, Decimal("59.99"))],
        total_amount=Decimal("59.99"),
        currency="PLN",
        status="READY_FOR_PROCESSING",
        order_date=datetime(2026, 7, 20, 10, 0, 0),
    )


async def test_blad_skladnika_wycofuje_cala_operacje(
    in_memory_session: AsyncSession,
) -> None:
    setup_repository = SqliteInventoryRepository(in_memory_session)
    await setup_repository.create(
        InventoryItem(sku="PET60", name="Butelka", stock=100, min_stock=10)
    )
    await setup_repository.create(
        InventoryItem(sku="CAP", name="Nakrętka", stock=100, min_stock=10)
    )
    # Zestaw KIT-1 = Butelka + Nakrętka.
    await setup_repository.add_offer_link("allegro", "KIT-1", "PET60", 1)
    await setup_repository.add_offer_link("allegro", "KIT-1", "CAP", 1)
    await in_memory_session.commit()

    # Aktualizacja składnika CAP zawiedzie - Butelka jest odejmowana wcześniej.
    failing_repository = _FailingInventoryRepository(in_memory_session, failing_sku="CAP")
    service = StockSyncService(
        inventory_repository=failing_repository,
        stock_sync_repository=SqliteStockSyncRepository(in_memory_session),
    )

    with pytest.raises(RuntimeError):
        async with in_memory_session.begin_nested():
            await service.process_order_created(_make_kit_order())

    # Po wycofaniu: stany bez zmian, brak ruchów, brak znacznika (retry możliwy).
    verify_repository = SqliteInventoryRepository(in_memory_session)
    pet = await verify_repository.get_by_sku("PET60")
    cap = await verify_repository.get_by_sku("CAP")
    assert pet is not None and pet.stock == 100
    assert cap is not None and cap.stock == 100

    movements = await verify_repository.get_movements(limit=10)
    assert movements == []

    markers = SqliteStockSyncRepository(in_memory_session)
    assert (await markers.was_processed("allegro", "KIT-ORDER", OPERATION_DEDUCT)) is False

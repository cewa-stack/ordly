"""Testy jednostkowe StockSyncService (Automatic Stock Synchronization)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.entities.customer import Customer
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.services.stock_sync_service import StockSyncService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_stock_sync_repository import FakeStockSyncRepository


def _make_order(products: list[Product], external_id: str = "ORDER-001") -> Order:
    return Order(
        external_id=external_id,
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski", email="jan@example.com"),
        products=products,
        total_amount=Decimal("100.00"),
        currency="PLN",
        status="NEW",
        order_date=datetime(2026, 7, 19, 10, 0, 0),
    )


@pytest.fixture
def inventory() -> FakeInventoryRepository:
    repository = FakeInventoryRepository()
    repository.items["PET60"] = InventoryItem(
        sku="PET60", name="Butelka PET 60 ml", stock=320, min_stock=50
    )
    repository.items["PIPETA"] = InventoryItem(
        sku="PIPETA", name="Pipeta 3 ml", stock=90, min_stock=20
    )
    repository.items["CAP"] = InventoryItem(
        sku="CAP", name="Nakrętka czarna", stock=100, min_stock=10
    )
    return repository


@pytest.fixture
def sync_markers() -> FakeStockSyncRepository:
    return FakeStockSyncRepository()


@pytest.fixture
def service(
    inventory: FakeInventoryRepository, sync_markers: FakeStockSyncRepository
) -> StockSyncService:
    return StockSyncService(inventory, sync_markers)


async def test_order_deducts_stock_by_sku_fallback(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order(
        [
            Product("PET60", "Butelka PET 60 ml", 2, Decimal("5.00")),
            Product("PIPETA", "Pipeta 3 ml", 5, Decimal("1.00")),
        ]
    )

    outcome = await service.process_order_created(order)

    assert outcome.processed is True
    assert inventory.items["PET60"].stock == 318
    assert inventory.items["PIPETA"].stock == 85
    assert len(inventory.movements) == 2
    assert all(m.source == "order" for m in inventory.movements)
    assert all(m.reference == "ORDER-001" for m in inventory.movements)


async def test_order_is_not_processed_twice(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PET60", "Butelka PET 60 ml", 2, Decimal("5.00"))])

    first = await service.process_order_created(order)
    second = await service.process_order_created(order)

    assert first.processed is True
    assert second.processed is False
    assert inventory.items["PET60"].stock == 318


async def test_kit_offer_deducts_all_components(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    await inventory.add_offer_link("allegro", "KIT-1", "PET60", 2)
    await inventory.add_offer_link("allegro", "KIT-1", "CAP", 2)
    await inventory.add_offer_link("allegro", "KIT-1", "PIPETA", 1)
    order = _make_order([Product("KIT-1", "Starter Kit", 1, Decimal("30.00"))])

    outcome = await service.process_order_created(order)

    assert outcome.processed is True
    assert inventory.items["PET60"].stock == 318
    assert inventory.items["CAP"].stock == 98
    assert inventory.items["PIPETA"].stock == 89


async def test_unmatched_product_is_reported(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("UNKNOWN", "Tajemniczy produkt", 1, Decimal("9.99"))])

    outcome = await service.process_order_created(order)

    assert outcome.processed is True
    assert outcome.unmatched_products == ("Tajemniczy produkt (UNKNOWN)",)
    assert inventory.movements == []


async def test_low_stock_is_detected_after_deduction(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PIPETA", "Pipeta 3 ml", 75, Decimal("1.00"))])

    outcome = await service.process_order_created(order)

    assert inventory.items["PIPETA"].stock == 15
    assert [item.sku for item in outcome.low_stock_items] == ["PIPETA"]


async def test_stock_never_goes_below_zero(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PIPETA", "Pipeta 3 ml", 200, Decimal("1.00"))])

    await service.process_order_created(order)

    assert inventory.items["PIPETA"].stock == 0
    assert inventory.movements[0].change == -90


async def test_cancellation_restores_previous_deduction(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PET60", "Butelka PET 60 ml", 2, Decimal("5.00"))])
    await service.process_order_created(order)

    outcome = await service.process_order_cancelled(order)

    assert outcome.processed is True
    assert inventory.items["PET60"].stock == 320
    assert inventory.movements[-1].source == "cancellation"


async def test_cancellation_without_prior_deduction_is_skipped(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PET60", "Butelka PET 60 ml", 2, Decimal("5.00"))])

    outcome = await service.process_order_cancelled(order)

    assert outcome.processed is False
    assert inventory.items["PET60"].stock == 320


async def test_cancellation_is_not_processed_twice(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order = _make_order([Product("PET60", "Butelka PET 60 ml", 2, Decimal("5.00"))])
    await service.process_order_created(order)
    await service.process_order_cancelled(order)

    outcome = await service.process_order_cancelled(order)

    assert outcome.processed is False
    assert inventory.items["PET60"].stock == 320


async def test_return_restores_returned_quantity(
    service: StockSyncService, inventory: FakeInventoryRepository
) -> None:
    order_return = OrderReturn(
        external_id="RETURN-001",
        marketplace="allegro",
        order_external_id="ORDER-001",
        buyer_login="jan_kowalski",
        products=[Product("PET60", "Butelka PET 60 ml", 1, Decimal("5.00"))],
        status="CREATED",
        created_at=datetime(2026, 7, 20, 12, 0, 0),
    )

    outcome = await service.process_return(order_return)
    repeated = await service.process_return(order_return)

    assert outcome.processed is True
    assert repeated.processed is False
    assert inventory.items["PET60"].stock == 321
    assert inventory.movements[-1].source == "return"


class TestKaskadaNaPodprodukty:
    """
    Sprzedaż butelki zdejmuje też nakrętkę i kroplomierz.

    To jedyne miejsce, gdzie kaskada spotyka się z prawdziwym
    dokumentem sprzedaży - z jego ilością, znacznikiem idempotencji
    i recepturą oferty. Reguła 1:1 sama w sobie jest sprawdzona
    w `test_sub_item_cascade`.
    """

    @staticmethod
    def _z_podproduktami() -> FakeInventoryRepository:
        repository = FakeInventoryRepository()
        repository.items["BUT10"] = InventoryItem(
            sku="BUT10", name="Butelka 10 ml", stock=500, min_stock=50
        )
        repository.items["NAK10"] = InventoryItem(
            sku="NAK10", name="Nakrętka 10 ml", stock=500, min_stock=50, parent_sku="BUT10"
        )
        repository.items["KRO10"] = InventoryItem(
            sku="KRO10",
            name="Kroplomierz 10 ml",
            stock=500,
            min_stock=50,
            parent_sku="BUT10",
        )
        return repository

    async def test_sprzedaz_stu_butelek_zdejmuje_sto_nakretek(self) -> None:
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        service = StockSyncService(inventory, FakeStockSyncRepository())

        await service.process_order_created(
            _make_order([Product("OFERTA-1", "Butelka 10 ml", 100, Decimal("1.99"))])
        )

        assert inventory.items["BUT10"].stock == 400
        assert inventory.items["NAK10"].stock == 400
        assert inventory.items["KRO10"].stock == 400

    async def test_anulowanie_przywraca_wszystkie_trzy_stany(self) -> None:
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        markers = FakeStockSyncRepository()
        service = StockSyncService(inventory, markers)
        order = _make_order([Product("OFERTA-1", "Butelka 10 ml", 100, Decimal("1.99"))])

        await service.process_order_created(order)
        await service.process_order_cancelled(order)

        assert inventory.items["BUT10"].stock == 500
        assert inventory.items["NAK10"].stock == 500
        assert inventory.items["KRO10"].stock == 500

    async def test_zwrot_przywraca_wszystkie_trzy_stany(self) -> None:
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        service = StockSyncService(inventory, FakeStockSyncRepository())

        await service.process_return(
            OrderReturn(
                external_id="ZWROT-1",
                order_external_id="ORDER-001",
                marketplace="allegro",
                buyer_login="jan_kowalski",
                products=[Product("OFERTA-1", "Butelka 10 ml", 10, Decimal("1.99"))],
                status="CREATED",
                created_at=datetime(2026, 7, 20, 10, 0, 0),
            )
        )

        assert inventory.items["BUT10"].stock == 510
        assert inventory.items["NAK10"].stock == 510
        assert inventory.items["KRO10"].stock == 510

    async def test_receptura_z_mnoznikiem_mnozy_takze_podprodukty(self) -> None:
        """
        Zestaw "2 butelki w komplecie": receptura mówi 2 butelki na
        sztukę, więc 5 zestawów to 10 butelek - i tyle samo nakrętek.
        """
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "ZESTAW", "BUT10", 2)
        service = StockSyncService(inventory, FakeStockSyncRepository())

        await service.process_order_created(
            _make_order([Product("ZESTAW", "Zestaw", 5, Decimal("9.99"))])
        )

        assert inventory.items["BUT10"].stock == 490
        assert inventory.items["NAK10"].stock == 490

    async def test_stara_receptura_nie_odejmuje_nakretki_dwa_razy(self) -> None:
        """
        Okno przejściowe z instrukcji migracji: użytkownik ustawił już
        relację produkt główny/podprodukt, ale receptura oferty nadal
        wymienia butelkę i nakrętkę osobno. Bez pominięcia składników
        receptury nakrętka schodziłaby podwójnie przy każdej sprzedaży.
        """
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        await inventory.add_offer_link("allegro", "OFERTA-1", "NAK10", 1)
        service = StockSyncService(inventory, FakeStockSyncRepository())

        await service.process_order_created(
            _make_order([Product("OFERTA-1", "Butelka", 100, Decimal("1.99"))])
        )

        assert inventory.items["NAK10"].stock == 400
        assert inventory.items["KRO10"].stock == 400

    async def test_podprodukt_ponizej_progu_trafia_do_ostrzezen(self) -> None:
        """Kończące się nakrętki trzeba dokupić tak samo jak butelki."""
        inventory = self._z_podproduktami()
        inventory.items["KRO10"] = InventoryItem(
            sku="KRO10", name="Kroplomierz 10 ml", stock=60, min_stock=50, parent_sku="BUT10"
        )
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        service = StockSyncService(inventory, FakeStockSyncRepository())

        outcome = await service.process_order_created(
            _make_order([Product("OFERTA-1", "Butelka", 20, Decimal("1.99"))])
        )

        assert [item.sku for item in outcome.low_stock_items] == ["KRO10"]

    async def test_powtorzona_synchronizacja_nie_dubluje_kaskady(self) -> None:
        """Znacznik idempotencji chroni podprodukty tak samo jak rodzica."""
        inventory = self._z_podproduktami()
        await inventory.add_offer_link("allegro", "OFERTA-1", "BUT10", 1)
        markers = FakeStockSyncRepository()
        service = StockSyncService(inventory, markers)
        order = _make_order([Product("OFERTA-1", "Butelka 10 ml", 100, Decimal("1.99"))])

        await service.process_order_created(order)
        await service.process_order_created(order)

        assert inventory.items["NAK10"].stock == 400

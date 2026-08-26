"""
Testy komendy `/stock parent` - podprodukty z poziomu czatu.

Ta komenda robi w bocie coś, czego desktop nie potrafi w drugą stronę:
odłącza podprodukt, który zniknął już z listy magazynowej. Dlatego
sprawdzana jest tu obie strony powiązania i to, że błąd reguły
zagnieżdżenia wraca jako czytelna wiadomość, a nie jako "Wystąpił błąd".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.bot.handlers.stock import handle_stock
from app.domain.entities.inventory_item import InventoryItem
from app.services.inventory_service import InventoryService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository


class FakeContainer:
    """Kontener zwracający serwis magazynowy na fake repozytorium."""

    def __init__(self, repository: FakeInventoryRepository) -> None:
        self._repository = repository

    def inventory_service(self, _session) -> InventoryService:
        return InventoryService(self._repository)


def _repozytorium() -> FakeInventoryRepository:
    repository = FakeInventoryRepository()
    for sku, name in [
        ("BUT10", "Butelka 10 ml"),
        ("NAK10", "Nakrętka 10 ml"),
        ("KRO10", "Kroplomierz 10 ml"),
    ]:
        repository.items[sku] = InventoryItem(sku=sku, name=name, stock=500, min_stock=50)
    return repository


async def _wywolaj(repository: FakeInventoryRepository, args: str) -> str:
    """Uruchamia `/stock <args>` i zwraca treść odpowiedzi bota."""
    message = MagicMock()
    message.answer = AsyncMock()
    command = MagicMock()
    command.args = args

    await handle_stock(message, command, FakeContainer(repository), session=None)

    message.answer.assert_awaited_once()
    return str(message.answer.call_args.args[0])


class TestPowiazanie:
    async def test_przypisuje_podprodukt(self) -> None:
        repository = _repozytorium()

        odpowiedz = await _wywolaj(repository, "parent NAK10 BUT10")

        assert repository.items["NAK10"].parent_sku == "BUT10"
        assert "NAK10" in odpowiedz
        assert "BUT10" in odpowiedz

    async def test_mysinik_odlacza(self) -> None:
        """Jedyna droga odłączenia z czatu - i najprostsza w ogóle."""
        repository = _repozytorium()
        await _wywolaj(repository, "parent NAK10 BUT10")

        odpowiedz = await _wywolaj(repository, "parent NAK10 -")

        assert repository.items["NAK10"].parent_sku is None
        assert "samodzielnym" in odpowiedz

    async def test_liczy_podprodukty_w_potwierdzeniu(self) -> None:
        repository = _repozytorium()
        await _wywolaj(repository, "parent NAK10 BUT10")

        odpowiedz = await _wywolaj(repository, "parent KRO10 BUT10")

        assert "2 podprodukty" in odpowiedz


class TestBledy:
    async def test_zla_liczba_argumentow_pokazuje_przyklad(self) -> None:
        repository = _repozytorium()

        odpowiedz = await _wywolaj(repository, "parent NAK10")

        assert "/stock parent NAK10 BUT10" in odpowiedz
        assert repository.items["NAK10"].parent_sku is None

    async def test_nieistniejacy_produkt_glowny(self) -> None:
        repository = _repozytorium()

        odpowiedz = await _wywolaj(repository, "parent NAK10 NIE-MA")

        assert "Nie znaleziono produktu" in odpowiedz
        assert "NIE-MA" in odpowiedz

    async def test_drugi_poziom_zagniezdzenia_to_czytelny_komunikat(self) -> None:
        """
        Nie "Wystąpił błąd podczas obsługi magazynu" - handler łapie
        `ValueError` i pokazuje jego treść.
        """
        repository = _repozytorium()
        await _wywolaj(repository, "parent NAK10 BUT10")

        odpowiedz = await _wywolaj(repository, "parent KRO10 NAK10")

        assert "jednopoziomowe" in odpowiedz
        assert repository.items["KRO10"].parent_sku is None


class TestPomoc:
    async def test_komenda_jest_w_sciagawce(self) -> None:
        """Komenda spoza ściągawki byłaby funkcją, o której nikt nie wie."""
        odpowiedz = await _wywolaj(_repozytorium(), "cokolwiek")

        assert "/stock parent" in odpowiedz

"""
Testy magazynu ORDLY: katalog wystawionych ofert i ręczna ilość przy każdej.

Sedno tego serwisu to trwałość liczby wpisanej przez człowieka. Asortyment
schodzi z marketplace przy każdej synchronizacji, ale ilość na półce nie ma
tam swojego źródła - jeśli zgubi się przy odświeżeniu, nie da się jej
odtworzyć z niczego poza ponownym liczeniem towaru.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.exceptions.domain_exceptions import (
    MarketplaceUnavailableError,
    OfferNotFoundError,
)
from app.services.offer_catalog_service import OfferCatalogService
from app.utils.time import utc_now
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_offer_catalog_repository import FakeOfferCatalogRepository


def _offer(
    external_id: str,
    name: str = "Oferta testowa",
    signature: str | None = None,
    available_stock: int = 0,
    price: Decimal | None = None,
) -> MarketplaceOffer:
    """Buduje ofertę katalogu z sensownymi wartościami domyślnymi."""
    return MarketplaceOffer(
        marketplace="allegro",
        external_id=external_id,
        name=name,
        signature=signature,
        available_stock=available_stock,
        price=price,
        synced_at=utc_now(),
    )


@pytest.fixture
def catalog() -> FakeOfferCatalogRepository:
    """Pusty katalog ofert w pamięci."""
    return FakeOfferCatalogRepository()


@pytest.fixture
def plugin() -> FakeMarketplacePlugin:
    """Plugin marketplace zwracający zaprogramowany asortyment."""
    return FakeMarketplacePlugin()


@pytest.fixture
def service(
    plugin: FakeMarketplacePlugin, catalog: FakeOfferCatalogRepository
) -> OfferCatalogService:
    """Serwis magazynu zbudowany na fake'ach."""
    return OfferCatalogService(plugin=plugin, catalog_repository=catalog)


class TestSynchronizacjaKatalogu:
    """Pobieranie asortymentu z marketplace do lokalnego katalogu."""

    async def test_zapisuje_pobrane_oferty_do_katalogu(self, service, plugin, catalog):
        """Oferty z pluginu trafiają do katalogu i są widoczne w podsumowaniu."""
        plugin.offers = [_offer("111", "Butelka 60 ml"), _offer("222", "Nakrętka")]

        result = await service.sync()

        assert result.fetched == 2
        assert result.added == 2
        assert result.removed == 0
        assert len(await catalog.get_all("allegro")) == 2

    async def test_usuwa_oferty_ktorych_juz_nie_ma_na_allegro(self, service, plugin, catalog):
        """
        Oferta wycofana ze sprzedaży musi zniknąć z magazynu, inaczej lista
        rosłaby o martwe pozycje bez żadnego sygnału, że ich już nie ma.
        """
        plugin.offers = [_offer("111"), _offer("222")]
        await service.sync()

        plugin.offers = [_offer("111")]
        result = await service.sync()

        assert result.removed == 1
        assert [o.external_id for o in await catalog.get_all("allegro")] == ["111"]

    async def test_ponowna_synchronizacja_nie_liczy_znanych_ofert_jako_nowych(
        self, service, plugin
    ):
        """Ta sama oferta drugi raz to aktualizacja, nie nowa pozycja."""
        plugin.offers = [_offer("111")]
        await service.sync()

        result = await service.sync()

        assert result.added == 0
        assert result.fetched == 1

    async def test_synchronizacja_odswieza_dane_oferty(self, service, plugin):
        """Cena i nazwa schodzą z API przy każdym odświeżeniu."""
        plugin.offers = [_offer("111", name="Butelka", price=Decimal("12.90"))]
        await service.sync()

        plugin.offers = [_offer("111", name="Butelka 60 ml", price=Decimal("14.50"))]
        await service.sync()

        offer = (await service.get_offers())[0]
        assert offer.name == "Butelka 60 ml"
        assert offer.price == Decimal("14.50")

    async def test_recznie_wpisana_ilosc_przezywa_synchronizacje(self, service, plugin):
        """
        KLUCZOWE. Ilość na półce nie ma źródła w API - gdyby znikała przy
        odświeżeniu asortymentu, jedynym sposobem odtworzenia byłoby
        ponowne przeliczenie towaru ręcznie.
        """
        plugin.offers = [_offer("111", name="Butelka", price=Decimal("12.90"))]
        await service.sync()
        await service.set_quantity("allegro", "111", 7, "Inwentaryzacja")

        plugin.offers = [_offer("111", name="Butelka 60 ml", price=Decimal("14.50"))]
        await service.sync()

        offer = (await service.get_offers())[0]
        assert offer.quantity_on_hand == 7

    async def test_awaria_allegro_nie_czysci_katalogu(self, service, plugin, catalog):
        """
        Błąd API kończy się `MarketplaceUnavailableError`, a katalog zostaje
        nietknięty - lepiej pokazać wczorajszy asortyment niż skasować
        ręcznie wpisane ilości przez chwilową awarię sieci.
        """
        plugin.offers = [_offer("111")]
        await service.sync()
        await service.set_quantity("allegro", "111", 3, "Inwentaryzacja")

        plugin.should_raise_offers_api_error = True
        with pytest.raises(MarketplaceUnavailableError):
            await service.sync()

        offers = await catalog.get_all("allegro")
        assert len(offers) == 1
        assert offers[0].quantity_on_hand == 3


class TestRecznaIlosc:
    """Wpisywanie ilości policzonej na półce."""

    async def test_zapisuje_wpisana_ilosc(self, service, plugin):
        """Serwis zwraca ofertę z nową ilością."""
        plugin.offers = [_offer("111")]
        await service.sync()

        offer = await service.set_quantity("allegro", "111", 12, "Inwentaryzacja")

        assert offer.quantity_on_hand == 12

    async def test_brak_ilosci_to_nie_zero(self, service, plugin):
        """
        Nowa oferta ma ilość `None`, nie zero. "Nigdy nie liczyłem" i
        "policzyłem, nie ma" to dwie różne odpowiedzi na pytanie "ile mam".
        """
        plugin.offers = [_offer("111")]
        await service.sync()

        assert (await service.get_offers())[0].quantity_on_hand is None

    async def test_nieznana_oferta_konczy_sie_bledem(self, service):
        """Ilości nie da się wpisać przy czymś, czego nie ma w katalogu."""
        with pytest.raises(OfferNotFoundError):
            await service.set_quantity("allegro", "nie-ma-takiej", 1, "Inwentaryzacja")


class TestHistoriaZmian:
    """Każdy ręczny wpis zostawia ślad."""

    async def test_kazdy_wpis_doklada_pozycje_historii(self, service, plugin):
        """Historia rośnie z każdym liczeniem, od najnowszego wpisu."""
        plugin.offers = [_offer("111")]
        await service.sync()

        await service.set_quantity("allegro", "111", 10, "Inwentaryzacja")
        await service.set_quantity("allegro", "111", 4, "Sprzedaż na targu")

        history = await service.get_history("allegro", "111")
        assert [(m.quantity_after, m.reason) for m in history] == [
            (4, "Sprzedaż na targu"),
            (10, "Inwentaryzacja"),
        ]

    async def test_historia_zapisuje_roznice_wzgledem_poprzedniego_stanu(self, service, plugin):
        """Wpis trzyma deltę, żeby było widać kierunek zmiany."""
        plugin.offers = [_offer("111")]
        await service.sync()

        await service.set_quantity("allegro", "111", 10, "Inwentaryzacja")
        await service.set_quantity("allegro", "111", 4, "Sprzedaż na targu")

        assert [m.change for m in await service.get_history("allegro", "111")] == [-6, 10]

    async def test_limit_przycina_historie(self, service, plugin):
        """Podany limit ogranicza liczbę zwróconych wpisów."""
        plugin.offers = [_offer("111")]
        await service.sync()
        for quantity in range(5):
            await service.set_quantity("allegro", "111", quantity, "Inwentaryzacja")

        assert len(await service.get_history("allegro", "111", limit=2)) == 2

    async def test_historia_nieznanej_oferty_konczy_sie_bledem(self, service):
        """Historia dotyczy konkretnej oferty, więc jej brak to błąd."""
        with pytest.raises(OfferNotFoundError):
            await service.get_history("allegro", "nie-ma-takiej")

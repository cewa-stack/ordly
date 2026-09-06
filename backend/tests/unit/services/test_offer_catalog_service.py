"""
Testy katalogu asortymentu marketplace i jego powiązań z magazynem.

Sedno tego serwisu to uczciwość wobec `ComponentResolver`: katalog ma
pokazywać ofertę jako powiązaną DOKŁADNIE wtedy, gdy jej sprzedaż
naprawdę zdejmie stan. Dlatego większość testów sprawdza nie "czy się
zapisało", tylko czy stan powiązania zgadza się z tym, co resolver
potrafi rozwiązać.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.product import Product
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.services.component_resolver import ComponentResolver
from app.services.offer_catalog_service import OfferCatalogService
from app.shared.dto.offer_catalog_dto import (
    LINK_NONE,
    LINK_RECIPE,
    LINK_SIGNATURE,
    LINK_SKU,
)
from app.utils.time import utc_now
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
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


def _item(sku: str, name: str = "Produkt", stock: int = 10) -> InventoryItem:
    """Buduje produkt magazynowy."""
    return InventoryItem(sku=sku, name=name, stock=stock, min_stock=0)


@pytest.fixture
def inventory() -> FakeInventoryRepository:
    """Pusty magazyn w pamięci."""
    return FakeInventoryRepository()


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
    plugin: FakeMarketplacePlugin,
    catalog: FakeOfferCatalogRepository,
    inventory: FakeInventoryRepository,
) -> OfferCatalogService:
    """Serwis katalogu zbudowany na fake'ach."""
    return OfferCatalogService(
        plugin=plugin, catalog_repository=catalog, inventory_repository=inventory
    )


class TestSynchronizacjaKatalogu:
    """Pobieranie asortymentu z marketplace do lokalnego katalogu."""

    async def test_zapisuje_pobrane_oferty_do_katalogu(self, service, plugin, catalog):
        """Oferty z pluginu trafiają do katalogu i są widoczne w podsumowaniu."""
        plugin.offers = [_offer("111", "Butelka 60 ml"), _offer("222", "Nakrętka")]

        result = await service.sync()

        assert result.fetched == 2
        assert result.unlinked == 2
        assert len(await catalog.get_all("allegro")) == 2

    async def test_usuwa_oferty_ktorych_juz_nie_ma_na_allegro(self, service, plugin, catalog):
        """
        Katalog jest podmieniany w całości, nie dopisywany.

        Oferta wycofana ze sprzedaży musi zniknąć z listy do powiązania,
        inaczej katalog rósłby o martwe pozycje bez żadnego sygnału.
        """
        plugin.offers = [_offer("111"), _offer("222")]
        await service.sync()

        plugin.offers = [_offer("111")]
        await service.sync()

        assert [o.external_id for o in await catalog.get_all("allegro")] == ["111"]

    async def test_awaria_allegro_nie_czysci_katalogu(self, service, plugin, catalog):
        """
        Błąd API kończy się `MarketplaceUnavailableError`, a katalog
        zostaje nietknięty - lepiej pokazać wczorajszy asortyment niż
        skasować powiązania przez chwilową awarię sieci.
        """
        plugin.offers = [_offer("111")]
        await service.sync()

        plugin.should_raise_offers_api_error = True
        with pytest.raises(MarketplaceUnavailableError):
            await service.sync()

        assert len(await catalog.get_all("allegro")) == 1


class TestAutomatycznePowiazanie:
    """Dowiązywanie ofert do magazynu po sygnaturze sprzedawcy."""

    async def test_wiaze_oferte_gdy_sygnatura_wskazuje_istniejace_sku(
        self, service, plugin, inventory
    ):
        """Sygnatura równa SKU zakłada recepturę jednoskładnikową."""
        await inventory.create(_item("BUT60", "Butelka 60 ml"))
        plugin.offers = [_offer("111", signature="BUT60")]

        result = await service.sync()

        assert result.auto_linked == 1
        assert result.unlinked == 0
        links = await inventory.get_offer_links("allegro", "111")
        assert [(c.sku, c.quantity) for c in links] == [("BUT60", 1)]

    async def test_nie_wiaze_po_nazwie_oferty(self, service, plugin, inventory):
        """
        Nazwa oferty jest tekstem marketingowym i NIE może być podstawą
        powiązania - błędne dopasowanie odejmuje realny towar z półki.
        """
        await inventory.create(_item("BUT60", "Butelka 60 ml"))
        plugin.offers = [_offer("111", name="Butelka 60 ml szkło + kroplomierz GRATIS")]

        result = await service.sync()

        assert result.auto_linked == 0
        assert await inventory.get_offer_links("allegro", "111") == []

    async def test_nie_nadpisuje_istniejacej_receptury(self, service, plugin, inventory):
        """Ręczna receptura użytkownika jest ważniejsza od zgadywania."""
        await inventory.create(_item("BUT60", "Butelka 60 ml"))
        await inventory.create(_item("KRO", "Kroplomierz"))
        await inventory.add_offer_link("allegro", "111", "KRO", 2)
        plugin.offers = [_offer("111", signature="BUT60")]

        result = await service.sync()

        assert result.auto_linked == 0
        links = await inventory.get_offer_links("allegro", "111")
        assert [(c.sku, c.quantity) for c in links] == [("KRO", 2)]

    async def test_pusta_sygnatura_nie_laczy_ofert_ze_soba(self, service, plugin, inventory):
        """Dwie oferty bez sygnatury nie mogą wpaść w ten sam produkt."""
        await inventory.create(_item("BUT60"))
        plugin.offers = [_offer("111", signature=None), _offer("222", signature=None)]

        result = await service.sync()

        assert result.auto_linked == 0

    async def test_relink_wiaze_produkt_zalozony_po_synchronizacji(
        self, service, plugin, inventory
    ):
        """
        Dopasowanie po sygnaturze zależy od obu stron. Produkt założony
        PO synchronizacji musi dać się dowiązać bez ponownego ściągania
        całego asortymentu.
        """
        plugin.offers = [_offer("111", signature="BUT60")]
        await service.sync()
        assert await inventory.get_offer_links("allegro", "111") == []

        await inventory.create(_item("BUT60"))
        linked = await service.relink()

        assert linked == 1
        assert len(await inventory.get_offer_links("allegro", "111")) == 1


class TestStanPowiazania:
    """Katalog musi opowiadać dokładnie to, co potrafi zrobić resolver."""

    async def test_oferta_z_receptura_jest_powiazana(self, service, plugin, inventory):
        """Jawna receptura to stan `recipe`."""
        await inventory.create(_item("BUT60", "Butelka 60 ml"))
        await inventory.add_offer_link("allegro", "111", "BUT60", 1)
        plugin.offers = [_offer("111")]
        await service.sync()

        offer = (await service.get_catalog())[0]

        assert offer.link_type == LINK_RECIPE
        assert offer.is_linked is True

    async def test_oferta_trafiajaca_po_sku_jest_powiazana(self, service, plugin, inventory):
        """
        Produkt o SKU równym identyfikatorowi oferty działa bez receptury -
        resolver ma taki fallback, więc katalog nie może wołać o naprawę,
        której nie potrzeba.
        """
        await inventory.create(_item("111", "Butelka po ID oferty"))
        plugin.offers = [_offer("111")]
        await service.sync()

        offer = (await service.get_catalog())[0]

        assert offer.link_type == LINK_SKU
        assert offer.is_linked is True

    async def test_sama_sygnatura_to_jeszcze_nie_powiazanie(self, service, plugin, inventory):
        """
        KLUCZOWE. Resolver NIE zna sygnatur. Dopóki receptura nie jest
        zapisana, oferta z pasującą sygnaturą nadal przechodzi obok
        magazynu - i katalog musi to przyznać, zamiast pokazywać zielony
        haczyk nad czymś, co nie odejmuje stanu.
        """
        plugin.offers = [_offer("111", signature="BUT60")]
        await service.sync()
        await inventory.create(_item("BUT60"))

        offer = (await service.get_catalog())[0]

        assert offer.link_type == LINK_SIGNATURE
        assert offer.is_linked is False

    async def test_oferta_bez_niczego_jest_niepowiazana(self, service, plugin):
        """Brak receptury, SKU i sygnatury to stan `none`."""
        plugin.offers = [_offer("111")]
        await service.sync()

        offer = (await service.get_catalog())[0]

        assert offer.link_type == LINK_NONE
        assert offer.is_linked is False

    async def test_filtr_zwraca_tylko_oferty_nieruszajace_magazynu(
        self, service, plugin, inventory
    ):
        """`only_unlinked` musi przepuścić też ofertę z samą sygnaturą."""
        await inventory.create(_item("BUT60"))
        await inventory.create(_item("KRO"))
        await inventory.add_offer_link("allegro", "111", "KRO", 1)
        plugin.offers = [
            _offer("111", name="Z recepturą"),
            _offer("222", name="Sama sygnatura", signature="BUT60"),
            _offer("333", name="Zupełnie luźna"),
        ]
        await service.sync()
        # Sygnatura dowiązała się przy sync - cofamy, żeby odtworzyć stan
        # "produkt założony po synchronizacji".
        await inventory.remove_offer_links("allegro", "222")

        unlinked = await service.get_catalog(only_unlinked=True)

        assert {o.external_id for o in unlinked} == {"222", "333"}

    async def test_stan_powiazania_zgadza_sie_z_resolverem(self, service, plugin, inventory):
        """
        Kontrakt między katalogiem a mechanizmem odejmującym: dla każdej
        oferty `is_linked` musi znaczyć to samo, co niepusty wynik
        `ComponentResolver.resolve`. To ten rozjazd sprawiał, że magazyn
        "nie odejmował", choć interfejs twierdził inaczej.
        """
        await inventory.create(_item("BUT60"))
        await inventory.create(_item("333", "Po ID oferty"))
        await inventory.create(_item("KRO"))
        await inventory.add_offer_link("allegro", "111", "KRO", 1)
        plugin.offers = [
            _offer("111", name="Z recepturą"),
            _offer("222", name="Sama sygnatura", signature="BUT60"),
            _offer("333", name="Po ID oferty"),
            _offer("444", name="Luźna"),
        ]
        await service.sync()
        await inventory.remove_offer_links("allegro", "222")

        resolver = ComponentResolver(inventory)
        for offer in await service.get_catalog():
            components = await resolver.resolve(
                "allegro",
                Product(
                    external_id=offer.external_id,
                    name=offer.name,
                    quantity=1,
                    unit_price=Decimal("0"),
                ),
            )
            assert offer.is_linked is bool(components), offer.external_id


class TestImportDoMagazynu:
    """Zakładanie produktów magazynowych z ofert katalogu."""

    async def test_zaklada_produkt_i_wiaze_go_z_oferta(self, service, plugin, inventory):
        """Import tworzy SKU z sygnatury i od razu zapisuje recepturę."""
        plugin.offers = [
            _offer(
                "111",
                name="Butelka 60 ml",
                signature="BUT60",
                available_stock=48,
                price=Decimal("12.90"),
            )
        ]
        await service.sync()

        result = await service.import_to_stock(["111"])

        assert result.created == ("BUT60",)
        item = await inventory.get_by_sku("BUT60")
        assert item is not None
        assert item.name == "Butelka 60 ml"
        assert item.stock == 48
        assert item.sale_price == Decimal("12.90")
        links = await inventory.get_offer_links("allegro", "111")
        assert [(c.sku, c.quantity) for c in links] == [("BUT60", 1)]

    async def test_bez_sygnatury_uzywa_identyfikatora_oferty_jako_sku(
        self, service, plugin, inventory
    ):
        """Oferta bez sygnatury dostaje SKU równe swojemu identyfikatorowi."""
        plugin.offers = [_offer("111", name="Nakrętka")]
        await service.sync()

        result = await service.import_to_stock(["111"])

        assert result.created == ("111",)
        assert await inventory.get_by_sku("111") is not None

    async def test_nie_nadpisuje_istniejacego_produktu(self, service, plugin, inventory):
        """
        Kolizja SKU nie może podmienić ręcznie opisanego produktu nazwą
        i stanem z Allegro - import ma tylko dowiązać ofertę.
        """
        await inventory.create(_item("BUT60", "Butelka apteczna oranż", stock=7))
        plugin.offers = [
            _offer(
                "111", name="BUTELKA 60ML PROMOCJA!!!", signature="BUT60", available_stock=48
            )
        ]
        await service.sync()

        result = await service.import_to_stock(["111"])

        assert result.created == ()
        item = await inventory.get_by_sku("BUT60")
        assert item is not None
        assert item.name == "Butelka apteczna oranż"
        assert item.stock == 7

    async def test_pomija_oferte_spoza_katalogu_z_podanym_powodem(self, service):
        """Nieznana oferta nie przerywa importu, ale wraca z powodem."""
        result = await service.import_to_stock(["nie-ma-takiej"])

        assert result.created == ()
        assert result.skipped == (("nie-ma-takiej", "Oferty nie ma w katalogu"),)

    async def test_import_czyni_oferte_powiazana_w_katalogu(self, service, plugin, inventory):
        """Po imporcie oferta przestaje być zgłaszana jako niepowiązana."""
        plugin.offers = [_offer("111", name="Butelka", signature="BUT60")]
        await service.sync()
        assert len(await service.get_catalog(only_unlinked=True)) == 1

        await service.import_to_stock(["111"])

        assert await service.get_catalog(only_unlinked=True) == []

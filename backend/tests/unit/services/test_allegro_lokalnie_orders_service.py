"""
Testy zamiany sprzedaży z Allegro Lokalnie na zamówienie ORDLY.

To jest miejsce, w którym dane odczytane z SZABLONU MAILA wchodzą do
torów odejmujących stany magazynowe i liczących przychód. Dlatego testy
pilnują nie tylko tego, co powstaje, ale przede wszystkim tego, co
POWSTAĆ NIE MOŻE: niekompletne zdarzenie nie ma prawa stać się
zamówieniem, bo zamówienie ze zgadniętą ilością albo kwotą zafałszuje
magazyn i statystyki.

Zdarzenia budowane są z PRAWDZIWYCH maili (`tests/fixtures/allegro_lokalnie/`).
"""

from __future__ import annotations

import pathlib
from decimal import Decimal
from email import message_from_bytes

import pytest

from app.domain.entities.allegro_lokalnie_event import (
    EVENT_NEW_ORDER,
    AllegroLokalnieEvent,
)
from app.domain.fulfillment import FULFILLMENT_NEW
from app.infrastructure.mail.allegro_lokalnie import offer_external_id, parse_event
from app.infrastructure.mail.imap_watcher import _parse_message
from app.infrastructure.mail.mime import extract_bodies
from app.services.allegro_lokalnie_orders_service import (
    MARKETPLACE_ALLEGRO_LOKALNIE,
    AllegroLokalnieOrdersService,
)
from tests.fakes.fake_order_repository import FakeOrderRepository

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_lokalnie"
SPRZEDANO_100 = (
    "Sprzedano 100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
SPRZEDANO_PLYTA = "Sprzedano Płyta gazowa AMICA PG0720 _ PMG2.0ZpZtR.eml"
WIADOMOSC = "Nowa wiadomość do Płyta gazowa AMICA PG0720 _ PMG2.0ZpZtR.eml"
DORECZONO = (
    "Dostarczyliśmy Twoją paczkę z 25szt. Butelka Gorilla 60ml Liquid Aromat "
    "Baza olejki DIY kosmetyki PET.eml"
)


def zdarzenie(nazwa: str) -> AllegroLokalnieEvent:
    raw = (FIXTURES / nazwa).read_bytes()
    message = _parse_message(raw)
    assert message is not None
    return parse_event(message, extract_bodies(message_from_bytes(raw)))


class TestPowstajeZamowienie:
    """Sprzedaż z kompletem danych staje się normalnym zamówieniem."""

    @pytest.mark.asyncio
    async def test_zamowienie_ma_dane_z_maila(self):
        repository = FakeOrderRepository()
        service = AllegroLokalnieOrdersService(repository)

        order = await service.create_from_event(zdarzenie(SPRZEDANO_100))

        assert order is not None
        assert order.marketplace == MARKETPLACE_ALLEGRO_LOKALNIE
        # Numer transakcji z linku „Sprawdź szczegóły" w mailu - jedyny
        # stabilny identyfikator, jaki Allegro Lokalnie w ogóle podaje.
        assert order.external_id == "2b80d30a-5b7a-42a1-ab18-2edd79b8a95a"
        assert order.buyer.login == "Antek2034"
        assert order.buyer.first_name == "Antoni"
        assert order.buyer.last_name == "Ponieważ"
        assert order.total_amount == Decimal("287.92")
        assert order.currency == "PLN"

    @pytest.mark.asyncio
    async def test_pozycja_ma_ilosc_i_cene_jednostkowa(self):
        """
        Magazyn odejmuje ILOŚĆ z pozycji, nie kwotę - pomyłka tutaj
        zdejmowałaby 1 sztukę zamiast 4 przy każdej sprzedaży wielosztukowej.
        """
        repository = FakeOrderRepository()

        order = await AllegroLokalnieOrdersService(repository).create_from_event(
            zdarzenie(SPRZEDANO_100)
        )

        assert order is not None
        assert len(order.products) == 1
        pozycja = order.products[0]
        assert pozycja.quantity == 4
        assert pozycja.unit_price == Decimal("71.98")
        assert pozycja.name == (
            "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )

    @pytest.mark.asyncio
    async def test_zamowienie_czeka_na_spakowanie(self):
        """
        Mail „Sprzedano…" przychodzi po zaksięgowaniu wpłaty, więc paczka
        dopiero czeka na wysyłkę - zamówienie musi wejść na listę „do
        spakowania" i do przypomnienia o 20:00.
        """
        order = await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
            zdarzenie(SPRZEDANO_100)
        )

        assert order is not None
        assert order.fulfillment_status == FULFILLMENT_NEW

    @pytest.mark.asyncio
    async def test_identyfikator_oferty_jest_ten_sam_dla_tego_samego_ogloszenia(self):
        """
        Powiązanie z magazynem ustawia się RAZ na ofertę. Gdyby id zmieniało
        się przy każdej sprzedaży, każde zamówienie wymagałoby nowego
        powiązania i sypało ostrzeżeniem „Sprzedaż poza magazynem".
        """
        order = await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
            zdarzenie(SPRZEDANO_100)
        )

        assert order is not None
        oczekiwany = offer_external_id(
            "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )
        assert order.products[0].external_id == oczekiwany
        assert order.products[0].external_id.startswith("al:")
        # Kolumna `offer_links.external_product_id` ma 100 znaków, a tytuły
        # ogłoszeń bywają dłuższe - identyfikator musi się zmieścić.
        assert len(order.products[0].external_id) <= 100

    @pytest.mark.asyncio
    async def test_zamowienie_trafia_do_repozytorium(self):
        repository = FakeOrderRepository()

        order = await AllegroLokalnieOrdersService(repository).create_from_event(
            zdarzenie(SPRZEDANO_PLYTA)
        )

        assert order is not None
        assert await repository.exists(MARKETPLACE_ALLEGRO_LOKALNIE, order.external_id)


class TestCzegoNieWolno:
    """Granice - to one chronią magazyn i statystyki przed danymi z szablonu."""

    @pytest.mark.asyncio
    async def test_wiadomosc_od_kupujacego_nie_jest_zamowieniem(self):
        order = await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
            zdarzenie(WIADOMOSC)
        )

        assert order is None

    @pytest.mark.asyncio
    async def test_doreczenie_paczki_nie_tworzy_drugiego_zamowienia(self):
        """
        „Dostarczyliśmy Twoją paczkę" dotyczy sprzedaży, o której ORDLY
        już wie - drugi rekord odjąłby stany magazynowe po raz drugi.
        """
        order = await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
            zdarzenie(DORECZONO)
        )

        assert order is None

    @pytest.mark.asyncio
    async def test_ten_sam_mail_nie_tworzy_dwoch_zamowien(self):
        """
        Job skrzynki chodzi co 5 minut, a Pi bywa restartowane. Klucz
        `(marketplace, external_id)` to ostatnia linia obrony przed
        podwójnym odjęciem stanów.
        """
        repository = FakeOrderRepository()
        service = AllegroLokalnieOrdersService(repository)
        event = zdarzenie(SPRZEDANO_100)

        pierwsze = await service.create_from_event(event)
        drugie = await service.create_from_event(event)

        assert pierwsze is not None
        assert drugie is None

    @pytest.mark.asyncio
    async def test_sprzedaz_bez_numeru_transakcji_nie_jest_zamowieniem(self):
        """
        Numer transakcji jest tylko w HTML-u maila. Gdy dociągnięcie
        treści z IMAP zawiedzie, zdarzenie zostaje POWIADOMIENIEM -
        zamówienie z wymyślonym numerem nie dałoby się później powiązać
        ani odróżnić od kolejnej sprzedaży tej samej oferty.
        """
        event = zdarzenie(SPRZEDANO_100)
        bez_numeru = AllegroLokalnieEvent(
            message_id=event.message_id,
            event_type=EVENT_NEW_ORDER,
            subject=event.subject,
            snippet=event.snippet,
            received_at=event.received_at,
            listing_title=event.listing_title,
            buyer_login=event.buyer_login,
            quantity=event.quantity,
            unit_amount=event.unit_amount,
            amount=event.amount,
            transaction_id=None,
        )

        assert bez_numeru.can_become_order is False
        assert (
            await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
                bez_numeru
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_sprzedaz_bez_ilosci_nie_jest_zamowieniem(self):
        """Bez ilości nie da się odjąć właściwej liczby sztuk z magazynu."""
        event = zdarzenie(SPRZEDANO_100)
        bez_ilosci = AllegroLokalnieEvent(
            message_id=event.message_id,
            event_type=EVENT_NEW_ORDER,
            subject=event.subject,
            snippet=event.snippet,
            received_at=event.received_at,
            listing_title=event.listing_title,
            quantity=None,
            unit_amount=event.unit_amount,
            amount=event.amount,
            transaction_id=event.transaction_id,
        )

        assert bez_ilosci.can_become_order is False
        assert (
            await AllegroLokalnieOrdersService(FakeOrderRepository()).create_from_event(
                bez_ilosci
            )
            is None
        )

"""
Pełna integracja Allegro Lokalnie: prawdziwy mail sprzedażowy -> zamówienie.

Bierze PRAWDZIWY mail z fixtures, przepuszcza go przez parser IMAP i serwis
zamówień, i sprawdza liczby, na których stoją statystyki. Ogłoszenie
„100szt. Butelka Gorilla 10ml" to pułapka: cena jednostkowa oferty to
71,98 zł, a kupujący zapłacił za cztery sztuki - pomylenie tych liczb
zaniża przychód czterokrotnie, po cichu.
"""

from __future__ import annotations

import pathlib
from decimal import Decimal
from email import message_from_bytes

import pytest

from app.infrastructure.mail.allegro_lokalnie import parse_event
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


async def zamowienie_z_maila(repository: FakeOrderRepository | None = None):
    """Mail -> zdarzenie -> zamówienie, dokładnie jak w produkcji."""
    raw = (FIXTURES / SPRZEDANO_100).read_bytes()
    message = _parse_message(raw)
    assert message is not None
    event = parse_event(message, extract_bodies(message_from_bytes(raw)))
    service = AllegroLokalnieOrdersService(repository or FakeOrderRepository())
    order = await service.create_from_event(event)
    assert order is not None
    return order


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

        await zamowienie_z_maila(repository)

        nowe = await repository.get_new_status()
        assert [o.marketplace for o in nowe] == [MARKETPLACE_ALLEGRO_LOKALNIE]

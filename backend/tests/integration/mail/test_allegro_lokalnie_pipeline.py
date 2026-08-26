"""
Cała droga zdarzenia z Allegro Lokalnie: skrzynka -> powiadomienie.

Test idzie przez PRAWDZIWY protokół IMAP (gniazdo TCP, SEARCH, FETCH
z literałem - patrz `fake_imap_server`), prawdziwy Event Bus i prawdziwy
`CompositeNotifier`. Udawany jest tylko serwer pocztowy i sam kanał
wysyłki, bo Allegro Lokalnie nie ma API i to powiadomienie e-mail JEST
całą integracją - jeśli ta ścieżka się rozejdzie, sprzedaż z tamtego
serwisu przestaje istnieć dla aplikacji, bez żadnego widocznego błędu.
"""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage

import aioimaplib
import pytest_asyncio
from pydantic import SecretStr

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import AllegroLokalnieEventDetected
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.composite_notifier import CompositeNotifier
from app.infrastructure.mail.imap_watcher import ImapWatcher
from app.services.mailbox_service import MailboxService
from tests.fakes.fake_mail_repository import FakeMailRepository
from tests.fakes.fake_notifier import FakeNotifier
from tests.integration.mail.fake_imap_server import FakeImapServer

#: Realny mail sprzedażowy z Allegro Lokalnie - ten sam plik, na którym
#: opiera się `tests/unit/infrastructure/test_allegro_lokalnie.py`.
#: Test przechodzi przez PRAWDZIWY szablon, a nie przez wyobrażenie o nim.
FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_lokalnie"
SPRZEDANO = (
    "Sprzedano 100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
WIADOMOSC = "Nowa wiadomość do Płyta gazowa AMICA PG0720 _ PMG2.0ZpZtR.eml"


def _fixture(nazwa: str) -> bytes:
    return (FIXTURES / nazwa).read_bytes()


def _allegro_pl_mail() -> bytes:
    message = EmailMessage()
    message["Message-ID"] = "<a-200@allegromail.pl>"
    message["From"] = "Allegro <noreply@allegromail.pl>"
    message["Subject"] = "Masz nowe zamówienie"
    message["Date"] = "Wed, 26 Aug 2026 11:00:00 +0000"
    message.set_content("Szczegóły w panelu sprzedawcy.")
    return message.as_bytes()


@pytest_asyncio.fixture
async def server() -> AsyncIterator[FakeImapServer]:
    fake = FakeImapServer()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


def _settings() -> MailWatchSettings:
    return MailWatchSettings(
        IMAP_HOST="127.0.0.1",
        IMAP_USER="sklep@gmail.com",
        IMAP_PASS=SecretStr("haslo-aplikacji"),
        # Token, a nie domena - "allegro" łapie i allegromail.pl,
        # i allegrolokalnie.pl (patrz test w test_imap_watcher_protocol).
        MAIL_WATCH_SENDERS="allegro,olx",
    )


async def _service(
    server: FakeImapServer, bus: EventBus
) -> tuple[MailboxService, FakeMailRepository]:
    repository = FakeMailRepository()
    # Próbki to PRAWDZIWE maile z prawdziwymi datami (sierpień 2026), a
    # pierwsza synchronizacja pyta serwer tylko o ostatnie 7 dni. Kotwica
    # z odległą datą przesuwa `SINCE` wstecz, żeby test sprawdzał parser
    # i powiadomienia, a nie okno czasowe - to samo robi w produkcji
    # pierwszy zapisany mail.
    await repository.save(
        MailMessage(
            message_id="<kotwica@example.com>",
            sender="noreply@example.com",
            subject="kotwica czasowa",
            received_at=datetime(2026, 1, 1, 0, 0, 0),
            source="other",
            body_preview="",
        )
    )
    service = MailboxService(
        repository,
        _settings(),
        watcher_factory=lambda: ImapWatcher(
            host="127.0.0.1",
            port=server.port,
            user="sklep@gmail.com",
            password="haslo-aplikacji",
            client_factory=lambda: aioimaplib.IMAP4(host="127.0.0.1", port=server.port),
        ),
        event_bus=bus,
    )
    return service, repository


class TestPelnaSciezkaAllegroLokalnie:
    async def test_mail_z_lokalnie_konczy_sie_powiadomieniem(self, server: FakeImapServer):
        server.add_message(_fixture(SPRZEDANO))
        notifier = FakeNotifier()
        bus = EventBus()
        bus.subscribe(
            AllegroLokalnieEventDetected,
            lambda event: notifier.notify_allegro_lokalnie(event.event),
        )
        service, repository = await _service(server, bus)

        saved = await service.sync_now()
        await service.publish_mail_events(saved)

        assert len(notifier.sent_allegro_lokalnie) == 1
        event = notifier.sent_allegro_lokalnie[0]
        assert event.event_type == "new_order"
        assert event.listing_title == (
            "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )
        assert event.quantity == 4
        # Kwota faktycznie zapłacona, nie cena jednostkowa (71,98 zł) -
        # tę różnicę widać dopiero po dociągnięciu PEŁNEJ treści maila,
        # bo sekcja "Łączna kwota zakupu" nie mieści się w podglądzie.
        assert event.amount == Decimal("287.92")
        assert event.buyer == "Antek2034 (Antoni Ponieważ)"

        stored = await repository.get_by_id(event.message_id)
        assert stored is not None
        assert stored.source == "allegro_lokalnie"

    async def test_poczta_z_allegro_pl_nie_dubluje_powiadomien(self, server: FakeImapServer):
        """
        Allegro.pl ma własne API i wysyła powiadomienie o zamówieniu
        z synchronizacji - drugie, ze skrzynki, byłoby duplikatem.
        """
        server.add_message(_allegro_pl_mail())
        notifier = FakeNotifier()
        bus = EventBus()
        bus.subscribe(
            AllegroLokalnieEventDetected,
            lambda event: notifier.notify_allegro_lokalnie(event.event),
        )
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert notifier.sent_allegro_lokalnie == []

    async def test_drugi_przebieg_nie_powtarza_powiadomienia(self, server: FakeImapServer):
        """
        Job chodzi co 5 minut, a Pi bywa restartowane - ten sam mail nie
        może powiadamiać dwa razy. Kluczem dedup jest `Message-ID`.
        """
        server.add_message(_fixture(SPRZEDANO))
        notifier = FakeNotifier()
        bus = EventBus()
        bus.subscribe(
            AllegroLokalnieEventDetected,
            lambda event: notifier.notify_allegro_lokalnie(event.event),
        )
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())
        await service.publish_mail_events(await service.sync_now())

        assert len(notifier.sent_allegro_lokalnie) == 1

    async def test_wiadomosc_od_kupujacego_tez_powiadamia(self, server: FakeImapServer):
        """
        Nie tylko sprzedaż: wiadomość od kupującego na Allegro Lokalnie
        też nie ma innego kanału niż mail.
        """
        server.add_message(_fixture(WIADOMOSC))
        notifier = FakeNotifier()
        bus = EventBus()
        bus.subscribe(
            AllegroLokalnieEventDetected,
            lambda event: notifier.notify_allegro_lokalnie(event.event),
        )
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert len(notifier.sent_allegro_lokalnie) == 1
        zdarzenie = notifier.sent_allegro_lokalnie[0]
        assert zdarzenie.event_type == "new_message"
        assert zdarzenie.listing_title == "Płyta gazowa AMICA PG0720 / PMG2.0ZpZtR"
        assert zdarzenie.is_order is False

    async def test_awaria_jednego_kanalu_nie_gubi_drugiego(self, server: FakeImapServer):
        """
        `CompositeNotifier` ma dostarczyć powiadomienie, dopóki działa
        chociaż jeden kanał - Telegram i push padają niezależnie.
        """
        server.add_message(_fixture(SPRZEDANO))
        dzialajacy = FakeNotifier()
        bus = EventBus()
        composite = CompositeNotifier([_ZawszePadajacyNotifier(), dzialajacy])
        bus.subscribe(
            AllegroLokalnieEventDetected,
            lambda event: composite.notify_allegro_lokalnie(event.event),
        )
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert len(dzialajacy.sent_allegro_lokalnie) == 1


class _ZawszePadajacyNotifier(FakeNotifier):
    """Kanał, który zawsze zawodzi - do sprawdzenia odporności fan-outu."""

    async def notify_allegro_lokalnie(self, event) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("kanał testowy zawsze zawodzi")

"""
Cała droga powiadomienia o dyskusji: skrzynka -> push.

Test idzie przez PRAWDZIWY protokół IMAP (gniazdo TCP, SEARCH, FETCH
z literałem) i PRAWDZIWE maile z Allegro.pl. Pilnuje też granicy podziału
pracy między API a pocztą: z poczty bierzemy WYŁĄCZNIE rozpoczęcie
dyskusji, bo o zamówieniach i zwrotach ORDLY wie już z API i drugie
powiadomienie byłoby duplikatem.
"""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from datetime import datetime

import aioimaplib
import pytest_asyncio
from pydantic import SecretStr

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import AllegroLokalnieEventDetected, DisputeNoticeDetected
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.imap_watcher import ImapWatcher
from app.services.mailbox_service import MailboxService
from tests.fakes.fake_mail_repository import FakeMailRepository
from tests.fakes.fake_notifier import FakeNotifier
from tests.integration.mail.fake_imap_server import FakeImapServer

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_mail"
DYSKUSJA = "dyskusja-rozpoczeta.eml"
ZWROT = "zwrot-odstapienie.eml"


def _fixture(nazwa: str) -> bytes:
    return (FIXTURES / nazwa).read_bytes()


@pytest_asyncio.fixture
async def server() -> AsyncIterator[FakeImapServer]:
    fake = FakeImapServer()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


async def _service(
    server: FakeImapServer, bus: EventBus
) -> tuple[MailboxService, FakeMailRepository]:
    repository = FakeMailRepository()
    # Próbki to prawdziwe maile z lipca 2026, a pierwsza synchronizacja
    # pyta serwer tylko o ostatnie 7 dni - kotwica przesuwa `SINCE` wstecz.
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
        MailWatchSettings(
            IMAP_HOST="127.0.0.1",
            IMAP_USER="sklep@gmail.com",
            IMAP_PASS=SecretStr("haslo-aplikacji"),
            MAIL_WATCH_SENDERS="allegro,olx",
        ),
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


def _bus_z_notifierem() -> tuple[EventBus, FakeNotifier]:
    notifier = FakeNotifier()
    bus = EventBus()
    bus.subscribe(
        DisputeNoticeDetected, lambda event: notifier.notify_new_dispute(event.notice)
    )
    bus.subscribe(
        AllegroLokalnieEventDetected,
        lambda event: notifier.notify_allegro_lokalnie(event.event),
    )
    return bus, notifier


class TestNowaDyskusja:
    async def test_mail_o_dyskusji_konczy_sie_powiadomieniem(self, server: FakeImapServer):
        server.add_message(_fixture(DYSKUSJA))
        bus, notifier = _bus_z_notifierem()
        service, repository = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert len(notifier.sent_disputes) == 1
        notice = notifier.sent_disputes[0]
        assert notice.buyer_login == "Rexpiot"
        assert notice.issue_id == "81ecd951-ab12-4528-8154-af5699df2b1c"
        assert notice.reason == "niezgodny z opisem"
        assert notice.respond_by == datetime(2026, 7, 29, 8, 41)

        stored = await repository.get_by_id(notice.message_id)
        assert stored is not None
        assert stored.source == "allegro"

    async def test_drugi_przebieg_nie_powtarza_powiadomienia(self, server: FakeImapServer):
        """Job skrzynki chodzi co 5 minut - dedup po `Message-ID`."""
        server.add_message(_fixture(DYSKUSJA))
        bus, notifier = _bus_z_notifierem()
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())
        await service.publish_mail_events(await service.sync_now())

        assert len(notifier.sent_disputes) == 1


class TestGranicaMiedzyApiAPoczta:
    async def test_mail_o_zwrocie_nie_powiadamia(self, server: FakeImapServer):
        """
        Zwroty pobiera synchronizacja z API i to ona wysyła powiadomienie.
        Drugi tor z poczty dałby dwa powiadomienia o jednym zwrocie.
        """
        server.add_message(_fixture(ZWROT))
        bus, notifier = _bus_z_notifierem()
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert notifier.sent_disputes == []
        assert notifier.sent_texts == []

    async def test_poczta_z_allegro_pl_nie_trafia_do_toru_allegro_lokalnie(
        self, server: FakeImapServer
    ):
        """
        Regresja granicy kanałów: `powiadomienia@allegro.pl` zawiera
        podciąg "allegro", więc bez sprawdzania "allegrolokalnie"
        NAJPIERW te maile próbowałyby stać się zamówieniami z Lokalnie.
        """
        server.add_message(_fixture(ZWROT))
        server.add_message(_fixture(DYSKUSJA))
        bus, notifier = _bus_z_notifierem()
        service, _ = await _service(server, bus)

        await service.publish_mail_events(await service.sync_now())

        assert notifier.sent_allegro_lokalnie == []

    async def test_oba_maile_sa_widoczne_w_skrzynce(self, server: FakeImapServer):
        """
        Brak powiadomienia nie znaczy „mail zniknął" - obie wiadomości
        mają być do przeczytania w zakładce Poczta.
        """
        server.add_message(_fixture(ZWROT))
        server.add_message(_fixture(DYSKUSJA))
        bus, _ = _bus_z_notifierem()
        service, repository = await _service(server, bus)

        zapisane = await service.sync_now()

        assert len(zapisane) == 2
        assert all(m.source == "allegro" for m in zapisane)
        assert await repository.count() == 3  # dwa maile + kotwica czasowa

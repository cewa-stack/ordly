"""
[FEAT-MAIL] Jednorazowe powiadomienie o mailu InPost dotyczącym paczki od
F.H.P. MAIK-POL.

Fixture'y `tests/fixtures/inpost/*.eml` odtwarzają mail z zrzutu w Notion
(decyzja M6-b: oryginał .eml nie był dostępny): nadawca, temat, zdanie
„Twoja paczka od F.H.P. MAIK-POL wyruszyła w podróż do Ciebie.” i numer
paczki 620999672171521435976372. Adres skrzynki i paczkomatu są fikcyjne.
Przypadek negatywny: ten sam szablon, inny hurtownik.

Ścieżka przez IMAP idzie przez PRAWDZIWY protokół (`FakeImapServer`):
gniazdo, LOGIN, SEARCH, FETCH z literałem - tak jak na Pi.
"""

from __future__ import annotations

import email
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import aioimaplib
import pytest
import pytest_asyncio
from pydantic import SecretStr

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import WholesaleParcelShipped
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapWatcher
from app.infrastructure.mail.inpost import (
    OUTCOME_AMBIGUOUS_NUMBER,
    OUTCOME_MATCH,
    OUTCOME_NO_NUMBER,
    OUTCOME_OTHER_SENDER,
    OUTCOME_OTHER_SUBJECT,
    OUTCOME_OTHER_WHOLESALER,
    parse_parcel_mail,
)
from app.infrastructure.mail.mime import MailBodies, extract_bodies
from app.repositories.sqlite_processed_parcel_mail_repository import (
    ProcessedParcelMail,
    SqliteProcessedParcelMailRepository,
)
from app.scheduler.jobs.sync_mail_job import run_mail_sync_job
from app.services.wholesale_parcel_service import WholesaleParcelService
from app.utils.time import utc_now
from tests.integration.hub.conftest import SessionScope, make_database
from tests.integration.mail.fake_imap_server import FakeImapServer

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "inpost"
MAIK_POL = _FIXTURES / "potwierdzenie-nadania-maik-pol.eml"
OTHER_WHOLESALER = _FIXTURES / "potwierdzenie-nadania-inny-hurtownik.eml"
NUMBER = "620999672171521435976372"


def _raw(path: Path, *, received_at=None) -> bytes:
    """Fixture z datą przesuniętą na "teraz" - alert dotyczy tylko świeżych maili."""
    message = email.message_from_bytes(path.read_bytes())
    when = received_at or utc_now()
    del message["Date"]
    message["Date"] = when.strftime("%a, %d %b %Y %H:%M:%S +0000")
    return message.as_bytes()


def _parts(raw: bytes) -> tuple[MailMessage, MailBodies]:
    parsed = email.message_from_bytes(raw)
    from email.header import decode_header, make_header

    subject = str(make_header(decode_header(parsed["Subject"])))
    message = MailMessage(
        message_id=parsed["Message-ID"],
        sender=str(parsed["From"]),
        subject=" ".join(subject.split()),
        received_at=utc_now(),
        source="other",
        body_preview="",
    )
    return message, extract_bodies(parsed)


# ----------------------------------------------------------------------------
# Rozpoznanie maila (W1-W7)
# ----------------------------------------------------------------------------


class TestRozpoznanie:
    def test_mail_ze_zrzutu_daje_alert(self):
        message, bodies = _parts(MAIK_POL.read_bytes())

        result = parse_parcel_mail(message, bodies)

        assert result.outcome == OUTCOME_MATCH
        assert result.notice is not None
        assert result.notice.tracking_number == NUMBER
        assert result.notice.wholesaler_name == "F.H.P. MAIK-POL"

    def test_inny_hurtownik_bez_alertu(self):
        message, bodies = _parts(OTHER_WHOLESALER.read_bytes())

        result = parse_parcel_mail(message, bodies)

        assert result.outcome == OUTCOME_OTHER_WHOLESALER
        assert result.notice is None

    def test_inny_nadawca_z_ta_sama_trescia_bez_alertu(self):
        message, bodies = _parts(MAIK_POL.read_bytes())
        for sender in (
            "InPost <info@paczkomaty-pl.example.com>",
            "Hurtownia <info@maikpol.example.com>",
            "Ktos <info@paczkomaty.pl>",  # właściwy adres, ale inna nazwa
        ):
            result = parse_parcel_mail(replace(message, sender=sender), bodies)
            assert result.outcome == OUTCOME_OTHER_SENDER, sender

    def test_inny_temat_bez_alertu(self):
        message, bodies = _parts(MAIK_POL.read_bytes())
        result = parse_parcel_mail(
            replace(message, subject="InPost - Paczka czeka w Paczkomacie"), bodies
        )
        assert result.outcome == OUTCOME_OTHER_SUBJECT

    def test_brak_numeru_bez_alertu(self):
        message, bodies = _parts(MAIK_POL.read_bytes())
        stripped = MailBodies(
            html=(bodies.html or "").replace(NUMBER, ""),
            text=(bodies.text or "").replace(NUMBER, ""),
        )
        assert parse_parcel_mail(message, stripped).outcome == OUTCOME_NO_NUMBER

    def test_dwa_rozne_numery_to_niejednoznacznosc(self):
        message, bodies = _parts(MAIK_POL.read_bytes())
        doubled = MailBodies(
            html=bodies.html,
            text=(bodies.text or "") + "\nNumer paczki: 620000000000000000000001",
        )
        assert parse_parcel_mail(message, doubled).outcome == OUTCOME_AMBIGUOUS_NUMBER

    def test_nazwa_hurtowni_zlamana_na_dwie_linie(self):
        """Na zrzucie „MAIK-” i „POL” są w różnych liniach."""
        message, _ = _parts(MAIK_POL.read_bytes())
        bodies = MailBodies(
            html=None,
            text=f"Twoja paczka od F.H.P. MAIK-\nPOL wyruszyła w podróż.\nNumer paczki: {NUMBER}",
        )
        assert parse_parcel_mail(message, bodies).outcome == OUTCOME_MATCH


# ----------------------------------------------------------------------------
# Serwis na prawdziwej bazie i prawdziwym IMAP
# ----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def server() -> AsyncIterator[FakeImapServer]:
    fake = FakeImapServer()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


@pytest_asyncio.fixture
async def scope(tmp_path: Path) -> AsyncIterator[SessionScope]:
    engine, session_scope = await make_database(tmp_path / "parcel.db")
    yield session_scope
    await engine.dispose()


def _settings() -> MailWatchSettings:
    return MailWatchSettings(
        IMAP_HOST="127.0.0.1",
        IMAP_USER="sklep.testowy@example.com",
        IMAP_PASS=SecretStr("haslo-aplikacji"),
    )


def _watcher_factory(server: FakeImapServer):
    def factory() -> ImapWatcher:
        return ImapWatcher(
            host="127.0.0.1",
            port=server.port,
            user="sklep.testowy@example.com",
            password="haslo-aplikacji",
            client_factory=lambda: aioimaplib.IMAP4(host="127.0.0.1", port=server.port),
        )

    return factory


class _Recorder:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[WholesaleParcelShipped] = []
        bus.subscribe(WholesaleParcelShipped, self._capture)  # type: ignore[arg-type]

    async def _capture(self, event: WholesaleParcelShipped) -> None:
        self.events.append(event)


async def _cycle(scope: SessionScope, server: FakeImapServer, bus: EventBus):
    """Jeden cykl jak w jobie: sync w sesji, publikacja po zatwierdzeniu."""
    async with scope() as session:
        service = WholesaleParcelService(
            SqliteProcessedParcelMailRepository(session),
            _settings(),
            watcher_factory=_watcher_factory(server),
            event_bus=bus,
        )
        notices = await service.sync()
    await service.publish(notices)
    return notices


class TestJedenAlertNaMail:
    async def test_mail_ze_zrzutu_daje_dokladnie_jeden_alert(self, scope, server):
        server.add_message(_raw(MAIK_POL))
        bus = EventBus()
        recorder = _Recorder(bus)

        await _cycle(scope, server, bus)
        await _cycle(scope, server, bus)  # W9: ponowna synchronizacja
        await _cycle(scope, server, bus)

        assert len(recorder.events) == 1
        notice = recorder.events[0].notice
        assert notice.tracking_number == NUMBER
        assert notice.message_id == "<20261005124300.maikpol.test@paczkomaty.pl>"

    async def test_zapisuje_wynik_takze_bez_alertu(self, scope, server):
        server.add_message(_raw(MAIK_POL))
        server.add_message(_raw(OTHER_WHOLESALER))
        bus = EventBus()
        recorder = _Recorder(bus)

        await _cycle(scope, server, bus)

        assert [e.notice.tracking_number for e in recorder.events] == [NUMBER]
        async with scope() as session:
            repository = SqliteProcessedParcelMailRepository(session)
            other = await repository.get("<20261005130000.inny.test@paczkomaty.pl>")
            match = await repository.get("<20261005124300.maikpol.test@paczkomaty.pl>")
        assert other is not None and other.outcome == OUTCOME_OTHER_WHOLESALER
        assert other.alerted is False
        assert match is not None and match.alerted is True and match.tracking_number == NUMBER

    async def test_inny_nadawca_nie_jest_nawet_czytany(self, scope, server):
        fake = email.message_from_bytes(_raw(MAIK_POL))
        fake.replace_header("From", "Hurtownia <sklep@maikpol.example.com>")
        fake.replace_header("Message-ID", "<podrobka@maikpol.example.com>")
        server.add_message(fake.as_bytes())
        bus = EventBus()
        recorder = _Recorder(bus)

        await _cycle(scope, server, bus)

        assert recorder.events == []

    async def test_stary_mail_zapisany_bez_alertu(self, scope, server):
        """
        M7-a: alert tylko o mailach z ostatnich 3 dni. Po dłuższej przerwie
        (ostatni rozpatrzony mail sprzed 10 dni) starsze potwierdzenia są
        zapamiętywane po cichu.
        """
        async with scope() as session:
            await SqliteProcessedParcelMailRepository(session).add(
                ProcessedParcelMail(
                    message_id="<dawny@paczkomaty.pl>",
                    received_at=utc_now() - timedelta(days=10),
                    sender="InPost <info@paczkomaty.pl>",
                    subject="InPost - Potwierdzenie nadania przesyłki",
                    outcome=OUTCOME_MATCH,
                    tracking_number="620000000000000000000009",
                    wholesaler="F.H.P. MAIK-POL",
                    alerted=True,
                )
            )
        server.add_message(_raw(MAIK_POL, received_at=utc_now() - timedelta(days=5)))
        bus = EventBus()
        recorder = _Recorder(bus)

        await _cycle(scope, server, bus)

        assert recorder.events == []
        async with scope() as session:
            record = await SqliteProcessedParcelMailRepository(session).get(
                "<20261005124300.maikpol.test@paczkomaty.pl>"
            )
        assert record is not None and record.outcome == OUTCOME_MATCH
        assert record.alerted is False

    async def test_brak_polaczenia_ze_skrzynka_nie_przerywa(self, scope):
        class _Broken:
            async def fetch_new_from_senders(self, senders, since):
                raise ImapConnectionError("serwer nie odpowiada")

            async def fetch_bodies_by_message_id(self, message_id):
                raise ImapConnectionError("serwer nie odpowiada")

        async with scope() as session:
            service = WholesaleParcelService(
                SqliteProcessedParcelMailRepository(session),
                _settings(),
                watcher_factory=_Broken,
            )
            assert await service.sync() == []

    async def test_niedostepna_tresc_ponawia_w_kolejnym_cyklu(self, scope, server):
        server.add_message(_raw(MAIK_POL))
        bus = EventBus()
        recorder = _Recorder(bus)
        real = _watcher_factory(server)

        class _NoBody:
            def __init__(self) -> None:
                self._inner = real()

            async def fetch_new_from_senders(self, senders, since):
                return await self._inner.fetch_new_from_senders(senders, since)

            async def fetch_bodies_by_message_id(self, message_id):
                raise ImapConnectionError("zerwane łącze")

        async with scope() as session:
            failing = WholesaleParcelService(
                SqliteProcessedParcelMailRepository(session),
                _settings(),
                watcher_factory=_NoBody,
                event_bus=bus,
            )
            assert await failing.sync() == []

        await _cycle(scope, server, bus)
        assert len(recorder.events) == 1

    async def test_wylaczona_skrzynka_nic_nie_robi(self, scope):
        async with scope() as session:
            service = WholesaleParcelService(
                SqliteProcessedParcelMailRepository(session), MailWatchSettings(IMAP_USER="")
            )
            assert await service.sync() == []


class TestJob:
    async def test_awaria_alertu_nie_przewraca_joba(self, scope):
        class _Mailbox:
            async def sync_now(self):
                return []

            async def publish_mail_events(self, saved):
                return None

        def broken(_session):
            raise RuntimeError("awaria")

        await run_mail_sync_job(
            session_scope_factory=scope,
            build_mailbox_service=lambda _s: _Mailbox(),  # type: ignore[arg-type,return-value]
            build_parcel_service=broken,
        )


class TestTylkoBackendCzytaPoczte:
    """W14: skrzynkę obsługuje backend na Pi - desktop i telefon nie łączą się z IMAP."""

    @pytest.mark.parametrize("app_dir", ["desktop/src", "mobile/src"])
    def test_aplikacje_nie_maja_kodu_imap(self, app_dir):
        root = Path(__file__).resolve().parents[4] / app_dir
        assert root.is_dir(), root
        offending = []
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".mjs"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "paczkomaty.pl" in text or "imapflow" in text or "node-imap" in text:
                offending.append(str(path))
        assert offending == []

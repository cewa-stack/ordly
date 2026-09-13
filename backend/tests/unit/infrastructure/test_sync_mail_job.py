"""
Alert o niedziałającej poczcie w jobie synchronizacji skrzynki.

Sprzedaż z Allegro Lokalnie i OLX przychodzi wyłącznie mailem. Wcześniej
job połykał błąd logowania IMAP po cichu - zepsute hasło aplikacji
oznaczało zamówienia, o których nikt się nie dowiadywał.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapLoginRejectedError
from app.scheduler.jobs.sync_mail_job import run_mail_sync_job
from app.scheduler.sync_failure_tracker import SyncFailureTracker
from tests.fakes.fake_notifier import FakeNotifier


class _Mailbox:
    """Skrzynka odgrywająca zadaną serię wyników `sync_now`."""

    def __init__(self, *outcomes: object) -> None:
        self._outcomes = list(outcomes)
        self.published: list[list] = []

    async def sync_now(self) -> list:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]

    async def publish_mail_events(self, saved: list) -> None:
        self.published.append(saved)


@asynccontextmanager
async def _scope() -> AsyncIterator[None]:
    yield None


async def _run(mailbox: _Mailbox, tracker: SyncFailureTracker, notifier: FakeNotifier) -> None:
    await run_mail_sync_job(
        session_scope_factory=_scope,  # type: ignore[arg-type]
        build_mailbox_service=lambda _session: mailbox,  # type: ignore[arg-type,return-value]
        failure_tracker=tracker,
        notifier=notifier,
        retry_in_minutes=5,
    )


def _rejected() -> ImapLoginRejectedError:
    return ImapLoginRejectedError("Logowanie IMAP odrzucone: [AUTHENTICATIONFAILED]")


class TestAlertONiedzialajacejPoczcie:
    async def test_pojedyncza_awaria_nie_alarmuje(self):
        """Jeden timeout Gmaila to nie powód, żeby budzić telefon."""
        mailbox, tracker, notifier = (
            _Mailbox(_rejected()),
            SyncFailureTracker(),
            FakeNotifier(),
        )

        await _run(mailbox, tracker, notifier)

        assert notifier.sent_mailbox_alerts == []

    async def test_druga_odmowa_logowania_alarmuje_raz_na_serie(self):
        mailbox = _Mailbox(_rejected(), _rejected(), _rejected(), _rejected())
        tracker, notifier = SyncFailureTracker(), FakeNotifier()

        for _ in range(4):
            await _run(mailbox, tracker, notifier)

        assert notifier.sent_mailbox_alerts == [(True, 5)]

    async def test_zerwane_polaczenie_to_alert_bez_odmowy_logowania(self):
        mailbox = _Mailbox(ImapConnectionError("timeout"), ImapConnectionError("timeout"))
        tracker, notifier = SyncFailureTracker(), FakeNotifier()

        await _run(mailbox, tracker, notifier)
        await _run(mailbox, tracker, notifier)

        assert notifier.sent_mailbox_alerts == [(False, 5)]

    async def test_udana_synchronizacja_zeruje_serie(self):
        """Po naprawie hasła kolejna awaria znów potrzebuje dwóch prób."""
        mailbox = _Mailbox(_rejected(), [], _rejected())
        tracker, notifier = SyncFailureTracker(), FakeNotifier()

        for _ in range(3):
            await _run(mailbox, tracker, notifier)

        assert notifier.sent_mailbox_alerts == []
        assert mailbox.published == [[]]

    async def test_awaria_poczty_nie_miesza_sie_z_seria_zamowien(self):
        """Tracker jest wspólny z Allegro - kanały muszą liczyć się osobno."""
        tracker, notifier = SyncFailureTracker(), FakeNotifier()
        tracker.record_failure("allegro")

        await _run(_Mailbox(_rejected()), tracker, notifier)

        assert notifier.sent_mailbox_alerts == []

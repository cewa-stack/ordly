"""Testy jednostkowe MailboxService."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import SecretStr

from app.core.config import MailWatchSettings
from app.infrastructure.mail.imap_watcher import ImapConnectionError
from app.services.mailbox_service import MailboxService
from app.utils.time import utc_now


def _configured_settings() -> MailWatchSettings:
    return MailWatchSettings(
        IMAP_HOST="imap.gmail.com",
        IMAP_USER="sklep@gmail.com",
        IMAP_PASS=SecretStr("haslo-aplikacji"),
        MAIL_WATCH_SENDERS="allegro.pl,olx.pl",
    )


class FakeWatcher:
    """Fake zastępujący ImapWatcher - śledzi wywołania bez realnego IMAP."""

    def __init__(self, messages_to_return=None, should_raise=None) -> None:
        self.messages_to_return = messages_to_return or []
        self.should_raise = should_raise
        self.calls: list[tuple[list[str], datetime]] = []

    async def fetch_new_from_senders(self, senders, since):
        self.calls.append((senders, since))
        if self.should_raise:
            raise self.should_raise
        return self.messages_to_return


class TestMailboxServiceSync:
    """Testy synchronizacji skrzynki."""

    @pytest.mark.asyncio
    async def test_nic_nie_robi_gdy_imap_nieskonfigurowany(self, fake_mail_repository):
        service = MailboxService(fake_mail_repository, MailWatchSettings())

        count = await service.sync_new_mail()

        assert count == 0

    @pytest.mark.asyncio
    async def test_zapisuje_nowe_maile_i_zwraca_ich_liczbe(
        self, fake_mail_repository, sample_mail_message
    ):
        watcher = FakeWatcher(messages_to_return=[sample_mail_message])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        count = await service.sync_new_mail()

        assert count == 1
        assert await fake_mail_repository.exists(sample_mail_message.message_id)

    @pytest.mark.asyncio
    async def test_nie_zapisuje_ponownie_juz_znanego_maila(
        self, fake_mail_repository, sample_mail_message
    ):
        await fake_mail_repository.save(sample_mail_message)
        watcher = FakeWatcher(messages_to_return=[sample_mail_message])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        count = await service.sync_new_mail()

        assert count == 0

    @pytest.mark.asyncio
    async def test_pierwsza_synchronizacja_szuka_7_dni_wstecz(self, fake_mail_repository):
        watcher = FakeWatcher()
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        await service.sync_new_mail()

        assert len(watcher.calls) == 1
        senders, since = watcher.calls[0]
        assert senders == ["allegro.pl", "olx.pl"]
        assert (utc_now() - timedelta(days=7) - since).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_kolejna_synchronizacja_liczy_od_ostatniego_zapisanego_maila(
        self, fake_mail_repository, sample_mail_message
    ):
        await fake_mail_repository.save(sample_mail_message)
        watcher = FakeWatcher()
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        await service.sync_new_mail()

        _, since = watcher.calls[0]
        assert since == sample_mail_message.received_at

    @pytest.mark.asyncio
    async def test_blad_polaczenia_imap_zwraca_zero_zamiast_wyjatku(
        self, fake_mail_repository
    ):
        watcher = FakeWatcher(should_raise=ImapConnectionError("brak polaczenia"))
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        count = await service.sync_new_mail()

        assert count == 0

    @pytest.mark.asyncio
    async def test_reczna_synchronizacja_przepuszcza_blad_imap_dalej(
        self, fake_mail_repository
    ):
        """
        Odwrotnie niż job cykliczny: przy kliknięciu w aplikacji użytkownik
        musi zobaczyć powód, a nie ciche "0 nowych wiadomości".
        """
        watcher = FakeWatcher(should_raise=ImapConnectionError("logowanie odrzucone"))
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        with pytest.raises(ImapConnectionError):
            await service.sync_now()


class TestMailboxServiceStatus:
    """Testy diagnostyki skrzynki (`GET /api/v1/mail/status`)."""

    @pytest.mark.asyncio
    async def test_nieskonfigurowany_imap_widac_w_statusie(self, fake_mail_repository):
        service = MailboxService(fake_mail_repository, MailWatchSettings(_env_file=None))

        status = await service.get_status()

        assert status.configured is False
        assert status.message_count == 0
        assert status.last_received_at is None

    @pytest.mark.asyncio
    async def test_status_maskuje_adres_i_liczy_maile(
        self, fake_mail_repository, sample_mail_message
    ):
        await fake_mail_repository.save(sample_mail_message)
        service = MailboxService(fake_mail_repository, _configured_settings())

        status = await service.get_status()

        assert status.configured is True
        assert status.user_masked == "sk***@gmail.com"
        assert "sklep@gmail.com" not in status.user_masked
        assert status.watch_senders == ["allegro.pl", "olx.pl"]
        assert status.message_count == 1
        assert status.last_received_at == sample_mail_message.received_at


class TestMailboxServiceRead:
    """Testy odczytu i oznaczania jako przeczytane."""

    @pytest.mark.asyncio
    async def test_list_messages_zwraca_zapisane_maile(
        self, fake_mail_repository, sample_mail_message
    ):
        await fake_mail_repository.save(sample_mail_message)
        service = MailboxService(fake_mail_repository, MailWatchSettings())

        messages = await service.list_messages()

        assert messages == [sample_mail_message]

    @pytest.mark.asyncio
    async def test_mark_read_oznacza_mail(self, fake_mail_repository, sample_mail_message):
        await fake_mail_repository.save(sample_mail_message)
        service = MailboxService(fake_mail_repository, MailWatchSettings())

        await service.mark_read(sample_mail_message.message_id)

        updated = await fake_mail_repository.get_by_id(sample_mail_message.message_id)
        assert updated is not None
        assert updated.is_read is True

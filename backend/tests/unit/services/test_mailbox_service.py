"""Testy jednostkowe MailboxService."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import AllegroLokalnieEventDetected, OlxEventDetected
from app.domain.entities.mail_message import MailMessage
from app.domain.exceptions.domain_exceptions import (
    MailboxNotConfiguredError,
    MailMessageNotFoundError,
)
from app.infrastructure.mail.imap_watcher import ImapConnectionError
from app.infrastructure.mail.mime import MailBodies
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

    def __init__(
        self, messages_to_return=None, should_raise=None, bodies_to_return=None
    ) -> None:
        self.messages_to_return = messages_to_return or []
        self.should_raise = should_raise
        self.bodies_to_return = bodies_to_return
        self.calls: list[tuple[list[str], datetime]] = []
        self.body_calls: list[str] = []

    async def fetch_new_from_senders(self, senders, since):
        self.calls.append((senders, since))
        if self.should_raise:
            raise self.should_raise
        return self.messages_to_return

    async def fetch_bodies_by_message_id(self, message_id):
        self.body_calls.append(message_id)
        if self.should_raise:
            raise self.should_raise
        return self.bodies_to_return


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

    @staticmethod
    def _mail(sender: str, message_id: str) -> MailMessage:
        return MailMessage(
            message_id=message_id,
            sender=sender,
            subject="Wow - 70% rabatu na wszystko!",
            received_at=utc_now(),
            source="olx",
            body_preview="Promocja tylko dzisiaj.",
        )

    @pytest.mark.asyncio
    async def test_mail_marketingowy_z_olx_nie_trafia_do_bazy(self, fake_mail_repository):
        """
        `IMAP SEARCH FROM "olx"` dopasowuje PODCIĄG, więc
        `powiadomienia@marketing.olx.pl` przechodzi tym samym filtrem co
        prawdziwe powiadomienia. Ma odpaść PRZED zapisem, nie przy
        wyświetlaniu - do `mail_messages` nie ma w ogóle wejść.
        """
        marketing = self._mail(
            "OLX <powiadomienia@marketing.olx.pl>", "<promo.20260904@marketing.olx.pl>"
        )
        watcher = FakeWatcher(messages_to_return=[marketing])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        saved = await service.sync_now()

        assert saved == []
        assert not await fake_mail_repository.exists(marketing.message_id)

    @pytest.mark.asyncio
    async def test_newsletter_allegro_nie_trafia_do_bazy(self, fake_mail_repository):
        newsletter = self._mail(
            "Allegro <hello@newsletter.allegro.pl>", "<kupon.20260904@newsletter.allegro.pl>"
        )
        watcher = FakeWatcher(messages_to_return=[newsletter])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        assert await service.sync_now() == []
        assert not await fake_mail_repository.exists(newsletter.message_id)

    @pytest.mark.asyncio
    async def test_prawdziwe_powiadomienie_olx_przechodzi_filtr(self, fake_mail_repository):
        """Filtr wykluczeń nie może odciąć nadawcy, dla którego skrzynka istnieje."""
        prawdziwy = self._mail("OLX <noreply@olx.pl>", "<sprzedaz.20260904@olx.pl>")
        watcher = FakeWatcher(messages_to_return=[prawdziwy])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        saved = await service.sync_now()

        assert [m.message_id for m in saved] == [prawdziwy.message_id]
        assert await fake_mail_repository.exists(prawdziwy.message_id)

    @pytest.mark.asyncio
    async def test_pusta_lista_wykluczen_nie_odsiewa_niczego(self, fake_mail_repository):
        marketing = self._mail(
            "OLX <powiadomienia@marketing.olx.pl>", "<promo.20260904@marketing.olx.pl>"
        )
        settings = MailWatchSettings(
            IMAP_HOST="imap.gmail.com",
            IMAP_USER="sklep@gmail.com",
            IMAP_PASS=SecretStr("haslo-aplikacji"),
            MAIL_WATCH_SENDERS="allegro.pl,olx.pl",
            MAIL_EXCLUDE_SENDERS="",
        )
        watcher = FakeWatcher(messages_to_return=[marketing])
        service = MailboxService(
            fake_mail_repository, settings, watcher_factory=lambda: watcher
        )

        assert len(await service.sync_now()) == 1

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


class TestMailboxServiceBody:
    """Testy dociągania pełnej treści maila na żądanie."""

    @pytest.mark.asyncio
    async def test_zwraca_obie_wersje_tresci(self, fake_mail_repository):
        watcher = FakeWatcher(
            bodies_to_return=MailBodies(html="<p>Dzień dobry</p>", text="Dzień dobry")
        )
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        bodies = await service.get_message_body("<a1@allegromail.pl>")

        assert bodies.html == "<p>Dzień dobry</p>"
        assert bodies.text == "Dzień dobry"
        assert watcher.body_calls == ["<a1@allegromail.pl>"]

    @pytest.mark.asyncio
    async def test_nieskonfigurowany_imap_mowi_o_skrzynce_a_nie_o_wysylce(
        self, fake_mail_repository
    ):
        """
        Osobny wyjątek od SMTP-owego `MailNotConfiguredError` - inaczej
        komunikat wysyłałby użytkownika do złej sekcji `.env` na Pi.
        """
        service = MailboxService(fake_mail_repository, MailWatchSettings(_env_file=None))

        with pytest.raises(MailboxNotConfiguredError) as error:
            await service.get_message_body("<a1@allegromail.pl>")

        assert "IMAP_USER" in str(error.value)

    @pytest.mark.asyncio
    async def test_brak_maila_na_serwerze_to_404_a_nie_pusta_tresc(self, fake_mail_repository):
        watcher = FakeWatcher(bodies_to_return=None)
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        with pytest.raises(MailMessageNotFoundError):
            await service.get_message_body("<skasowany@allegromail.pl>")

    @pytest.mark.asyncio
    async def test_mail_bez_zadnej_czytelnej_tresci_tez_jest_404(self, fake_mail_repository):
        """Sam załącznik bez treści - nie ma czego pokazać, więc nie udajemy, że jest."""
        watcher = FakeWatcher(bodies_to_return=MailBodies(html=None, text=None))
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        with pytest.raises(MailMessageNotFoundError):
            await service.get_message_body("<sam-zalacznik@allegromail.pl>")

    @pytest.mark.asyncio
    async def test_blad_polaczenia_imap_leci_dalej(self, fake_mail_repository):
        """Użytkownik czeka przy otwartej wiadomości - musi zobaczyć powód."""
        watcher = FakeWatcher(should_raise=ImapConnectionError("logowanie odrzucone"))
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        with pytest.raises(ImapConnectionError):
            await service.get_message_body("<a1@allegromail.pl>")


class TestMailboxServiceAllegroLokalnieEvents:
    """Publikacja zdarzeń z Allegro Lokalnie - jedyne źródło wiedzy o tamtej sprzedaży."""

    @staticmethod
    def _mail(message_id: str, source: str, subject: str = "Nowe zamówienie") -> MailMessage:
        return MailMessage(
            message_id=message_id,
            sender="Allegro Lokalnie <powiadomienia@allegrolokalnie.pl>",
            subject=subject,
            received_at=utc_now(),
            source=source,
            body_preview="Kupujący opłacił zamówienie na 129,90 zł.",
        )

    @pytest.mark.asyncio
    async def test_publikuje_zdarzenie_dla_maila_z_allegro_lokalnie(
        self, fake_mail_repository
    ):
        bus = EventBus()
        captured: list[AllegroLokalnieEventDetected] = []
        bus.subscribe(AllegroLokalnieEventDetected, lambda event: _collect(captured, event))

        service = MailboxService(fake_mail_repository, _configured_settings(), event_bus=bus)
        mail = self._mail("<al-1@allegrolokalnie.pl>", "allegro_lokalnie")

        await service.publish_mail_events([mail])

        assert len(captured) == 1
        assert captured[0].event.message_id == "<al-1@allegrolokalnie.pl>"
        assert captured[0].event.event_type == "new_order"

    @pytest.mark.asyncio
    async def test_dociaga_pelna_tresc_do_rozpoznania_zdarzenia(self, fake_mail_repository):
        """
        `body_preview` jest przycięty do 500 znaków, a sekcje „Łączna kwota
        zakupu" i „Osoba kupująca" stoją w szablonie Allegro Lokalnie
        NIŻEJ - bez pełnej treści powiadomienie pokazywałoby cenę
        jednostkową ogłoszenia zamiast kwoty, którą kupujący zapłacił.
        """
        pelna_tresc = (
            "Sprzedany przedmiot\n\nkup teraz\n\n"
            "25szt. Butelka Gorilla 60ml\n\n49,99 zł\n\n1 sztuka\n\n"
            "Łączna kwota zakupu\n\n287,92 zł\n\n"
            "Osoba kupująca\n\nArchiTheOne (Artur Wisniewski)"
        )
        bus = EventBus()
        captured: list[AllegroLokalnieEventDetected] = []
        bus.subscribe(AllegroLokalnieEventDetected, lambda event: _collect(captured, event))
        watcher = FakeWatcher(bodies_to_return=MailBodies(html=None, text=pelna_tresc))
        service = MailboxService(
            fake_mail_repository,
            _configured_settings(),
            watcher_factory=lambda: watcher,
            event_bus=bus,
        )

        await service.publish_mail_events(
            [self._mail("<al-7@allegrolokalnie.pl>", "allegro_lokalnie")]
        )

        event = captured[0].event
        assert event.listing_title == "25szt. Butelka Gorilla 60ml"
        assert event.quantity == 1
        assert event.unit_amount == Decimal("49.99")
        assert event.amount == Decimal("287.92")
        assert event.buyer == "ArchiTheOne (Artur Wisniewski)"

    @pytest.mark.asyncio
    async def test_awaria_dociagania_tresci_nie_gubi_zdarzenia(self, fake_mail_repository):
        """Gdy IMAP nie odpowie, zdarzenie ma powstać z podglądu - uboższe, ale jest."""
        bus = EventBus()
        captured: list[AllegroLokalnieEventDetected] = []
        bus.subscribe(AllegroLokalnieEventDetected, lambda event: _collect(captured, event))
        watcher = FakeWatcher(should_raise=ImapConnectionError("brak polaczenia"))
        service = MailboxService(
            fake_mail_repository,
            _configured_settings(),
            watcher_factory=lambda: watcher,
            event_bus=bus,
        )

        await service.publish_mail_events(
            [self._mail("<al-8@allegrolokalnie.pl>", "allegro_lokalnie")]
        )

        assert len(captured) == 1
        assert captured[0].event.event_type == "new_order"

    @pytest.mark.asyncio
    async def test_zdarzenie_lokalnie_nie_powstaje_z_cudzej_poczty(self, fake_mail_repository):
        """
        Każdy kanał ma własny typ zdarzenia. Mail z Allegro.pl, z OLX
        i od hurtowni nie ma prawa wygenerować zdarzenia z Lokalnie -
        inaczej ten sam mail dałby dwa powiadomienia.
        """
        bus = EventBus()
        captured: list[AllegroLokalnieEventDetected] = []
        bus.subscribe(AllegroLokalnieEventDetected, lambda event: _collect(captured, event))

        service = MailboxService(fake_mail_repository, _configured_settings(), event_bus=bus)

        await service.publish_mail_events(
            [
                self._mail("<a@allegromail.pl>", "allegro"),
                self._mail("<o@olx.pl>", "olx"),
                self._mail("<x@example.com>", "other"),
            ]
        )

        assert captured == []

    @pytest.mark.asyncio
    async def test_bez_magistrali_nie_wybucha(self, fake_mail_repository):
        """Serwis budowany bez event busa (testy, skrypty) ma po prostu nic nie robić."""
        service = MailboxService(fake_mail_repository, _configured_settings())

        await service.publish_mail_events(
            [self._mail("<al-2@allegrolokalnie.pl>", "allegro_lokalnie")]
        )

    @pytest.mark.asyncio
    async def test_sync_zwraca_tylko_nowo_zapisane_maile(
        self, fake_mail_repository, sample_mail_message
    ):
        """
        Deduplikacja powiadomień opiera się na tym zwrocie: mail już
        obecny w bazie nie może wrócić do `publish_mail_events`, bo
        użytkownik dostałby ten sam push po każdym restarcie Pi.
        """
        await fake_mail_repository.save(sample_mail_message)
        nowy = self._mail("<al-3@allegrolokalnie.pl>", "allegro_lokalnie")
        watcher = FakeWatcher(messages_to_return=[sample_mail_message, nowy])
        service = MailboxService(
            fake_mail_repository, _configured_settings(), watcher_factory=lambda: watcher
        )

        saved = await service.sync_now()

        assert [m.message_id for m in saved] == ["<al-3@allegrolokalnie.pl>"]


async def _collect(bucket: list, event) -> None:
    """Subskrybent testowy - Event Bus oczekuje korutyny, nie zwykłej funkcji."""
    bucket.append(event)


class TestMailboxServiceOlxEvents:
    """
    Publikacja zdarzeń z OLX.

    Do niedawna poczta OLX nie generowała żadnych zdarzeń - sprzedaż,
    wiadomość i zwrot z tego kanału przechodziły przez ORDLY bezgłośnie.
    Teraz każdy taki mail publikuje `OlxEventDetected`; dopóki parser nie
    ma wzorców tematu, zdarzenie ma typ `unknown` i zostaje zwykłym
    powiadomieniem, a nie zamówieniem.
    """

    @staticmethod
    def _mail(message_id: str, source: str = "olx", subject: str = "Sprzedałeś przedmiot"):
        return MailMessage(
            message_id=message_id,
            sender="OLX <noreply@olx.pl>",
            subject=subject,
            received_at=utc_now(),
            source=source,
            body_preview="Gratulacje! Kupujący opłacił zamówienie.",
        )

    @pytest.mark.asyncio
    async def test_publikuje_zdarzenie_dla_maila_z_olx(self, fake_mail_repository):
        bus = EventBus()
        captured: list[OlxEventDetected] = []
        bus.subscribe(OlxEventDetected, lambda event: _collect(captured, event))

        service = MailboxService(fake_mail_repository, _configured_settings(), event_bus=bus)

        await service.publish_mail_events([self._mail("<olx-1@olx.pl>")])

        assert len(captured) == 1
        assert captured[0].event.message_id == "<olx-1@olx.pl>"

    @pytest.mark.asyncio
    async def test_rozpoznaje_sprzedaz_po_temacie(self, fake_mail_repository):
        """Wzorce tematu pochodzą z prawdziwych maili - patrz `tests/fixtures/olx/`."""
        bus = EventBus()
        captured: list[OlxEventDetected] = []
        bus.subscribe(OlxEventDetected, lambda event: _collect(captured, event))

        service = MailboxService(fake_mail_repository, _configured_settings(), event_bus=bus)

        await service.publish_mail_events(
            [
                self._mail(
                    "<olx-2@olx.pl>",
                    subject="💵➡️👍 Kupujący już zapłacił, potwierdź sprzedaż do 15:29 16-12-2025",
                )
            ]
        )

        assert captured[0].event.event_type == "new_order"

    @pytest.mark.asyncio
    async def test_zdarzenie_olx_nie_powstaje_z_cudzej_poczty(self, fake_mail_repository):
        bus = EventBus()
        captured: list[OlxEventDetected] = []
        bus.subscribe(OlxEventDetected, lambda event: _collect(captured, event))

        service = MailboxService(fake_mail_repository, _configured_settings(), event_bus=bus)

        await service.publish_mail_events(
            [
                self._mail("<al@allegrolokalnie.pl>", "allegro_lokalnie"),
                self._mail("<a@allegromail.pl>", "allegro"),
                self._mail("<x@example.com>", "other"),
            ]
        )

        assert captured == []

    @pytest.mark.asyncio
    async def test_awaria_dociagania_tresci_nie_gubi_zdarzenia(self, fake_mail_repository):
        """Gdy IMAP nie odpowie, zdarzenie ma powstać z podglądu - uboższe, ale jest."""
        bus = EventBus()
        captured: list[OlxEventDetected] = []
        bus.subscribe(OlxEventDetected, lambda event: _collect(captured, event))
        watcher = FakeWatcher(should_raise=ImapConnectionError("brak polaczenia"))
        service = MailboxService(
            fake_mail_repository,
            _configured_settings(),
            watcher_factory=lambda: watcher,
            event_bus=bus,
        )

        await service.publish_mail_events([self._mail("<olx-3@olx.pl>")])

        assert len(captured) == 1
        assert captured[0].event.snippet == "Gratulacje! Kupujący opłacił zamówienie."

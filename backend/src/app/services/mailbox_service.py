"""Serwis skrzynki - synchronizacja i odczyt maili od marketplace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from loguru import logger

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import (
    AllegroLokalnieEventDetected,
    DisputeNoticeDetected,
)
from app.domain.entities.mail_message import MailMessage
from app.domain.exceptions.domain_exceptions import (
    MailboxNotConfiguredError,
    MailMessageNotFoundError,
)
from app.domain.interfaces.mail_repository import MailRepository
from app.infrastructure.mail.allegro_lokalnie import parse_event
from app.infrastructure.mail.allegro_notifications import parse_dispute_notice
from app.infrastructure.mail.classify import SOURCE_ALLEGRO, SOURCE_ALLEGRO_LOKALNIE
from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapWatcher
from app.infrastructure.mail.mime import MailBodies
from app.utils.time import utc_now

_FIRST_SYNC_LOOKBACK_DAYS = 7


@dataclass(frozen=True, slots=True)
class MailboxStatus:
    """
    Stan skrzynki do pokazania w aplikacji.

    Istnieje po to, żeby pusta lista maili nie była niemym "brak
    wiadomości" - użytkownik musi widzieć różnicę między "IMAP nie jest
    skonfigurowany na Pi", "skonfigurowany, ale nic nie przyszło" i
    "logowanie IMAP nie działa". Nie zawiera hasła ani pełnego adresu -
    `user_masked` pokazuje tylko tyle, żeby dało się rozpoznać konto.
    """

    configured: bool
    host: str
    user_masked: str
    watch_senders: list[str]
    message_count: int
    last_received_at: datetime | None


def _mask_user(user: str) -> str:
    """Zamienia `sklep@gmail.com` na `sk***@gmail.com` - do rozpoznania, nie do skopiowania."""
    if not user:
        return ""
    local, _, domain = user.partition("@")
    visible = local[:2]
    masked = f"{visible}***" if len(local) > 2 else f"{local}***"
    return f"{masked}@{domain}" if domain else masked


class MailWatcherProtocol(Protocol):
    """Kontrakt watchera IMAP - pozwala podmienić realny ImapWatcher fake'iem w testach."""

    async def fetch_new_from_senders(
        self, senders: list[str], since: datetime
    ) -> list[MailMessage]: ...

    async def fetch_bodies_by_message_id(self, message_id: str) -> MailBodies | None: ...


WatcherFactory = Callable[[], MailWatcherProtocol]


def _default_watcher_factory(settings: MailWatchSettings) -> WatcherFactory:
    def factory() -> MailWatcherProtocol:
        return ImapWatcher(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password.get_secret_value(),
        )

    return factory


class MailboxService:
    """
    Synchronizuje metadane maili (IMAP -> SQLite) i udostępnia je do
    wyświetlenia.

    W bazie lądują wyłącznie metadane i krótki, czysto tekstowy
    `body_preview` (patrz dokumentacja modułu appplans_06: "cache'ować
    tylko podgląd"). Pełna treść jest dostępna przez `get_message_body()`,
    ale dociągana ze skrzynki NA ŻĄDANIE, a nie zapisywana: mail z
    obrazkami osadzonymi jako `data:` potrafi ważyć kilka megabajtów, a
    baza na Pi jest codziennie kopiowana przez `VACUUM INTO`, więc każdy
    zapisany megabajt mnożyłby się przez liczbę kopii zapasowych.
    """

    def __init__(
        self,
        mail_repository: MailRepository,
        settings: MailWatchSettings,
        watcher_factory: WatcherFactory | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """
        Args:
            mail_repository: Repozytorium zapisanych maili.
            settings: Konfiguracja IMAP.
            watcher_factory: Fabryka watchera - domyślnie tworzy prawdziwy
                `ImapWatcher`, nadpisywalna w testach fake'iem (bez
                monkeypatchowania), analogicznie do `MailService.send_fn`.
            event_bus: Magistrala do publikacji zdarzeń z Allegro Lokalnie.
                `None` wyłącza publikację - używane w testach, które
                sprawdzają wyłącznie zapis do skrzynki.
        """
        self._mail_repository = mail_repository
        self._settings = settings
        self._watcher_factory = watcher_factory or _default_watcher_factory(settings)
        self._event_bus = event_bus

    async def sync_new_mail(self) -> int:
        """
        Sprawdza skrzynkę i zapisuje nowo wykryte maile.

        Zwraca liczbę nowo zapisanych maili. Nic nie robi (zwraca 0),
        gdy IMAP nie jest skonfigurowany - to nie jest błąd, tylko
        funkcja świadomie wyłączona do czasu konfiguracji w `.env`.

        Wariant dla schedulera: awaria IMAP jest logowana i połykana,
        bo cykliczny job nie ma komu jej pokazać. Wersja dla ręcznego
        wyzwolenia z aplikacji to `sync_now()` - tam błąd LECI dalej,
        bo użytkownik stoi przy przycisku i czeka na odpowiedź.
        """
        return len(await self.sync_new_mail_messages())

    async def sync_new_mail_messages(self) -> list[MailMessage]:
        """
        Jak `sync_new_mail`, ale zwraca nowo zapisane maile zamiast ich
        liczby - job schedulera przekazuje je dalej do
        `publish_mail_events()` po zamknięciu sesji.
        """
        try:
            return await self.sync_now()
        except ImapConnectionError:
            logger.exception("Synchronizacja skrzynki IMAP nie powiodła się")
            return []

    async def sync_now(self) -> list[MailMessage]:
        """
        Jak `sync_new_mail`, ale przepuszcza `ImapConnectionError` dalej.

        Używane przez `POST /api/v1/mail/sync` - gdy logowanie IMAP nie
        działa, użytkownik musi zobaczyć powód, a nie ciche "0 nowych".

        Zwraca maile NOWO zapisane w tym cyklu (bez tych, które już były
        w bazie) - wywołujący przekazuje je do `publish_mail_events()` PO
        zatwierdzeniu transakcji, tak samo jak przy synchronizacji
        zamówień (`SyncOrdersService.publish_sync_events`). Subskrybenci
        piszą we własnych sesjach i muszą widzieć zatwierdzone dane.

        Raises:
            ImapConnectionError: Gdy połączenie/logowanie IMAP zawiedzie.
        """
        if not self._settings.enabled:
            return []

        latest = await self._mail_repository.get_latest_received_at()
        since = (
            latest
            if latest is not None
            else utc_now() - timedelta(days=_FIRST_SYNC_LOOKBACK_DAYS)
        )

        watcher = self._watcher_factory()
        messages = await watcher.fetch_new_from_senders(self._settings.watch_senders, since)

        saved: list[MailMessage] = []
        for message in messages:
            if await self._mail_repository.exists(message.message_id):
                continue
            await self._mail_repository.save(message)
            saved.append(message)
        return saved

    async def publish_mail_events(self, messages: list[MailMessage]) -> None:
        """
        Publikuje zdarzenia domenowe dla nowo wykrytych maili.

        Dwa źródła, dwa różne powody:

        - **Allegro Lokalnie** - serwis nie ma API, więc mail jest
          JEDYNYM sygnałem, że cokolwiek się wydarzyło.
        - **Allegro.pl** - API jest, ale odpytujemy `/sale/issues` dopiero
          przy otwarciu ekranu Dyskusji. Z poczty bierzemy więc dokładnie
          jedno zdarzenie: rozpoczęcie dyskusji (patrz
          `allegro_notifications`). Zamówienia i zwroty przychodzą
          z synchronizacji API i drugi tor dałby duplikaty powiadomień.

        Poczta OLX i pozostała nie generuje dziś żadnych zdarzeń.

        Deduplikacja jest naturalna: `sync_now()` zwraca tylko maile
        faktycznie zapisane w tym cyklu, a `Message-ID` jest kluczem
        głównym tabeli - ten sam mail nie przejdzie tędy dwa razy nawet
        po restarcie Pi czy ponownym skanie tego samego zakresu dat.
        """
        if self._event_bus is None:
            return
        for message in messages:
            if message.source == SOURCE_ALLEGRO_LOKALNIE:
                await self._event_bus.publish(
                    AllegroLokalnieEventDetected(
                        occurred_at=utc_now(),
                        event=parse_event(message, await self._bodies(message)),
                    )
                )
            elif message.source == SOURCE_ALLEGRO:
                notice = parse_dispute_notice(message, await self._bodies(message))
                if notice is not None:
                    await self._event_bus.publish(
                        DisputeNoticeDetected(occurred_at=utc_now(), notice=notice)
                    )

    async def _bodies(self, message: MailMessage) -> MailBodies | None:
        """
        Dociąga pełną treść maila do rozpoznania zdarzenia.

        Potrzebna z dwóch powodów. `body_preview` w bazie jest przycięty
        do 500 znaków, a w szablonie Allegro Lokalnie sekcje "Łączna kwota
        zakupu" i "Osoba kupująca" stoją NIŻEJ - bez pełnej treści
        powiadomienie pokazywałoby cenę jednostkową ogłoszenia zamiast
        kwoty, którą kupujący zapłacił. Drugi powód jest ostrzejszy:
        numer transakcji siedzi wyłącznie w HTML-u (w adresie linku),
        a bez niego sprzedaż nie może stać się zamówieniem.

        Kosztuje to jedno dodatkowe połączenie IMAP na każdy nowy mail
        z Lokalnie (kilka dziennie), a niepowodzenie NIE przerywa
        publikacji: zdarzenie powstaje wtedy z samego podglądu - jako
        powiadomienie, nie jako zamówienie.
        """
        try:
            return await self._watcher_factory().fetch_bodies_by_message_id(message.message_id)
        except (ImapConnectionError, ValueError):
            logger.warning(
                "Nie udało się dociągnąć treści maila {} - zdarzenie powstanie z podglądu",
                message.message_id,
            )
            return None

    async def get_status(self) -> MailboxStatus:
        """Zwraca stan skrzynki (konfiguracja + liczniki) do diagnostyki w aplikacji."""
        return MailboxStatus(
            configured=self._settings.enabled,
            host=self._settings.host,
            user_masked=_mask_user(self._settings.user),
            watch_senders=self._settings.watch_senders,
            message_count=await self._mail_repository.count(),
            last_received_at=await self._mail_repository.get_latest_received_at(),
        )

    async def list_messages(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MailMessage]:
        """Zwraca ostatnie maile (opcjonalnie filtrowane po źródle/nieprzeczytane)."""
        return await self._mail_repository.get_recent(
            source=source, unread_only=unread_only, limit=limit, offset=offset
        )

    async def mark_read(self, message_id: str) -> None:
        """Oznacza mail jako przeczytany."""
        await self._mail_repository.mark_read(message_id)

    async def get_message_body(self, message_id: str) -> MailBodies:
        """
        Dociąga pełną treść jednego maila prosto ze skrzynki IMAP.

        Treść jest pobierana NA ŻĄDANIE, a nie cache'owana przy
        synchronizacji - patrz docstring klasy. Cena to jedno połączenie
        IMAP przy otwarciu wiadomości (aplikacja pokazuje na ten czas
        wskaźnik ładowania).

        Raises:
            MailboxNotConfiguredError: Gdy IMAP nie jest ustawiony w `.env`.
            MailMessageNotFoundError: Gdy maila nie ma już na serwerze.
            ImapConnectionError: Gdy połączenie/logowanie IMAP zawiedzie.
        """
        if not self._settings.enabled:
            raise MailboxNotConfiguredError()

        watcher = self._watcher_factory()
        bodies = await watcher.fetch_bodies_by_message_id(message_id)
        if bodies is None or (bodies.html is None and bodies.text is None):
            raise MailMessageNotFoundError(message_id)
        return bodies

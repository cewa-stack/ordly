"""
ORDLy Control Hub - ekran "Zamów w hurtowni".

Hurtownie, ich pozycje i szablony maili edytuje się na desktopie; desktop
wysyła ich kopię na Pi (`save_catalog`). Hub wybiera hurtownię, szablon
i pozycje, ogląda podgląd i przytrzymuje OK - ORDLY składa mail tymi samymi
regułami co desktop i wysyła go przez SMTP z `.env` na Pi.

    Hub -> ORDLY:  ordly/hub/wholesale/get      {wholesaler_id?}
                   ordly/hub/wholesale/preview  {request_id, version, wholesaler_id,
                                                 template_id, items: [indeksy]}
                   ordly/hub/wholesale/send     jak preview + confirm_duplicate
    ORDLY -> Hub:  ordly/wholesale/catalog      lista hurtowni i szablonów
                   ordly/wholesale/items        pozycje jednej hurtowni
                   ordly/wholesale/preview      podgląd maila
                   ordly/wholesale/result       wynik wysyłki

Mail do hurtowni jest nieodwracalny, więc:
- adres bierze się wyłącznie z kopii hurtowni, nigdy z wiadomości Huba,
- `request_id` od Huba jest unikalny - powtórzona prośba nie wyśle drugiego maila,
- to samo zamówienie do tej samej hurtowni w ciągu 15 minut wymaga
  osobnego potwierdzenia (`confirm_duplicate`),
- `version` katalogu: prośba złożona do starej listy (desktop zmienił
  hurtownię w międzyczasie) jest odrzucana, zamiast wysłać inne pozycje,
- tryb testowy (domyślnie włączony): mail idzie na adres nadawcy SMTP
  z dopiskiem, do kogo poszedłby naprawdę.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions.domain_exceptions import MailNotConfiguredError, MailSendError
from app.domain.wholesale_email import (
    WholesaleCatalog,
    WholesaleEmail,
    WholesaleItem,
    Wholesaler,
    WholesaleTemplate,
    catalog_version,
    render_wholesale_email,
)
from app.repositories.sqlite_event_repository import SqliteEventRepository
from app.repositories.sqlite_hub_wholesale_repository import (
    STATUS_SENDING,
    STATUS_SENT,
    HubWholesaleOrder,
    SqliteHubWholesaleRepository,
)
from app.services.hub_events_service import HubPublisher
from app.utils.time import local_today, to_local, utc_now

TOPIC_WHOLESALE_GET = "ordly/hub/wholesale/get"
TOPIC_WHOLESALE_PREVIEW_REQUEST = "ordly/hub/wholesale/preview"
TOPIC_WHOLESALE_SEND = "ordly/hub/wholesale/send"
TOPIC_WHOLESALE_CATALOG = "ordly/wholesale/catalog"
TOPIC_WHOLESALE_ITEMS = "ordly/wholesale/items"
TOPIC_WHOLESALE_PREVIEW = "ordly/wholesale/preview"
TOPIC_WHOLESALE_RESULT = "ordly/wholesale/result"

#: Tyle mieści pamięć i ekran Huba; reszta zostaje na desktopie (Hub pokazuje "+N").
MAX_HUB_WHOLESALERS = 16
MAX_HUB_TEMPLATES = 8
MAX_HUB_ITEMS = 24
HUB_NAME_MAX_CHARS = 40
#: Ten sam mail do tej samej hurtowni w tym czasie = pytanie "na pewno jeszcze raz?".
DUPLICATE_WINDOW = timedelta(minutes=15)

RESULT_SENT = "sent"
RESULT_ALREADY_SENT = "already_sent"
RESULT_DUPLICATE = "duplicate"
RESULT_ERROR = "error"


class WholesaleMailer(Protocol):
    """Wysyłka maila (implementacja: `MailService`)."""

    async def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _Draft:
    wholesaler: Wholesaler
    template: WholesaleTemplate
    email: WholesaleEmail


class _RequestError(Exception):
    """Prośba Huba, której nie da się spełnić - treść idzie na ekran Huba."""


class HubWholesaleService:
    """Katalog hurtowni od desktopu i zamówienia do hurtowni z Huba."""

    def __init__(
        self,
        session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        mailer_factory: Callable[[], WholesaleMailer],
        publisher: HubPublisher | None,
        test_mode: bool,
        test_recipient: str,
        today: Callable[[], date] = local_today,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        """
        Args:
            session_scope_factory: Fabryka krótkich sesji bazy.
            mailer_factory: Wysyłka maili (SMTP z `.env` na Pi).
            publisher: Odpowiedzi do Huba; None, gdy most MQTT jest wyłączony
                (desktop i tak może wysyłać kopię katalogu).
            test_mode: Maile z Huba idą na `test_recipient` zamiast do hurtowni.
            test_recipient: Adres testowy - nadawca SMTP.
            today: Dzisiejsza data w Polsce (znacznik {data}).
            now: Bieżący czas UTC (okno powtórki).
        """
        self._session_scope = session_scope_factory
        self._mailer_factory = mailer_factory
        self._publisher = publisher
        self._test_mode = test_mode
        self._test_recipient = test_recipient
        self._today = today
        self._now = now

    # ------------------------------------------------------------------
    # Desktop -> Pi
    # ------------------------------------------------------------------

    async def save_catalog(self, payload: dict[str, Any]) -> str:
        """Zapisuje kopię hurtowni i szablonów z desktopu. Zwraca wersję katalogu."""
        version = catalog_version(payload)
        async with self._session_scope() as session:
            await SqliteHubWholesaleRepository(session).save_catalog(payload, version)
        logger.info(
            "Hurtownie z desktopu: {} hurtowni, {} szablonów (wersja {})",
            len(payload.get("wholesalers") or []),
            len(payload.get("templates") or []),
            version,
        )
        return version

    async def list_sent_orders(self, limit: int) -> list[HubWholesaleOrder]:
        """Wysłane z Huba - do historii na ekranie Hurtownia w desktopie."""
        async with self._session_scope() as session:
            return await SqliteHubWholesaleRepository(session).list_sent(limit)

    # ------------------------------------------------------------------
    # Hub -> ORDLY
    # ------------------------------------------------------------------

    async def handle_get(self, payload: dict[str, Any]) -> None:
        """Lista hurtowni i szablonów albo pozycje jednej hurtowni."""
        catalog, updated_at = await self._catalog()
        wholesaler_id = payload.get("wholesaler_id")
        if isinstance(wholesaler_id, str) and wholesaler_id:
            await self._publish(
                TOPIC_WHOLESALE_ITEMS, self._items_message(catalog, wholesaler_id)
            )
            return
        await self._publish(
            TOPIC_WHOLESALE_CATALOG, self._catalog_message(catalog, updated_at)
        )

    async def handle_preview(self, payload: dict[str, Any]) -> None:
        """Podgląd maila przed wysyłką - z ostrzeżeniem o powtórce."""
        await self._publish(TOPIC_WHOLESALE_PREVIEW, await self.build_preview(payload))

    async def handle_send(self, payload: dict[str, Any]) -> None:
        """Wysyłka po przytrzymaniu OK na Hubie."""
        await self._publish(TOPIC_WHOLESALE_RESULT, await self.send(payload))

    async def build_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = _request_id(payload)
        try:
            catalog, _ = await self._catalog()
            draft = self._draft(catalog, payload)
        except _RequestError as exc:
            return {"request_id": request_id, "ok": False, "error": str(exc)}
        duplicate = await self._recent_duplicate(draft)
        return {
            "request_id": request_id,
            "ok": True,
            "wholesaler": _short(draft.wholesaler.name),
            "to": draft.wholesaler.email,
            "send_to": self._test_recipient if self._test_mode else draft.wholesaler.email,
            "test_mode": self._test_mode,
            "template": _short(draft.template.name),
            "subject": _short(draft.email.subject, 80),
            "inquiry": draft.email.inquiry,
            "items": [
                {"name": _short(item.name), "qty": item.quantity}
                for item in draft.email.items[:MAX_HUB_ITEMS]
            ],
            "duplicate_minutes": duplicate,
        }

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = _request_id(payload)
        if not request_id:
            return _result("", RESULT_ERROR, "Brak numeru prośby - zaktualizuj firmware Huba")

        async with self._session_scope() as session:
            existing = await SqliteHubWholesaleRepository(session).get_order(request_id)
        if existing is not None and existing.status == STATUS_SENT:
            # Ta sama prośba drugi raz (np. po zerwanym połączeniu) - mail już poszedł.
            return _result(request_id, RESULT_ALREADY_SENT, "Ten mail już wysłano", existing)
        if existing is not None and existing.status == STATUS_SENDING:
            return _result(
                request_id,
                RESULT_ERROR,
                "Poprzednia próba przerwana - sprawdź wysłane w poczcie, zanim wyślesz znowu",
            )

        try:
            catalog, _ = await self._catalog()
            draft = self._draft(catalog, payload)
        except _RequestError as exc:
            return _result(request_id, RESULT_ERROR, str(exc))

        duplicate = await self._recent_duplicate(draft)
        if duplicate is not None and payload.get("confirm_duplicate") is not True:
            return {
                **_result(
                    request_id,
                    RESULT_DUPLICATE,
                    f"To samo zamówienie wysłano {duplicate} min temu",
                ),
                "duplicate_minutes": duplicate,
            }

        to, subject, body = self._outgoing(draft)
        async with self._session_scope() as session:
            await SqliteHubWholesaleRepository(session).start_order(
                request_id=request_id,
                wholesaler_id=draft.wholesaler.id,
                wholesaler_name=draft.wholesaler.name,
                to_email=to,
                subject=subject,
                body=body,
                items_summary=draft.email.items_summary,
                items_key=draft.email.items_key,
                test_mode=self._test_mode,
            )

        error: str | None = None
        try:
            await self._mailer_factory().send(to, subject, body)
        except MailNotConfiguredError:
            error = "Wysyłka maili nie jest ustawiona na Pi (SMTP w .env)"
        except MailSendError as exc:
            error = f"Serwer poczty odrzucił mail: {exc}"[:200]

        async with self._session_scope() as session:
            await SqliteHubWholesaleRepository(session).finish_order(
                request_id, error, self._now()
            )
            if error is None:
                await SqliteEventRepository(session).record(
                    event_type="HubWholesaleOrderSent",
                    level="INFO",
                    payload={
                        "request_id": request_id,
                        "wholesaler": draft.wholesaler.name,
                        "to": to,
                        "items": draft.email.items_summary,
                        "test_mode": self._test_mode,
                    },
                )

        if error is not None:
            logger.warning(
                "Hub: mail do hurtowni {} nie wyszedł: {}", draft.wholesaler.name, error
            )
            return _result(request_id, RESULT_ERROR, error)
        logger.info(
            "Hub: mail do hurtowni {} wysłany na {}{}",
            draft.wholesaler.name,
            to,
            " (TEST)" if self._test_mode else "",
        )
        message = (
            f"Wysłano TEST na {to}"
            if self._test_mode
            else f"Wysłano do {draft.wholesaler.name}"
        )
        return _result(request_id, RESULT_SENT, message)

    # ------------------------------------------------------------------

    async def _catalog(self) -> tuple[WholesaleCatalog, datetime | None]:
        async with self._session_scope() as session:
            return await SqliteHubWholesaleRepository(session).get_catalog()

    def _catalog_message(
        self, catalog: WholesaleCatalog, updated_at: datetime | None
    ) -> dict[str, Any]:
        def template_of(wholesaler: Wholesaler) -> str | None:
            template = catalog.resolve_template(wholesaler.template_id)
            return template.id if template else None

        return {
            "version": catalog.version,
            "updated_at": to_local(updated_at).isoformat(timespec="seconds")
            if updated_at
            else None,
            "test_mode": self._test_mode,
            "wholesalers": [
                {
                    "id": w.id,
                    "name": _short(w.name),
                    "template_id": template_of(w),
                    "items": len(w.items),
                }
                for w in catalog.wholesalers[:MAX_HUB_WHOLESALERS]
            ],
            "more_wholesalers": max(0, len(catalog.wholesalers) - MAX_HUB_WHOLESALERS),
            "templates": [
                {"id": t.id, "name": _short(t.name), "default": t.is_default}
                for t in catalog.templates[:MAX_HUB_TEMPLATES]
            ],
        }

    def _items_message(self, catalog: WholesaleCatalog, wholesaler_id: str) -> dict[str, Any]:
        wholesaler = catalog.wholesaler(wholesaler_id)
        if wholesaler is None:
            return {
                "version": catalog.version,
                "wholesaler_id": wholesaler_id,
                "ok": False,
                "error": "Tej hurtowni już nie ma - wybierz jeszcze raz",
                "items": [],
            }
        return {
            "version": catalog.version,
            "wholesaler_id": wholesaler_id,
            "ok": True,
            "items": [
                {"name": _short(item.name), "qty": item.quantity}
                for item in wholesaler.items[:MAX_HUB_ITEMS]
            ],
            "more_items": max(0, len(wholesaler.items) - MAX_HUB_ITEMS),
        }

    def _draft(self, catalog: WholesaleCatalog, payload: dict[str, Any]) -> _Draft:
        if not catalog.wholesalers:
            raise _RequestError("Brak hurtowni na Pi - otwórz ORDLY na komputerze")
        if payload.get("version") != catalog.version:
            raise _RequestError("Lista hurtowni zmieniła się - wybierz jeszcze raz")
        wholesaler = catalog.wholesaler(str(payload.get("wholesaler_id") or ""))
        if wholesaler is None:
            raise _RequestError("Tej hurtowni już nie ma - wybierz jeszcze raz")
        template_id = payload.get("template_id")
        template = catalog.resolve_template(
            template_id if isinstance(template_id, str) else None
        )
        if template is None:
            raise _RequestError("Brak szablonu maila - dodaj go na komputerze")
        if isinstance(template_id, str) and template_id and template.id != template_id:
            raise _RequestError("Tego szablonu już nie ma - wybierz jeszcze raz")
        items = _selected_items(wholesaler, payload.get("items"))
        email = render_wholesale_email(template, wholesaler, items, self._today())
        return _Draft(wholesaler=wholesaler, template=template, email=email)

    async def _recent_duplicate(self, draft: _Draft) -> int | None:
        """Ile minut temu poszło to samo zamówienie do tej hurtowni (None = nie poszło)."""
        now = self._now()
        async with self._session_scope() as session:
            last = await SqliteHubWholesaleRepository(session).last_sent_same(
                draft.wholesaler.id,
                draft.email.items_key,
                self._test_mode,
                now - DUPLICATE_WINDOW,
            )
        if last is None or last.sent_at is None:
            return None
        return max(0, int((now - last.sent_at).total_seconds() // 60))

    def _outgoing(self, draft: _Draft) -> tuple[str, str, str]:
        """Adresat, temat i treść - w trybie testowym do nadawcy, z dopiskiem."""
        if not self._test_mode:
            return draft.wholesaler.email, draft.email.subject, draft.email.body
        note = (
            "TEST z ORDLy Control Hub. Ten mail poszedłby do: "
            f"{draft.wholesaler.name} <{draft.wholesaler.email}>.\n"
            "Tryb testowy wyłączysz wpisem HUB_WHOLESALE_TEST_MODE=false w .env na Pi.\n"
            "----------------------------------------\n\n"
        )
        return (
            self._test_recipient,
            f"[TEST Hub -> {draft.wholesaler.name}] {draft.email.subject}",
            note + draft.email.body,
        )

    async def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self._publisher is not None:
            await self._publisher.publish(topic, payload)


def _request_id(payload: dict[str, Any]) -> str:
    value = payload.get("request_id")
    return value[:64] if isinstance(value, str) else ""


def _selected_items(wholesaler: Wholesaler, raw: Any) -> tuple[WholesaleItem, ...]:
    """Indeksy pozycji od Huba -> pozycje hurtowni (w kolejności listy, bez powtórek)."""
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(i, int) for i in raw):
        raise _RequestError("Zła lista pozycji - wybierz jeszcze raz")
    indexes = sorted(set(raw))
    limit = min(len(wholesaler.items), MAX_HUB_ITEMS)
    if any(i < 0 or i >= limit for i in indexes):
        raise _RequestError("Lista pozycji zmieniła się - wybierz jeszcze raz")
    return tuple(wholesaler.items[i] for i in indexes)


def _short(text: str, limit: int = HUB_NAME_MAX_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _result(
    request_id: str, status: str, message: str, order: HubWholesaleOrder | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {"request_id": request_id, "status": status, "message": message}
    if order is not None and order.sent_at is not None:
        result["sent_at"] = to_local(order.sent_at).isoformat(timespec="seconds")
    return result

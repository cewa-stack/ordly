"""Encje domenowe i stałe dla wiadomości SMS do klienta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Typ wiadomości - jedno zamówienie może otrzymać maksymalnie jeden SMS
# danego typu (np. jeden PACKING_STARTED).
MESSAGE_TYPE_PACKING_STARTED = "PACKING_STARTED"

# Wynik próby wysyłki zapisywany w historii.
SMS_STATUS_SENT = "SENT"
SMS_STATUS_FAILED = "FAILED"
SMS_STATUS_SKIPPED_NO_PHONE = "SKIPPED_NO_PHONE"


@dataclass(frozen=True, slots=True)
class SmsResult:
    """
    Wynik pojedynczej próby wysłania SMS przez bramkę.

    `success=False` wraz z wypełnionym `error` oznacza, że bramka
    odpowiedziała, ale odrzuciła wiadomość. Wyjątek sieciowy bramki
    jest obsługiwany osobno w SmsService (nie tworzy SmsResult).
    """

    success: bool
    provider_message_id: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SmsRecord:
    """Wpis historii wysłanych (lub pominiętych) wiadomości SMS."""

    order_external_id: str
    message_type: str
    phone: str | None
    status: str
    detail: str | None
    occurred_at: datetime

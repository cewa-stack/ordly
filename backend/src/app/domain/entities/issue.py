"""Encje domenowe dla dyskusji i reklamacji pozakupowych (Allegro: post-purchase issues)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class IssueMessage:
    """Pojedyncza wiadomość w wątku dyskusji lub reklamacji."""

    id: str
    text: str
    author_login: str
    author_role: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Issue:
    """
    Dyskusja lub reklamacja pozakupowa, niezależna od marketplace.

    Allegro od czerwca 2025 łączy dawne "dyskusje" i "reklamacje" w
    jeden zasób ("post purchase issues") - `type` odróżnia je
    (`"DISPUTE"` | `"CLAIM"`). Pobierane zawsze na żywo z marketplace,
    bez cache'owania - analogicznie do Shipment/TrackingService: dyskusje
    są rzadkie, więc świeżość danych jest ważniejsza niż oszczędność
    zapytań.
    """

    external_id: str
    marketplace: str
    type: str
    status: str
    order_external_id: str
    buyer_login: str
    subject: str | None
    description: str | None
    opened_at: datetime
    messages_count: int
    chat_active: bool
    last_message_at: datetime | None

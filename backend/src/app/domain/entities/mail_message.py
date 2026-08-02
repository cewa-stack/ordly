"""Encja domenowa reprezentująca mail od marketplace (Allegro/OLX) wykryty w skrzynce."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MailMessage:
    """
    Pojedynczy mail wykryty przez IMAP watcher.

    `message_id` to nagłówek `Message-ID` (globalnie unikalny, nadawany
    przez serwer pocztowy nadawcy) - naturalny klucz biznesowy, więc ten
    sam mail nigdy nie zostanie zapisany dwa razy nawet przy ponownym
    przeszukaniu tego samego zakresu dat.
    """

    message_id: str
    sender: str
    subject: str
    received_at: datetime
    source: str
    body_preview: str
    is_read: bool = False

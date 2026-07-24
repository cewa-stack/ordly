"""Encja domenowa reprezentująca subskrypcję Web Push jednego urządzenia/przeglądarki."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PushSubscription:
    """
    Subskrypcja Web Push (RFC 8030) zwrócona przez `PushManager.subscribe()`
    w przeglądarce (TOOM Mobile uruchomiony jako PWA na iOS/Android/desktop).

    `endpoint` jest unikalnym kluczem biznesowym - jedna przeglądarka/
    urządzenie ma jeden aktywny endpoint na raz; ponowna subskrypcja z tym
    samym endpointem aktualizuje klucze (`p256dh`/`auth`) zamiast tworzyć
    duplikat.
    """

    endpoint: str
    p256dh: str
    auth: str
    created_at: datetime

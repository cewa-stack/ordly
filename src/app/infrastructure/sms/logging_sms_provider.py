"""
Bramka SMS w trybie testowym - loguje wiadomość zamiast realnej wysyłki.

Pozwala w pełni uruchomić i przetestować ścieżkę SMS (wyzwalacz, blokada
przed dublowaniem, historia) bez konta u operatora. Realną bramkę
(np. SMSAPI) dodaje się jako nową implementację SmsProvider i wskazuje
w konfiguracji (SMS_PROVIDER), bez zmiany logiki biznesowej.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.sms_message import SmsResult
from app.domain.interfaces.sms_provider import SmsProvider


class LoggingSmsProvider(SmsProvider):
    """Symuluje wysyłkę SMS, zapisując treść do logów aplikacji."""

    def __init__(self, sender_name: str = "TOOM") -> None:
        """
        Args:
            sender_name: Nazwa nadawcy, która trafiłaby na SMS u realnego
                operatora (tutaj tylko widoczna w logu).
        """
        self._sender_name = sender_name

    @property
    def provider_code(self) -> str:
        """Kod tej bramki widoczny w logach i audycie."""
        return "logging"

    async def send(self, phone: str, text: str) -> SmsResult:
        """Loguje treść SMS i zwraca wynik sukcesu (bez realnej wysyłki)."""
        logger.info(
            "[SMS TEST | nadawca={}] -> {}\n{}",
            self._sender_name,
            phone,
            text,
        )
        return SmsResult(success=True, provider_message_id="logged")

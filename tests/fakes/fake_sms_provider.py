"""Fake implementacja SmsProvider - zapamiętuje wysyłki zamiast realnej bramki."""

from __future__ import annotations

from app.domain.entities.sms_message import SmsResult
from app.domain.interfaces.sms_provider import SmsProvider


class FakeSmsProvider(SmsProvider):
    """
    Bramka testowa. Domyślnie "wysyła" pomyślnie i zapisuje treść w `sent`.

    Flagi pozwalają symulować dwa tryby awarii:
    - should_raise: bramka rzuca wyjątek (błąd sieci),
    - should_fail: bramka odpowiada, ale odrzuca wiadomość.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.should_raise: bool = False
        self.should_fail: bool = False
        self.error_text: str = "Odrzucono przez bramkę testową"

    @property
    def provider_code(self) -> str:
        return "fake"

    async def send(self, phone: str, text: str) -> SmsResult:
        if self.should_raise:
            raise RuntimeError("Symulowany błąd sieci bramki SMS")
        if self.should_fail:
            return SmsResult(success=False, error=self.error_text)
        self.sent.append((phone, text))
        return SmsResult(success=True, provider_message_id="fake-123")

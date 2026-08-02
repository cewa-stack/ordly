"""Abstrakcja bramki SMS, niezależna od konkretnego operatora."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.sms_message import SmsResult


class SmsProvider(ABC):
    """
    Kontrakt wysyłki pojedynczej wiadomości SMS.

    Dodanie realnego operatora (SMSAPI, SerwerSMS, Twilio) sprowadza się
    do nowej implementacji tego interfejsu w infrastructure/sms/ i wskazania
    jej w konfiguracji - logika biznesowa (SmsService) nie ulega zmianie.
    """

    @property
    @abstractmethod
    def provider_code(self) -> str:
        """Zwraca kod operatora (np. 'logging', 'smsapi'), używany w logach."""
        raise NotImplementedError

    @abstractmethod
    async def send(self, phone: str, text: str) -> SmsResult:
        """
        Wysyła pojedynczą wiadomość SMS.

        Implementacja NIE powinna rzucać wyjątku dla zwykłego odrzucenia
        przez bramkę - powinna zwrócić SmsResult(success=False, error=...).
        Wyjątki są dopuszczalne wyłącznie dla błędów sieciowych/nieoczekiwanych
        i są przechwytywane przez SmsService.
        """
        raise NotImplementedError

"""Kontrakt dostępu do przechowywanych subskrypcji Web Push."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.push_subscription import PushSubscription


class PushSubscriptionRepository(ABC):
    """Przechowuje subskrypcje Web Push, po jednej na endpoint przeglądarki."""

    @abstractmethod
    async def add(self, subscription: PushSubscription) -> None:
        """
        Zapisuje subskrypcję. Gdy `endpoint` już istnieje, aktualizuje
        jego klucze (`p256dh`/`auth`) zamiast tworzyć duplikat - przeglądarka
        może zwrócić ten sam endpoint z odnowionymi kluczami.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all(self) -> list[PushSubscription]:
        """Zwraca wszystkie zapisane subskrypcje (odbiorców powiadomień push)."""
        raise NotImplementedError

    @abstractmethod
    async def delete_by_endpoint(self, endpoint: str) -> None:
        """
        Usuwa subskrypcję po jej endpoincie.

        Wywoływane zarówno na jawne żądanie (wylogowanie w apce), jak i
        automatycznie przez `WebPushNotifier`, gdy przeglądarka odrzuci
        wysyłkę kodem 404/410 (subskrypcja wygasła/została odwołana).
        """
        raise NotImplementedError

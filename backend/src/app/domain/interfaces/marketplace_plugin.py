"""
Abstrakcyjny kontrakt, który musi zaimplementować każdy plugin
marketplace (Allegro, Amazon, eBay, ...).

Warstwa aplikacyjna (services/, scheduler/, bot/) komunikuje się
WYŁĄCZNIE poprzez ten interfejs - nigdy nie importuje niczego
bezpośrednio z infrastructure/plugins/{nazwa}.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.customer import Customer
from app.domain.entities.issue import Issue, IssueMessage
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.domain.entities.shipment import Shipment


class MarketplacePlugin(ABC):
    """Wspólny kontrakt dla wszystkich integracji marketplace."""

    @property
    @abstractmethod
    def marketplace_code(self) -> str:
        """Zwraca unikalny kod marketplace (np. 'allegro'), używany w rejestrze."""
        raise NotImplementedError

    @abstractmethod
    async def authenticate(self) -> None:
        """Wykonuje pełny proces autoryzacji (np. OAuth2 + PKCE)."""
        raise NotImplementedError

    @abstractmethod
    async def refresh_token(self) -> None:
        """Odświeża wygasły token dostępowy przy użyciu refresh tokenu."""
        raise NotImplementedError

    @abstractmethod
    async def get_orders(self, since: str | None = None) -> list[Order]:
        """
        Pobiera listę zamówień, opcjonalnie od podanej daty/znacznika.

        Args:
            since: Znacznik czasu lub kursor, od którego pobierać
                nowe zamówienia. None oznacza pobranie najnowszych.

        Returns:
            Lista encji domenowych Order (nie surowy JSON marketplace).
        """
        raise NotImplementedError

    async def get_customer_returns(self) -> list[OrderReturn]:
        """
        Pobiera listę zwrotów klientów z marketplace.

        Metoda ma domyślną implementację (pusta lista), aby nie wymuszać
        obsługi zwrotów na marketplace'ach, które ich nie udostępniają -
        realne pluginy (np. Allegro) powinny ją nadpisać.
        """
        return []

    async def get_issues(self) -> list[Issue]:
        """
        Pobiera listę dyskusji i reklamacji pozakupowych z marketplace.

        Domyślna pusta implementacja - jak get_customer_returns, nie
        każdy marketplace musi obsługiwać ten koncept.
        """
        return []

    async def get_issue_messages(self, issue_id: str) -> list[IssueMessage]:
        """Pobiera wątek wiadomości pojedynczej dyskusji/reklamacji."""
        return []

    async def reply_to_issue(self, issue_id: str, text: str) -> None:
        """
        Wysyła odpowiedź sprzedawcy w dyskusji/reklamacji.

        W odróżnieniu od odczytów (pusta lista domyślnie), brak wsparcia
        tutaj rzuca NotImplementedError - cicha "udana" odpowiedź, która
        nigdzie nie dotarła, byłaby myląca dla użytkownika.
        """
        raise NotImplementedError(
            f"{self.marketplace_code} nie obsługuje odpowiedzi na dyskusje/reklamacje"
        )

    async def set_fulfillment_status(self, external_id: str, status: str) -> None:
        """
        Ustawia status realizacji zamówienia po stronie marketplace.

        Jak `reply_to_issue`: brak wsparcia rzuca NotImplementedError,
        nie "udaje sukcesu". Cicha zgoda na zapis, ktory nigdzie nie
        dotarl, jest gorsza niz jawny blad - sprzedawca myslalby, ze
        kupujacy widzi juz "wysłane".
        """
        raise NotImplementedError(
            f"{self.marketplace_code} nie obsługuje zmiany statusu realizacji"
        )

    @abstractmethod
    async def get_order(self, external_id: str) -> Order:
        """Pobiera szczegóły pojedynczego zamówienia po jego identyfikatorze."""
        raise NotImplementedError

    @abstractmethod
    async def get_tracking(self, external_id: str) -> Shipment:
        """Pobiera aktualny status pierwszej przesyłki dla danego zamówienia."""
        raise NotImplementedError

    @abstractmethod
    async def get_all_trackings(self, external_id: str) -> list[Shipment]:
        """
        Pobiera statusy wszystkich przesyłek powiązanych z zamówieniem.

        Zwraca pustą listę, jeśli sprzedawca jeszcze nie nadał żadnej
        paczki - to jest prawidłowy stan biznesowy, nie błąd.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_products(self) -> list[Product]:
        """Pobiera listę produktów sprzedawcy dostępnych w marketplace."""
        raise NotImplementedError

    @abstractmethod
    async def get_customer(self, external_id: str) -> Customer:
        """Pobiera dane kupującego powiązane z zamówieniem."""
        raise NotImplementedError

    @abstractmethod
    async def validate_webhook(self, payload: bytes, signature: str) -> bool:
        """Weryfikuje autentyczność przychodzącego webhooka."""
        raise NotImplementedError

    async def check_connection(self) -> bool:
        """
        Weryfikuje, że plugin jest gotowy do komunikacji z marketplace
        (np. posiada ważny lub odświeżalny token dostępowy).

        Metoda ma domyślną implementację, aby nie wymuszać jej na
        prostych implementacjach testowych - realne pluginy powinny
        ją nadpisać.
        """
        return True

"""Bazowe wyjątki domenowe - niezależne od żadnego marketplace."""

from __future__ import annotations


class DomainError(Exception):
    """Bazowa klasa dla wszystkich wyjątków warstwy domenowej."""


class OrderNotFoundError(DomainError):
    """Zamówienie o podanym identyfikatorze nie istnieje."""

    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"Zamówienie o numerze '{external_id}' nie zostało znalezione")


class AuthenticationError(DomainError):
    """Autoryzacja z marketplace nie powiodła się."""


class TokenExpiredError(DomainError):
    """Token dostępowy wygasł i nie udało się go odświeżyć."""


class MarketplaceUnavailableError(DomainError):
    """Marketplace API jest chwilowo niedostępne (timeout, 5xx, brak sieci)."""


class DuplicateOrderError(DomainError):
    """
    Zamówienie o danym (marketplace, external_id) już istnieje w bazie.

    Rzucane przez repozytorium, gdy unique constraint zablokuje zapis -
    wyścig między exists() a save() w dwóch równoległych synchronizacjach.
    """

    def __init__(self, marketplace: str, external_id: str) -> None:
        self.marketplace = marketplace
        self.external_id = external_id
        super().__init__(f"Zamówienie {marketplace}/{external_id} już istnieje w bazie")


class DuplicateReturnError(DomainError):
    """
    Zwrot o danym (marketplace, external_id) już istnieje w bazie.

    Rzucane przez repozytorium, gdy unique constraint zablokuje zapis -
    wyścig między exists() a save() w dwóch równoległych synchronizacjach.
    """

    def __init__(self, marketplace: str, external_id: str) -> None:
        self.marketplace = marketplace
        self.external_id = external_id
        super().__init__(f"Zwrot {marketplace}/{external_id} już istnieje w bazie")


class InventoryItemNotFoundError(DomainError):
    """Produkt magazynowy o podanym SKU nie istnieje."""

    def __init__(self, sku: str) -> None:
        self.sku = sku
        super().__init__(f"Produkt o SKU '{sku}' nie istnieje w magazynie")


class DuplicateInventoryItemError(DomainError):
    """Produkt magazynowy o danym SKU już istnieje w bazie."""

    def __init__(self, sku: str) -> None:
        self.sku = sku
        super().__init__(f"Produkt o SKU '{sku}' już istnieje w magazynie")


class InsufficientStockError(DomainError):
    """Ręczna operacja zdjęcia ze stanu przekracza dostępną ilość."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(
            f"Nie można zdjąć {requested} szt. produktu '{sku}' - dostępne {available} szt."
        )


class ShipmentNotAvailableError(DomainError):
    """Zamówienie istnieje, ale sprzedawca jeszcze nie nadał żadnej przesyłki."""

    def __init__(self, order_external_id: str) -> None:
        self.order_external_id = order_external_id
        super().__init__(f"Zamówienie {order_external_id} nie ma jeszcze nadanej przesyłki")


class MailNotConfiguredError(DomainError):
    """SMTP nie jest skonfigurowany w .env - wysyłka maili jest niedostępna."""

    def __init__(self) -> None:
        super().__init__(
            "Wysyłka maili nie jest skonfigurowana - ustaw SMTP_HOST/SMTP_USER/"
            "SMTP_PASS w pliku .env na Raspberry Pi"
        )


class MailSendError(DomainError):
    """Wysyłka maila nie powiodła się (błąd połączenia/logowania SMTP)."""


class MailboxNotConfiguredError(DomainError):
    """
    IMAP nie jest skonfigurowany w .env - skrzynka jest niedostępna.

    Osobno od `MailNotConfiguredError`, bo tamten dotyczy WYSYŁKI (SMTP)
    i podpowiada inne zmienne środowiskowe - wspólny komunikat wysyłałby
    użytkownika do złej sekcji `.env`.
    """

    def __init__(self) -> None:
        super().__init__(
            "Skrzynka nie jest podłączona - ustaw IMAP_HOST/IMAP_USER/IMAP_PASS "
            "w pliku .env na Raspberry Pi"
        )


class MailMessageNotFoundError(DomainError):
    """
    Maila nie ma już na serwerze IMAP, mimo że ORDLY zna jego metadane.

    Normalna sytuacja: wiadomość została skasowana albo przeniesiona
    poza INBOX w kliencie pocztowym. ORDLY trzyma tylko metadane, więc
    treści nie ma skąd odtworzyć.
    """

    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        super().__init__(
            f"Wiadomości {message_id} nie ma już w skrzynce - mogła zostać "
            "usunięta lub przeniesiona poza INBOX"
        )

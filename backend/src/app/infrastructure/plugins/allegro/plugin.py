"""
Implementacja MarketplacePlugin dla Allegro.

To jedyna klasa w całym systemie, która "spina" auth.py, client.py
i mapper.py w jedną spójną całość zgodną z kontraktem domenowym.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from loguru import logger

from app.domain.entities.customer import Customer
from app.domain.entities.issue import Issue, IssueMessage
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.domain.entities.shipment import Shipment
from app.domain.exceptions.domain_exceptions import TokenExpiredError
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.token_store import TokenStore
from app.infrastructure.plugins.allegro.auth import (
    AllegroOAuthClient,
    PkcePair,
    TokenEncryptor,
)
from app.infrastructure.plugins.allegro.client import AllegroApiClient
from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.mapper import (
    map_checkout_form_to_order,
    map_customer_return_to_domain,
    map_issue_message_to_domain,
    map_issue_to_domain,
    map_shipments_list_to_domain,
)
from app.utils.time import utc_now

_TOKEN_REFRESH_MARGIN = timedelta(minutes=5)

# Kilka zasobów Allegro API jest oznaczonych jako beta i wymaga jawnego
# nagłówka Accept, inaczej niż reszta pluginu (public.v1): "Post Purchase
# Issues" (dyskusje + reklamacje, od czerwca 2025 zastąpiły /sale/disputes)
# oraz /order/customer-returns (potwierdzone w oficjalnym swagger.yaml -
# oznaczone tam "[BETA]"), stąd 406 Not Acceptable przy domyślnym public.v1.
_BETA_ACCEPT_HEADER = "application/vnd.allegro.beta.v1+json"


class AllegroPlugin(MarketplacePlugin):
    """Integracja z Allegro REST API zgodna z kontraktem MarketplacePlugin."""

    def __init__(
        self,
        config: AllegroConfig,
        token_store: TokenStore,
    ) -> None:
        """
        Inicjalizuje plugin Allegro.

        Args:
            config: Konfiguracja OAuth2 i adresów API dla Allegro.
            token_store: Abstrakcja dostępu do zapisanych tokenów.
        """
        self._config = config
        self._token_store = token_store
        self._oauth_client = AllegroOAuthClient(config)
        self._api_client = AllegroApiClient(config)
        self._encryptor = TokenEncryptor(config.token_encryption_key.get_secret_value())

    @property
    def marketplace_code(self) -> str:
        """Zwraca kod tego marketplace używany w rejestrze pluginów."""
        return "allegro"

    async def authenticate(self) -> None:
        """Wykonuje pełny proces OAuth2 + PKCE i zapisuje otrzymane tokeny."""
        pkce = PkcePair()
        auth_url = self._oauth_client.build_authorization_url(pkce)
        logger.info("Otwórz w przeglądarce, aby zalogować się do Allegro: {}", auth_url)

        code = await self._oauth_client.wait_for_authorization_code(pkce)
        tokens = await self._oauth_client.exchange_code_for_tokens(code, pkce)

        await self._token_store.save_tokens(
            marketplace=self.marketplace_code,
            encrypted_access_token=self._encryptor.encrypt(tokens.access_token),
            encrypted_refresh_token=self._encryptor.encrypt(tokens.refresh_token),
            expires_at=tokens.expires_at,
        )
        logger.info("Autoryzacja Allegro zakończona pomyślnie")

    async def refresh_token(self) -> None:
        """Odświeża token dostępowy przy użyciu zapisanego refresh tokenu."""
        stored = await self._token_store.get_tokens(self.marketplace_code)
        if stored is None:
            raise TokenExpiredError(
                "Brak zapisanych tokenów Allegro - konieczna ponowna autoryzacja "
                "(uruchom authenticate())"
            )

        refresh_token = self._encryptor.decrypt(stored.encrypted_refresh_token)
        tokens = await self._oauth_client.refresh_access_token(refresh_token)

        await self._token_store.save_tokens(
            marketplace=self.marketplace_code,
            encrypted_access_token=self._encryptor.encrypt(tokens.access_token),
            encrypted_refresh_token=self._encryptor.encrypt(tokens.refresh_token),
            expires_at=tokens.expires_at,
        )
        logger.info("Token Allegro odświeżony pomyślnie")

    async def _get_valid_access_token(self) -> str:
        """
        Zwraca ważny access token, odświeżając go automatycznie w razie potrzeby.

        Returns:
            Odszyfrowany, ważny access token.

        Raises:
            TokenExpiredError: Gdy brak tokenów i konieczna jest pełna
                ponowna autoryzacja (authenticate()).
        """
        stored = await self._token_store.get_tokens(self.marketplace_code)
        if stored is None:
            raise TokenExpiredError("Brak zapisanych tokenów Allegro - wymagana autoryzacja")

        if utc_now() + _TOKEN_REFRESH_MARGIN >= stored.expires_at:
            await self.refresh_token()
            stored = await self._token_store.get_tokens(self.marketplace_code)
            assert stored is not None

        return self._encryptor.decrypt(stored.encrypted_access_token)

    async def get_orders(self, since: str | None = None) -> list[Order]:
        """Pobiera listę zamówień (checkout forms) z Allegro."""
        access_token = await self._get_valid_access_token()
        params: dict[str, str] = {"limit": "50", "sort": "-lineItems.boughtAt"}
        if since:
            params["lineItems.boughtAt.gte"] = since

        response = await self._api_client.get(
            "/order/checkout-forms", access_token, params=params
        )
        raw_orders = response.get("checkoutForms", [])
        return [map_checkout_form_to_order(raw) for raw in raw_orders]

    async def get_customer_returns(self) -> list[OrderReturn]:
        """Pobiera listę zwrotów klientów (customer returns) z Allegro."""
        access_token = await self._get_valid_access_token()
        response = await self._api_client.get(
            "/order/customer-returns",
            access_token,
            params={"limit": "50"},
            accept=_BETA_ACCEPT_HEADER,
        )
        raw_returns = response.get("customerReturns", [])
        return [map_customer_return_to_domain(raw) for raw in raw_returns]

    async def get_order(self, external_id: str) -> Order:
        """Pobiera szczegóły pojedynczego zamówienia po jego numerze."""
        access_token = await self._get_valid_access_token()
        raw = await self._api_client.get(f"/order/checkout-forms/{external_id}", access_token)
        return map_checkout_form_to_order(raw)

    async def get_tracking(self, external_id: str) -> Shipment:
        """
        Pobiera aktualny status pierwszej przesyłki dla podanego zamówienia.

        Jeśli zamówienie ma więcej niż jedną przesyłkę, ta metoda zwraca
        tylko pierwszą - użyj get_all_trackings(), aby pobrać wszystkie.
        """
        shipments = await self.get_all_trackings(external_id)
        if not shipments:
            return Shipment(
                order_external_id=external_id,
                carrier=None,
                tracking_number=None,
                status="PRZYGOTOWYWANA",
                updated_at=None,
            )
        return shipments[0]

    async def get_all_trackings(self, external_id: str) -> list[Shipment]:
        """
        Pobiera statusy wszystkich przesyłek powiązanych z zamówieniem.

        Args:
            external_id: Numer zamówienia Allegro.

        Returns:
            Lista przesyłek - pusta, jeśli sprzedawca nie nadał jeszcze
            żadnej paczki (to nie jest błąd, tylko stan biznesowy).
        """
        access_token = await self._get_valid_access_token()
        raw = await self._api_client.get(
            f"/order/checkout-forms/{external_id}/shipments", access_token
        )
        raw_shipments = raw.get("shipments", [])
        return map_shipments_list_to_domain(external_id, raw_shipments)

    async def get_issues(self) -> list[Issue]:
        """Pobiera listę dyskusji i reklamacji (post purchase issues) z Allegro."""
        access_token = await self._get_valid_access_token()
        response = await self._api_client.get(
            "/sale/issues",
            access_token,
            params={"limit": "50"},
            accept=_BETA_ACCEPT_HEADER,
        )
        return [map_issue_to_domain(raw) for raw in response.get("issues", [])]

    async def get_issue_messages(self, issue_id: str) -> list[IssueMessage]:
        """Pobiera wątek wiadomości (chat) dla jednej dyskusji/reklamacji."""
        access_token = await self._get_valid_access_token()
        response = await self._api_client.get(
            f"/sale/issues/{issue_id}/chat",
            access_token,
            params={"limit": "100"},
            accept=_BETA_ACCEPT_HEADER,
        )
        return [map_issue_message_to_domain(raw) for raw in response.get("chat", [])]

    async def reply_to_issue(self, issue_id: str, text: str) -> None:
        """
        Wysyła nową wiadomość (odpowiedź sprzedawcy) w dyskusji/reklamacji.

        `type: "REGULAR"` to zwykła wiadomość w wątku - Allegro rezerwuje
        inne typy (`END_REQUEST`, warianty zwrotu) dla specyficznych akcji
        formalnych, których ten plugin świadomie nie obsługuje.
        """
        access_token = await self._get_valid_access_token()
        await self._api_client.post(
            f"/sale/issues/{issue_id}/message",
            access_token,
            json_body={"text": text, "type": "REGULAR"},
            accept=_BETA_ACCEPT_HEADER,
        )

    async def set_fulfillment_status(self, external_id: str, status: str) -> None:
        """
        Ustawia status realizacji zamówienia (`PUT .../fulfillment`).

        Allegro przyjmuje tu m.in. `NEW`, `PROCESSING`, `READY_FOR_SHIPMENT`,
        `SENT`, `PICKED_UP`. Endpoint odpowiada 204 bez ciała.

        Wymaga uprawnienia `allegro:api:orders:write` na poziomie
        REJESTRACJI aplikacji w apps.developer.allegro.pl - bez niego
        Allegro zwraca 403 AccessDenied i sam ponowny login nic nie da
        (ta sama pułapka co przy dyskusjach).
        """
        access_token = await self._get_valid_access_token()
        await self._api_client.put(
            f"/order/checkout-forms/{external_id}/fulfillment",
            access_token,
            json_body={"status": status},
        )

    async def get_products(self) -> list[Product]:
        """Pobiera listę ofert (produktów) sprzedawcy."""
        access_token = await self._get_valid_access_token()
        response = await self._api_client.get(
            "/sale/offers", access_token, params={"limit": "100"}
        )
        return [
            Product(
                external_id=item.get("id", ""),
                name=item.get("name", "nieznany produkt"),
                quantity=int(item.get("stock", {}).get("available", 0)),
                unit_price=Decimal(
                    str(item.get("sellingMode", {}).get("price", {}).get("amount", "0.00"))
                ),
            )
            for item in response.get("offers", [])
        ]

    async def get_customer(self, external_id: str) -> Customer:
        """
        Pobiera dane kupującego na podstawie zamówienia.

        Allegro API nie udostępnia oddzielnego endpointu do pobrania
        kupującego po jego ID - dane kupującego są zawsze zagnieżdżone
        w zamówieniu.
        """
        order = await self.get_order(external_id)
        return order.buyer

    async def check_connection(self) -> bool:
        """
        Weryfikuje, że plugin posiada ważny (lub odświeżalny) token dostępowy.

        Używane przez HealthService - nie wykonuje pełnego zapytania do
        API, jedynie sprawdza/odświeża token.
        """
        await self._get_valid_access_token()
        return True

    async def validate_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Weryfikuje podpis webhooka Allegro.

        Projekt nie korzysta obecnie z webhooków Allegro (synchronizacja
        odbywa się przez polling co 60s), więc metoda zwraca False.
        """
        logger.warning("validate_webhook() wywołane, ale webhooki nie są jeszcze obsługiwane")
        return False

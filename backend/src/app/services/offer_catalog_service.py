"""
Magazyn ORDLY: lista ofert wystawionych na marketplace i ilość przy każdej.

DLACZEGO TAK, A NIE OSOBNY REJESTR PRODUKTÓW. Wcześniej magazyn był
niezależną listą SKU z recepturami ofert i automatycznym odejmowaniem
stanów przy sprzedaży. Działało to dokładnie tak dobrze, jak kompletne
były receptury - oferta bez receptury sprzedawała się obok magazynu,
a błędna odejmowała nie ten towar, więc liczby były mieszaniną stanów
prawdziwych i takich, których nikt nie pilnował. Teraz jednostką jest
oferta: widać, co jest wystawione i po ile, a ilość wpisuje człowiek.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.offer_stock_movement import OfferStockMovement
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.shared.dto.offer_catalog_dto import CatalogSyncResult
from app.utils.time import utc_now

#: Ile wpisów historii pokazać, gdy nikt nie poprosił o konkretną liczbę.
DEFAULT_HISTORY_LIMIT = 20


class OfferCatalogService:
    """Pobiera ofertę z marketplace i prowadzi ręczne ilości przy niej."""

    def __init__(
        self,
        plugin: MarketplacePlugin,
        catalog_repository: OfferCatalogRepository,
    ) -> None:
        """
        Args:
            plugin: Plugin marketplace, z którego schodzi asortyment.
            catalog_repository: Lokalna kopia katalogu ofert.
        """
        self._plugin = plugin
        self._catalog = catalog_repository

    @property
    def marketplace(self) -> str:
        """Kod marketplace obsługiwanego przez wstrzyknięty plugin."""
        return self._plugin.marketplace_code

    async def sync(self) -> CatalogSyncResult:
        """
        Pobiera asortyment z marketplace i dosuwa do niego lokalny katalog.

        Returns:
            Ile ofert zeszło, ile z nich jest nowych i ile zniknęło.

        Raises:
            MarketplaceUnavailableError: Gdy API marketplace odmówiło
                odpowiedzi. Katalog zostaje wtedy nietknięty - lepiej
                pokazać wczorajszą listę niż wyczyścić ją razem z ręcznie
                wpisanymi ilościami z powodu chwilowej awarii sieci.
        """
        try:
            offers = await self._plugin.get_offers()
        except AllegroApiError as exc:
            logger.error("Nie udało się pobrać asortymentu z Allegro: {}", exc)
            raise MarketplaceUnavailableError(str(exc)) from exc

        changes = await self._catalog.upsert_all(self.marketplace, offers)

        logger.info(
            "Katalog {}: {} ofert, {} nowych, {} zdjętych",
            self.marketplace,
            len(offers),
            changes.added,
            changes.removed,
        )
        return CatalogSyncResult(
            marketplace=self.marketplace,
            fetched=len(offers),
            added=changes.added,
            removed=changes.removed,
            synced_at=utc_now(),
        )

    async def get_offers(self) -> list[MarketplaceOffer]:
        """Zwraca wystawione oferty razem z ręcznie wpisanymi ilościami."""
        return await self._catalog.get_all(self.marketplace)

    async def set_quantity(
        self, marketplace: str, external_id: str, quantity: int, reason: str
    ) -> MarketplaceOffer:
        """
        Zapisuje ręcznie policzoną ilość przy ofercie.

        Raises:
            OfferNotFoundError: Gdy oferty nie ma w katalogu.
        """
        return await self._catalog.set_quantity(marketplace, external_id, quantity, reason)

    async def get_history(
        self, marketplace: str, external_id: str, limit: int = DEFAULT_HISTORY_LIMIT
    ) -> list[OfferStockMovement]:
        """
        Zwraca historię ręcznych zmian ilości dla jednej oferty.

        Raises:
            OfferNotFoundError: Gdy oferty nie ma w katalogu.
        """
        return await self._catalog.get_history(marketplace, external_id, limit)

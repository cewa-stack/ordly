"""Implementacja repozytorium katalogu ofert marketplace na SQLite."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.marketplace_offer_model import MarketplaceOfferModel
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository


class SqliteOfferCatalogRepository(OfferCatalogRepository):
    """Katalog ofert marketplace przechowywany w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja.
        """
        self._session = session

    async def replace_all(self, marketplace: str, offers: list[MarketplaceOffer]) -> int:
        """
        Podmienia cały katalog danego marketplace.

        Kasowanie i wstawianie idzie w jednej sesji, więc albo katalog
        podmieni się w całości, albo nie zmieni się wcale - pusty katalog
        w połowie synchronizacji zgasiłby wszystkie powiązania w UI.
        """
        await self._session.execute(
            delete(MarketplaceOfferModel).where(
                MarketplaceOfferModel.marketplace == marketplace
            )
        )
        self._session.add_all(
            [
                MarketplaceOfferModel(
                    marketplace=offer.marketplace,
                    external_id=offer.external_id,
                    name=offer.name,
                    signature=offer.signature,
                    status=offer.status,
                    available_stock=offer.available_stock,
                    sold_count=offer.sold_count,
                    price=offer.price,
                    image_url=offer.image_url,
                    synced_at=offer.synced_at,
                )
                for offer in offers
            ]
        )
        await self._session.flush()
        return len(offers)

    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        """Zwraca katalog posortowany po nazwie oferty."""
        stmt = select(MarketplaceOfferModel).order_by(MarketplaceOfferModel.name)
        if marketplace is not None:
            stmt = stmt.where(MarketplaceOfferModel.marketplace == marketplace)
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        """Zwraca jedną ofertę katalogu albo None."""
        result = await self._session.execute(
            select(MarketplaceOfferModel).where(
                MarketplaceOfferModel.marketplace == marketplace,
                MarketplaceOfferModel.external_id == external_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_domain(model)

    async def last_synced_at(self, marketplace: str) -> datetime | None:
        """Zwraca najświeższy znacznik synchronizacji w katalogu."""
        result = await self._session.execute(
            select(MarketplaceOfferModel.synced_at)
            .where(MarketplaceOfferModel.marketplace == marketplace)
            .order_by(MarketplaceOfferModel.synced_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(model: MarketplaceOfferModel) -> MarketplaceOffer:
        """Mapuje wiersz ORM na encję domenową."""
        return MarketplaceOffer(
            marketplace=model.marketplace,
            external_id=model.external_id,
            name=model.name,
            signature=model.signature,
            status=model.status,
            available_stock=model.available_stock,
            sold_count=model.sold_count,
            price=Decimal(str(model.price)) if model.price is not None else None,
            image_url=model.image_url,
            synced_at=model.synced_at,
        )

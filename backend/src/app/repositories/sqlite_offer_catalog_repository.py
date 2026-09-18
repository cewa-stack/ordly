"""Implementacja repozytorium katalogu ofert marketplace na SQLite."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.marketplace_offer_model import MarketplaceOfferModel
from app.database.models.offer_stock_movement_model import OfferStockMovementModel
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.offer_stock_movement import OfferStockMovement
from app.domain.exceptions.domain_exceptions import OfferNotFoundError
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository
from app.shared.dto.offer_catalog_dto import CatalogUpsertResult
from app.utils.time import utc_now


class SqliteOfferCatalogRepository(OfferCatalogRepository):
    """Katalog ofert marketplace przechowywany w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja.
        """
        self._session = session

    async def upsert_all(
        self, marketplace: str, offers: list[MarketplaceOffer]
    ) -> CatalogUpsertResult:
        """
        Dosuwa katalog do pobranej listy: aktualizuje, dodaje, kasuje.

        DLACZEGO NIE "SKASUJ I WSTAW". Wcześniej synchronizacja czyściła
        cały katalog i wstawiała go od nowa - proste, bo wszystkie dane
        pochodziły z API i były odtwarzalne. Od czasu, gdy przy ofercie
        leży ręcznie wpisana ilość, to już nieprawda: takie odświeżenie
        kasowałoby przy każdym kliknięciu "Synchronizuj" jedyną liczbę,
        której marketplace nie zna.

        Wszystko idzie w jednej sesji, więc albo katalog dosunie się
        w całości, albo nie zmieni się wcale.
        """
        existing = {
            model.external_id: model
            for model in await self._models_for(marketplace)
        }

        # Plugin wypełnia `synced_at`, ale kolumna jest NOT NULL, więc
        # ofertę bez znacznika stemplujemy momentem tej synchronizacji.
        now = utc_now()
        incoming_ids: set[str] = set()
        added = 0
        for offer in offers:
            incoming_ids.add(offer.external_id)
            model = existing.get(offer.external_id)
            if model is None:
                added += 1
                self._session.add(
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
                        synced_at=offer.synced_at or now,
                    )
                )
                continue

            model.name = offer.name
            model.signature = offer.signature
            model.status = offer.status
            model.available_stock = offer.available_stock
            model.sold_count = offer.sold_count
            model.price = offer.price
            model.image_url = offer.image_url
            model.synced_at = offer.synced_at or now

        stale = [
            model.id for external_id, model in existing.items() if external_id not in incoming_ids
        ]
        if stale:
            # Historia ilości schodzi jawnie, a nie kaskadą z klucza
            # obcego: SQLite egzekwuje ON DELETE CASCADE tylko przy
            # włączonym PRAGMA foreign_keys, więc opieranie się na nim
            # zostawiłoby sieroty przy pierwszym połączeniu bez pragmy.
            await self._session.execute(
                delete(OfferStockMovementModel).where(
                    OfferStockMovementModel.offer_id.in_(stale)
                )
            )
            await self._session.execute(
                delete(MarketplaceOfferModel).where(MarketplaceOfferModel.id.in_(stale))
            )

        await self._session.flush()
        return CatalogUpsertResult(added=added, removed=len(stale))

    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        """Zwraca katalog posortowany po nazwie oferty."""
        stmt = select(MarketplaceOfferModel).order_by(MarketplaceOfferModel.name)
        if marketplace is not None:
            stmt = stmt.where(MarketplaceOfferModel.marketplace == marketplace)
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        """Zwraca jedną ofertę katalogu albo None."""
        model = await self._get_model(marketplace, external_id)
        return None if model is None else self._to_domain(model)

    async def set_quantity(
        self, marketplace: str, external_id: str, quantity: int, reason: str
    ) -> MarketplaceOffer:
        """Zapisuje ilość i dokłada wpis do historii tej oferty."""
        model = await self._get_model(marketplace, external_id)
        if model is None:
            raise OfferNotFoundError(marketplace, external_id)

        previous = model.quantity_on_hand
        model.quantity_on_hand = quantity
        self._session.add(
            OfferStockMovementModel(
                offer_id=model.id,
                change=None if previous is None else quantity - previous,
                quantity_after=quantity,
                reason=reason,
            )
        )
        await self._session.flush()
        return self._to_domain(model)

    async def get_history(
        self, marketplace: str, external_id: str, limit: int
    ) -> list[OfferStockMovement]:
        """Zwraca historię ręcznych zmian ilości, od najnowszej."""
        model = await self._get_model(marketplace, external_id)
        if model is None:
            raise OfferNotFoundError(marketplace, external_id)

        result = await self._session.execute(
            select(OfferStockMovementModel)
            .where(OfferStockMovementModel.offer_id == model.id)
            .order_by(OfferStockMovementModel.created_at.desc())
            .limit(limit)
        )
        return [
            OfferStockMovement(
                change=movement.change,
                quantity_after=movement.quantity_after,
                reason=movement.reason,
                occurred_at=movement.created_at,
            )
            for movement in result.scalars().all()
        ]

    async def last_synced_at(self, marketplace: str) -> datetime | None:
        """Zwraca najświeższy znacznik synchronizacji w katalogu."""
        result = await self._session.execute(
            select(MarketplaceOfferModel.synced_at)
            .where(MarketplaceOfferModel.marketplace == marketplace)
            .order_by(MarketplaceOfferModel.synced_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _models_for(self, marketplace: str) -> list[MarketplaceOfferModel]:
        """Zwraca wiersze ORM jednego marketplace."""
        result = await self._session.execute(
            select(MarketplaceOfferModel).where(
                MarketplaceOfferModel.marketplace == marketplace
            )
        )
        return list(result.scalars().all())

    async def _get_model(
        self, marketplace: str, external_id: str
    ) -> MarketplaceOfferModel | None:
        """Zwraca wiersz ORM jednej oferty albo None."""
        result = await self._session.execute(
            select(MarketplaceOfferModel).where(
                MarketplaceOfferModel.marketplace == marketplace,
                MarketplaceOfferModel.external_id == external_id,
            )
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
            quantity_on_hand=model.quantity_on_hand,
        )

"""Implementacja PushSubscriptionRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.push_subscription_model import PushSubscriptionModel
from app.domain.entities.push_subscription import PushSubscription
from app.domain.interfaces.push_subscription_repository import (
    PushSubscriptionRepository,
)


class SqlitePushSubscriptionRepository(PushSubscriptionRepository):
    """Dostęp do subskrypcji Web Push przechowywanych w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja.
        """
        self._session = session

    async def add(self, subscription: PushSubscription) -> None:
        """Zapisuje subskrypcję - aktualizuje klucze, gdy endpoint już istnieje."""
        stmt = select(PushSubscriptionModel).where(
            PushSubscriptionModel.endpoint == subscription.endpoint
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.p256dh = subscription.p256dh
            existing.auth = subscription.auth
            return

        self._session.add(
            PushSubscriptionModel(
                endpoint=subscription.endpoint,
                p256dh=subscription.p256dh,
                auth=subscription.auth,
            )
        )

    async def get_all(self) -> list[PushSubscription]:
        """Zwraca wszystkie zapisane subskrypcje."""
        stmt = select(PushSubscriptionModel)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete_by_endpoint(self, endpoint: str) -> None:
        """Usuwa subskrypcję o podanym endpoincie (brak - operacja jest no-opem)."""
        stmt = delete(PushSubscriptionModel).where(
            PushSubscriptionModel.endpoint == endpoint
        )
        await self._session.execute(stmt)

    @staticmethod
    def _to_domain(model: PushSubscriptionModel) -> PushSubscription:
        """Mapuje model ORM na encję domenową."""
        return PushSubscription(
            endpoint=model.endpoint,
            p256dh=model.p256dh,
            auth=model.auth,
            created_at=model.created_at,
        )

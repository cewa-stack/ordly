"""Implementacja OrdlakRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ordlak_generation_model import OrdlakGenerationModel
from app.domain.entities.ordlak_generation import OrdlakGeneration
from app.domain.interfaces.ordlak_repository import OrdlakRepository


class SqliteOrdlakRepository(OrdlakRepository):
    """Historia generacji Ordlaka przechowywana w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, generation: OrdlakGeneration) -> OrdlakGeneration:
        model = OrdlakGenerationModel(
            user_note=generation.user_note,
            condition=generation.condition,
            purchase_cost=generation.purchase_cost,
            inbound_shipping_cost=generation.inbound_shipping_cost,
            buyer_shipping_cost=generation.buyer_shipping_cost,
            commission_percent=generation.commission_percent,
            target_margin_percent=generation.target_margin_percent,
            photo_count=generation.photo_count,
            generated_title=generation.generated_title,
            generated_description_html=generation.generated_description_html,
            ai_condition_notes=generation.ai_condition_notes,
            suggested_price=generation.suggested_price,
            final_title=generation.final_title,
            final_description_html=generation.final_description_html,
        )
        self._session.add(model)
        # flush, nie commit - transakcją steruje `session_scope` w kontenerze,
        # ale `id` jest potrzebne od razu, żeby wrócić w odpowiedzi API.
        await self._session.flush()
        return self._to_domain(model)

    async def get_by_id(self, generation_id: int) -> OrdlakGeneration | None:
        model = await self._session.get(OrdlakGenerationModel, generation_id)
        return self._to_domain(model) if model else None

    async def get_recent(self, limit: int = 20, offset: int = 0) -> list[OrdlakGeneration]:
        stmt = (
            select(OrdlakGenerationModel)
            .order_by(OrdlakGenerationModel.created_at.desc(), OrdlakGenerationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update_final_texts(
        self, generation_id: int, final_title: str, final_description_html: str
    ) -> OrdlakGeneration | None:
        model = await self._session.get(OrdlakGenerationModel, generation_id)
        if model is None:
            return None
        model.final_title = final_title
        model.final_description_html = final_description_html
        await self._session.flush()
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: OrdlakGenerationModel) -> OrdlakGeneration:
        return OrdlakGeneration(
            id=model.id,
            created_at=model.created_at,
            user_note=model.user_note,
            condition=model.condition,
            purchase_cost=model.purchase_cost,
            inbound_shipping_cost=model.inbound_shipping_cost,
            buyer_shipping_cost=model.buyer_shipping_cost,
            commission_percent=model.commission_percent,
            target_margin_percent=model.target_margin_percent,
            photo_count=model.photo_count,
            generated_title=model.generated_title,
            generated_description_html=model.generated_description_html,
            ai_condition_notes=model.ai_condition_notes,
            suggested_price=model.suggested_price,
            final_title=model.final_title,
            final_description_html=model.final_description_html,
        )

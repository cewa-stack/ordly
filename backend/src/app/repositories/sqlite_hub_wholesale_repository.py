"""Kopia hurtowni z desktopu i zamówienia do hurtowni wysłane z Control Huba."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.hub_wholesale_model import (
    HubWholesaleCatalogModel,
    HubWholesaleOrderModel,
)
from app.domain.wholesale_email import WholesaleCatalog, catalog_from_payload
from app.utils.time import utc_now

_CATALOG_ROW_ID = 1

STATUS_SENDING = "sending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class HubWholesaleOrder:
    """Zamówienie do hurtowni z Huba (wiersz `hub_wholesale_orders`)."""

    request_id: str
    wholesaler_id: str
    wholesaler_name: str
    to_email: str
    subject: str
    items_summary: str
    items_key: str
    test_mode: bool
    status: str
    error: str | None
    sent_at: datetime | None
    created_at: datetime


class SqliteHubWholesaleRepository:
    """Dostęp do `hub_wholesale_catalog` i `hub_wholesale_orders`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---- katalog -----------------------------------------------------------

    async def save_catalog(self, payload: dict[str, Any], version: str) -> None:
        model = await self._session.get(HubWholesaleCatalogModel, _CATALOG_ROW_ID)
        text = json.dumps(payload, ensure_ascii=False)
        if model is None:
            self._session.add(
                HubWholesaleCatalogModel(
                    id=_CATALOG_ROW_ID, payload_json=text, version=version
                )
            )
        else:
            model.payload_json = text
            model.version = version
            model.updated_at = utc_now()
        await self._session.flush()

    async def get_catalog(self) -> tuple[WholesaleCatalog, datetime | None]:
        """Katalog i chwila ostatniej kopii z desktopu (pusty katalog, gdy jeszcze nie przyszła)."""
        model = await self._session.get(HubWholesaleCatalogModel, _CATALOG_ROW_ID)
        if model is None:
            return WholesaleCatalog(), None
        return catalog_from_payload(
            json.loads(model.payload_json), model.version
        ), model.updated_at

    # ---- zamówienia --------------------------------------------------------

    async def get_order(self, request_id: str) -> HubWholesaleOrder | None:
        stmt = select(HubWholesaleOrderModel).where(
            HubWholesaleOrderModel.request_id == request_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def start_order(
        self,
        *,
        request_id: str,
        wholesaler_id: str,
        wholesaler_name: str,
        to_email: str,
        subject: str,
        body: str,
        items_summary: str,
        items_key: str,
        test_mode: bool,
    ) -> None:
        """
        Zapis PRZED wysyłką (status `sending`). Ponowiona po błędzie prośba
        z tym samym `request_id` nadpisuje nieudaną próbę.
        """
        stmt = select(HubWholesaleOrderModel).where(
            HubWholesaleOrderModel.request_id == request_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            model = HubWholesaleOrderModel(request_id=request_id)
            self._session.add(model)
        model.wholesaler_id = wholesaler_id
        model.wholesaler_name = wholesaler_name
        model.to_email = to_email
        model.subject = subject
        model.body = body
        model.items_summary = items_summary
        model.items_key = items_key
        model.test_mode = test_mode
        model.status = STATUS_SENDING
        model.error = None
        model.sent_at = None
        await self._session.flush()

    async def finish_order(self, request_id: str, error: str | None, at: datetime) -> None:
        """Wynik wysyłki; `at` (naiwny UTC) to chwila wysłania - z zegara serwisu."""
        stmt = select(HubWholesaleOrderModel).where(
            HubWholesaleOrderModel.request_id == request_id
        )
        model = (await self._session.execute(stmt)).scalar_one()
        model.status = STATUS_FAILED if error else STATUS_SENT
        model.error = error
        model.sent_at = None if error else at
        await self._session.flush()

    async def last_sent_same(
        self, wholesaler_id: str, items_key: str, test_mode: bool, since: datetime
    ) -> HubWholesaleOrder | None:
        """
        Ostatnie wysłane od `since` zamówienie z tymi samymi pozycjami do tej
        hurtowni, w tym samym trybie (próby testowe nie blokują prawdziwej).
        """
        stmt = (
            select(HubWholesaleOrderModel)
            .where(
                HubWholesaleOrderModel.wholesaler_id == wholesaler_id,
                HubWholesaleOrderModel.items_key == items_key,
                HubWholesaleOrderModel.test_mode == test_mode,
                HubWholesaleOrderModel.status == STATUS_SENT,
                HubWholesaleOrderModel.sent_at >= since,
            )
            .order_by(HubWholesaleOrderModel.sent_at.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_sent(self, limit: int) -> list[HubWholesaleOrder]:
        stmt = (
            select(HubWholesaleOrderModel)
            .where(HubWholesaleOrderModel.status == STATUS_SENT)
            .order_by(HubWholesaleOrderModel.sent_at.desc())
            .limit(limit)
        )
        return [_to_domain(m) for m in (await self._session.execute(stmt)).scalars().all()]


def _to_domain(model: HubWholesaleOrderModel) -> HubWholesaleOrder:
    return HubWholesaleOrder(
        request_id=model.request_id,
        wholesaler_id=model.wholesaler_id,
        wholesaler_name=model.wholesaler_name,
        to_email=model.to_email,
        subject=model.subject,
        items_summary=model.items_summary,
        items_key=model.items_key,
        test_mode=model.test_mode,
        status=model.status,
        error=model.error,
        sent_at=model.sent_at,
        created_at=model.created_at,
    )

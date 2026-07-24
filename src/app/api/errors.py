"""
Mapowanie wyjątków domenowych na odpowiedzi HTTP - jedno miejsce dla
całego TOOM API, żeby endpointy nie powtarzały tych samych bloków
try/except (tak jak dziś robią to handlery Telegrama, gdzie każdy
komunikat jest formatowany osobno na potrzeby czatu).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions.domain_exceptions import (
    DomainError,
    DuplicateInventoryItemError,
    DuplicateOrderError,
    DuplicateReturnError,
    InsufficientStockError,
    InventoryItemNotFoundError,
    MarketplaceUnavailableError,
    OrderNotFoundError,
    ShipmentNotAvailableError,
)

_NOT_FOUND = (OrderNotFoundError, InventoryItemNotFoundError)
_CONFLICT = (DuplicateOrderError, DuplicateReturnError, DuplicateInventoryItemError)
_UNPROCESSABLE = (InsufficientStockError,)
_UNAVAILABLE = (MarketplaceUnavailableError, ShipmentNotAvailableError)


def _status_code_for(exc: DomainError) -> int:
    """Wybiera kod HTTP odpowiadający typowi wyjątku domenowego."""
    if isinstance(exc, _NOT_FOUND):
        return 404
    if isinstance(exc, _CONFLICT):
        return 409
    if isinstance(exc, _UNPROCESSABLE):
        return 422
    if isinstance(exc, _UNAVAILABLE):
        return 503
    return 500


def register_exception_handlers(app: FastAPI) -> None:
    """Rejestruje handlery wyjątków domenowych i walidacyjnych w aplikacji FastAPI."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=_status_code_for(exc), content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _handle_value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

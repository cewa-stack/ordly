"""
Endpointy HTTP /api/v1/ordlak/* - generator ofert Allegro (Ordlak).

Generowanie przyjmuje `multipart/form-data`, bo razem z liczbami leci do
3 zdjęć. Reszta endpointów to zwykły JSON.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    OrdlakFinalizeIn,
    OrdlakGenerationOut,
    OrdlakHistoryItemOut,
    OrdlakStatusOut,
    ordlak_generation_out,
    ordlak_history_item_out,
)
from app.container import Container
from app.services.ordlak_service import (
    MAX_PHOTOS,
    OrdlakError,
    OrdlakNotConfiguredError,
    OrdlakPhoto,
)

router = APIRouter()


@router.get("/ordlak/status", response_model=OrdlakStatusOut)
async def get_ordlak_status(
    container: Annotated[Container, Depends(get_container)],
) -> OrdlakStatusOut:
    """
    Zwraca stan modułu: czy klucz API jest ustawiony i jakie są limity zdjęć.

    Ekran Ordlaka pyta o to przed pokazaniem formularza, żeby od razu
    powiedzieć "brak klucza na Pi" zamiast pozwolić wypełnić cały formularz
    i dopiero wtedy pokazać błąd.
    """
    settings = container.ordlak_settings()
    return OrdlakStatusOut(
        configured=settings.enabled,
        model=settings.model,
        max_photos=MAX_PHOTOS,
        max_photo_size_mb=settings.max_photo_size_mb,
    )


@router.post("/ordlak/generate", response_model=OrdlakGenerationOut)
async def generate_offer(
    container: Annotated[Container, Depends(get_container)],
    note: Annotated[str, Form()],
    condition: Annotated[str, Form()],
    purchase_cost: Annotated[float, Form()],
    commission_percent: Annotated[float, Form()],
    target_margin_percent: Annotated[float, Form()],
    inbound_shipping_cost: Annotated[float, Form()] = 0.0,
    buyer_shipping_cost: Annotated[float, Form()] = 0.0,
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> OrdlakGenerationOut:
    """
    Generuje tytuł, opis i sugerowaną cenę oferty.

    Otwiera własny zakres sesji (jak `POST /orders/sync`), żeby zapis
    generacji był zatwierdzony przed odpowiedzią - inaczej `id` w
    odpowiedzi wskazywałoby na rekord, którego nie ma jeszcze w bazie,
    i kolejny `POST /ordlak/{id}/finalize` dostałby 404.
    """
    uploaded = [photo for photo in (photos or []) if photo.filename]
    if len(uploaded) > MAX_PHOTOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Maksymalnie {MAX_PHOTOS} zdjęcia na jedną generację.",
        )

    loaded_photos = [
        OrdlakPhoto(
            media_type=(photo.content_type or "application/octet-stream").lower(),
            content=await photo.read(),
        )
        for photo in uploaded
    ]

    async with container.session_scope() as session:
        service = container.ordlak_service(session)
        try:
            draft = await service.generate(
                note=note,
                condition=condition,
                purchase_cost=purchase_cost,
                inbound_shipping_cost=inbound_shipping_cost,
                buyer_shipping_cost=buyer_shipping_cost,
                commission_percent=commission_percent,
                target_margin_percent=target_margin_percent,
                photos=loaded_photos,
            )
        except OrdlakNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except OrdlakError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

    return ordlak_generation_out(draft)


@router.get("/ordlak/history", response_model=list[OrdlakHistoryItemOut])
async def get_ordlak_history(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrdlakHistoryItemOut]:
    """Zwraca historię wygenerowanych ofert, najnowsze pierwsze."""
    service = container.ordlak_service(session)
    generations = await service.history(limit=limit, offset=offset)
    return [ordlak_history_item_out(g) for g in generations]


@router.post("/ordlak/{generation_id}/finalize", response_model=OrdlakHistoryItemOut)
async def finalize_offer(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    generation_id: int,
    payload: OrdlakFinalizeIn,
) -> OrdlakHistoryItemOut:
    """Zapisuje ręcznie poprawiony tytuł i opis do historii."""
    service = container.ordlak_service(session)
    updated = await service.finalize(
        generation_id, payload.final_title, payload.final_description_html
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generacja o id {generation_id} nie istnieje.",
        )
    return ordlak_history_item_out(updated)

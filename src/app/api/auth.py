"""
Autoryzacja TOOM API - pojedynczy token dla jedynego użytkownika.

Odpowiednik `AdminOnlyMiddleware` z bota Telegram: TOOM jest osobistym
asystentem jednej osoby, więc API nie ma kont ani ról - jeden długożyjący
token, wygenerowany raz i wklejony w aplikacji mobilnej, wystarcza.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

_BEARER_PREFIX = "Bearer "


async def require_api_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """
    Weryfikuje nagłówek `Authorization: Bearer <token>` względem
    `TOOM_API_TOKEN` skonfigurowanego w `.env`.

    Używa `hmac.compare_digest`, aby porównanie tokena było odporne na
    ataki czasowe (timing attack) - zwykłe `==` na stringach nie daje
    takiej gwarancji.

    Raises:
        HTTPException: 401, gdy nagłówek brakuje, ma zły format lub token
            się nie zgadza.
    """
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak tokena autoryzacji (nagłówek Authorization: Bearer <token>)",
        )

    provided_token = authorization.removeprefix(_BEARER_PREFIX).strip()
    expected_token = get_settings().api.api_token.get_secret_value()

    if not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy token autoryzacji",
        )

"""
Endpoint HTTP /api/v1/auth/login - login+hasło jako brama do `api_token`.

ORDLY API pozostaje jednotokenowe (`require_api_token`, patrz
`app/api/auth.py`) - ten endpoint niczego w tym nie zmienia, tylko dodaje
przyjazny dla człowieka sposób na zdobycie tokena z aplikacji mobilnej
zamiast ręcznego wklejania długiego ciągu znaków. Endpoint musi być
zarejestrowany w `router.py` BEZ `Depends(require_api_token)` - to jedyne
miejsce w ORDLY API, do którego telefon łączy się bez tokena.

Prosta blokada po nieudanych próbach chroni domyślne poświadczenia
(`admin`/`admin`) przed automatycznym zgadywaniem w sieci Tailscale/LAN -
stan trzymany w pamięci procesu wystarcza, bo API działa jako pojedynczy
proces uvicorn (patrz `app/main.py`).
"""

from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from app.api.schemas import LoginIn, LoginOut
from app.core.config import get_settings

router = APIRouter()

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60.0
_failed_attempts: dict[str, tuple[int, float]] = {}


def _client_key(request: Request) -> str:
    """Adres klienta jako klucz licznika prób - wystarcza dla sieci domowej/Tailscale."""
    return request.client.host if request.client else "unknown"


def _is_locked_out(key: str) -> bool:
    count, locked_until = _failed_attempts.get(key, (0, 0.0))
    return count >= _MAX_ATTEMPTS and time.monotonic() < locked_until


def _register_failure(key: str) -> None:
    count, _ = _failed_attempts.get(key, (0, 0.0))
    count += 1
    locked_until = time.monotonic() + _LOCKOUT_SECONDS if count >= _MAX_ATTEMPTS else 0.0
    _failed_attempts[key] = (count, locked_until)


def _clear_failures(key: str) -> None:
    _failed_attempts.pop(key, None)


@router.post("/auth/login", response_model=LoginOut)
async def login(request: Request, payload: LoginIn) -> LoginOut:
    """
    Weryfikuje login+hasło (`ORDLY_ADMIN_USERNAME`/`ORDLY_ADMIN_PASSWORD`
    z `.env`) i zwraca `ORDLY_API_TOKEN` używany do wszystkich pozostałych
    wywołań ORDLY API.
    """
    key = _client_key(request)
    if _is_locked_out(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Zbyt wiele nieudanych prób logowania. "
                f"Spróbuj ponownie za {int(_LOCKOUT_SECONDS)} sekund."
            ),
        )

    settings = get_settings().api
    # `hmac.compare_digest` na stringach akceptuje wyłącznie znaki ASCII
    # (rzuca TypeError na "ą", "ł", "ę" itd.) - login i hasło kodujemy do
    # UTF-8 i porównujemy bajty, żeby polskie znaki w haśle działały.
    username_ok = hmac.compare_digest(
        payload.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    password_ok = hmac.compare_digest(
        payload.password.encode("utf-8"),
        settings.admin_password.get_secret_value().encode("utf-8"),
    )

    if not (username_ok and password_ok):
        _register_failure(key)
        logger.warning("Nieudana próba logowania do ORDLY API (login={})", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło",
        )

    _clear_failures(key)
    return LoginOut(token=settings.api_token.get_secret_value())

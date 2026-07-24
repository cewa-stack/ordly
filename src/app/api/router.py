"""
Agregacja wszystkich routerów FastAPI w jeden router aplikacji.

TOOM API dla aplikacji mobilnej żyje pod prefiksem `/api/v1` i wymaga
tokena (`require_api_token`) na każdym endpointzie poza `/api/v1/health` -
zdrowie API musi być sprawdzalne z ekranu logowania w apce, zanim
użytkownik w ogóle wklei token.

Istniejące endpointy `/health` i `/backup/trigger` (bez prefiksu) zostają
bez zmian - są używane lokalnie (monitoring, backup) od czasu, zanim
powstało TOOM API, i nie są częścią kontraktu aplikacji mobilnej
(zob. docs/01_app.md, sekcja 5).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_api_token
from app.api.endpoints import (
    backup,
    dashboard,
    health,
    logs,
    orders,
    push,
    stats,
    stock,
)

api_router = APIRouter()

# Endpointy historyczne (bez prefiksu, bez tokena) - zachowane dla zgodności.
api_router.include_router(health.router, tags=["health"])
api_router.include_router(backup.router, tags=["backup"])

# TOOM API (aplikacja mobilna) - wersjonowane, zabezpieczone tokenem.
mobile_api_router = APIRouter(prefix="/api/v1")
mobile_api_router.include_router(health.router, tags=["mobile-health"])
mobile_api_router.include_router(
    dashboard.router, tags=["mobile-dashboard"], dependencies=[Depends(require_api_token)]
)
mobile_api_router.include_router(
    orders.router, tags=["mobile-orders"], dependencies=[Depends(require_api_token)]
)
mobile_api_router.include_router(
    stock.router, tags=["mobile-stock"], dependencies=[Depends(require_api_token)]
)
mobile_api_router.include_router(
    stats.router, tags=["mobile-stats"], dependencies=[Depends(require_api_token)]
)
mobile_api_router.include_router(
    logs.router, tags=["mobile-logs"], dependencies=[Depends(require_api_token)]
)
mobile_api_router.include_router(
    push.router, tags=["mobile-push"], dependencies=[Depends(require_api_token)]
)

api_router.include_router(mobile_api_router)

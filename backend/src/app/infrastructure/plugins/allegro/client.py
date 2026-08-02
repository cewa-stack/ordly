"""
Niskopoziomowy klient HTTP do komunikacji z api.allegro.pl.

Ten klient NIE zna encji domenowych - zwraca surowe słowniki JSON.
Mapowanie na encje domenowe odbywa się w mapper.py.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError

_ALLEGRO_ACCEPT_HEADER = "application/vnd.allegro.public.v1+json"


class AllegroApiClient:
    """Klient HTTP do wykonywania autoryzowanych zapytań do Allegro REST API."""

    def __init__(self, config: AllegroConfig) -> None:
        self._config = config

    async def get(
        self,
        path: str,
        access_token: str,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> dict[str, Any]:
        """Wykonuje żądanie GET do Allegro API i zwraca sparsowany JSON."""
        return await self._request("GET", path, access_token, params=params, accept=accept)

    async def post(
        self,
        path: str,
        access_token: str,
        json_body: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> dict[str, Any]:
        """Wykonuje żądanie POST do Allegro API i zwraca sparsowany JSON."""
        return await self._request(
            "POST", path, access_token, json_body=json_body, accept=accept
        )

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> dict[str, Any]:
        """
        Wspólna implementacja żądań HTTP z obsługą błędów sieciowych i API.

        Args:
            method: Metoda HTTP (GET, POST).
            path: Ścieżka względna endpointu.
            access_token: Ważny access token.
            params: Opcjonalne parametry query string.
            json_body: Opcjonalne ciało żądania JSON.
            accept: Nagłówek Accept - domyślnie `public.v1`. Zasoby
                beta (np. `/sale/issues`) wymagają jawnego
                `application/vnd.allegro.beta.v1+json`.

        Returns:
            Odpowiedź API zdekodowana z JSON.

        Raises:
            AllegroApiError: Gdy Allegro zwróci kod błędu HTTP.
        """
        url = f"{self._config.base_api_url}{path}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": accept or _ALLEGRO_ACCEPT_HEADER,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method, url, headers=headers, params=params, json=json_body
                )
            except httpx.RequestError as exc:
                logger.error("Błąd sieci przy zapytaniu do Allegro: {}", exc)
                raise AllegroApiError(0, f"Błąd sieci: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "Allegro API zwróciło błąd {} dla {} {}: {}",
                response.status_code,
                method,
                path,
                response.text,
            )
            raise AllegroApiError(response.status_code, response.text)

        return response.json()

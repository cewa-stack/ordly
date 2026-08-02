"""
Obsługa OAuth2 Authorization Code + PKCE dla Allegro.

Ten moduł odpowiada za:
1. Wygenerowanie pary code_verifier/code_challenge.
2. Zbudowanie URL autoryzacji do otwarcia w przeglądarce.
3. Uruchomienie lokalnego serwera HTTP przechwytującego redirect.
4. Wymianę kodu autoryzacyjnego na tokeny.
5. Odświeżanie tokenu przy użyciu refresh_token.
6. Szyfrowanie/deszyfrowanie tokenów przed zapisem w bazie.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from app.domain.exceptions.domain_exceptions import AuthenticationError
from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.utils.time import utc_now


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Para tokenów OAuth2 wraz z czasem wygaśnięcia access tokenu."""

    access_token: str
    refresh_token: str
    expires_at: datetime


class PkcePair:
    """
    Generuje i przechowuje parę code_verifier / code_challenge (PKCE)
    oraz losowy parametr `state` chroniący przed atakiem CSRF na
    lokalny redirect.
    """

    def __init__(self) -> None:
        self.verifier: str = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        self.challenge: str = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        self.state: str = secrets.token_urlsafe(32)


class TokenEncryptor:
    """
    Szyfruje i deszyfruje tokeny OAuth2 przed zapisem/odczytem z bazy.

    Używa Fernet (symetryczne szyfrowanie AES128 w trybie CBC + HMAC),
    kluczem pochodzącym wyłącznie z .env - nigdy z bazy danych.
    """

    def __init__(self, encryption_key: str) -> None:
        try:
            self._fernet = Fernet(encryption_key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise AuthenticationError(
                "ALLEGRO_TOKEN_ENCRYPTION_KEY jest niepoprawny - musi być "
                "32-bajtowym kluczem zakodowanym w base64 (użyj "
                "Fernet.generate_key() do wygenerowania)"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        """Szyfruje wartość tekstową do postaci bezpiecznej do zapisu w bazie."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Deszyfruje wartość zapisaną wcześniej metodą encrypt()."""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AuthenticationError(
                "Nie udało się odszyfrować tokenu - klucz szyfrujący mógł "
                "się zmienić od czasu zapisu tokenu"
            ) from exc


class AllegroOAuthClient:
    """Realizuje pełny przepływ OAuth2 Authorization Code + PKCE dla Allegro."""

    def __init__(self, config: AllegroConfig) -> None:
        self._config = config

    def build_authorization_url(self, pkce: PkcePair) -> str:
        """Buduje URL, który użytkownik musi otworzyć w przeglądarce."""
        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": pkce.challenge,
            "state": pkce.state,
        }
        return f"{self._config.auth_base_url}/auth/oauth/authorize?{urlencode(params)}"

    async def wait_for_authorization_code(
        self, pkce: PkcePair, timeout_seconds: int = 300
    ) -> str:
        """
        Uruchamia lokalny serwer HTTP i czeka na przekierowanie z kodem.

        Args:
            pkce: Para PKCE użyta do budowy URL autoryzacji - jej `state`
                musi się zgadzać z parametrem `state` w przekierowaniu.
            timeout_seconds: Maksymalny czas oczekiwania na zatwierdzenie
                autoryzacji przez użytkownika w przeglądarce.

        Returns:
            Kod autoryzacyjny otrzymany od Allegro.

        Raises:
            AuthenticationError: Gdy upłynie limit czasu bez otrzymania kodu.
        """
        parsed = urlparse(self._config.redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 80

        code_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        async def handle_client(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            """Obsługuje pojedyncze żądanie HTTP przekierowania."""
            request_line = await reader.readline()
            request_text = request_line.decode("utf-8", errors="ignore")

            code: str | None = None
            request_parts = request_text.split(" ")
            if len(request_parts) >= 2:
                query_params = parse_qs(urlparse(request_parts[1]).query)
                received_code = query_params.get("code", [None])[0]
                received_state = query_params.get("state", [None])[0]
                if received_code and secrets.compare_digest(received_state or "", pkce.state):
                    code = received_code
                elif received_code:
                    logger.warning(
                        "Odrzucono przekierowanie OAuth z niepoprawnym parametrem state"
                    )

            response_body = (
                "<html><body><h2>Autoryzacja zakonczona. "
                "Mozesz zamknac to okno.</h2></body></html>"
            )
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode("utf-8"))
            await writer.drain()
            writer.close()

            if code and not code_future.done():
                code_future.set_result(code)

        server = await asyncio.start_server(handle_client, host=host, port=port)
        logger.info("Oczekiwanie na autoryzację Allegro na {}:{}", host, port)

        try:
            async with server:
                return await asyncio.wait_for(code_future, timeout=timeout_seconds)
        except TimeoutError as exc:
            raise AuthenticationError(
                f"Przekroczono limit czasu ({timeout_seconds}s) oczekiwania "
                "na autoryzację użytkownika w przeglądarce"
            ) from exc

    async def exchange_code_for_tokens(self, code: str, pkce: PkcePair) -> TokenPair:
        """Wymienia kod autoryzacyjny na parę tokenów access/refresh."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._config.redirect_uri,
            "code_verifier": pkce.verifier,
        }
        return await self._request_token(payload)

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Wymienia refresh_token na nowy access_token (i zwykle nowy refresh_token)."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self._config.redirect_uri,
        }
        return await self._request_token(payload)

    async def _request_token(self, payload: dict[str, str]) -> TokenPair:
        """Wykonuje żądanie POST do endpointu tokenowego Allegro."""
        auth = (self._config.client_id, self._config.client_secret.get_secret_value())
        url = f"{self._config.auth_base_url}/auth/oauth/token"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, data=payload, auth=auth)
            except httpx.RequestError as exc:
                raise AuthenticationError(
                    f"Błąd sieci podczas komunikacji z serwerem autoryzacji Allegro: {exc}"
                ) from exc

        if response.status_code != 200:
            raise AllegroApiError(response.status_code, response.text)

        data = response.json()
        expires_at = utc_now() + timedelta(seconds=data["expires_in"])
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )

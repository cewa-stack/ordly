"""
Konfiguracja specyficzna dla pluginu Allegro.

Trzymanie jej wewnątrz folderu pluginu jest zgodne z zasadą, że
każdy plugin ma własną, w pełni odizolowaną konfigurację.
"""

from __future__ import annotations

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AllegroConfig(BaseSettings):
    """Ustawienia OAuth2 + PKCE oraz adresów API dla Allegro."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    client_id: str = Field(..., alias="ALLEGRO_CLIENT_ID")
    client_secret: SecretStr = Field(..., alias="ALLEGRO_CLIENT_SECRET")
    environment: str = Field(default="production", alias="ALLEGRO_ENVIRONMENT")
    redirect_uri: str = Field(
        default="http://localhost:53682/auth/callback",
        alias="ALLEGRO_REDIRECT_URI",
    )
    token_encryption_key: SecretStr = Field(..., alias="ALLEGRO_TOKEN_ENCRYPTION_KEY")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Waliduje wartość środowiska Allegro."""
        allowed = {"production", "sandbox"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"environment musi być jednym z {allowed}")
        return normalized

    @property
    def base_api_url(self) -> str:
        """Bazowy URL REST API Allegro, zależny od środowiska."""
        if self.environment == "sandbox":
            return "https://api.allegro.pl.allegrosandbox.pl"
        return "https://api.allegro.pl"

    @property
    def auth_base_url(self) -> str:
        """Bazowy URL serwera autoryzacji Allegro, zależny od środowiska."""
        if self.environment == "sandbox":
            return "https://allegro.pl.allegrosandbox.pl"
        return "https://allegro.pl"

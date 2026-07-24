"""
Centralny moduł konfiguracji aplikacji.

Wszystkie zmienne środowiskowe są ładowane, walidowane i typowane
wyłącznie w tym miejscu. Żaden inny moduł nie powinien odczytywać
`os.environ` bezpośrednio - to gwarantuje jedno źródło prawdy
oraz fail-fast przy starcie aplikacji (brak wymaganej zmiennej
powoduje błąd walidacji natychmiast, a nie w trakcie działania).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Ogólne ustawienia środowiska aplikacji."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="production", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Waliduje, że poziom logowania jest jednym z akceptowanych przez Loguru."""
        allowed = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(
                f"log_level musi być jednym z {allowed}, otrzymano: {value}"
            )
        return normalized


class MarketplaceSettings(BaseSettings):
    """
    Ustawienia wyboru aktywnego pluginu marketplace.

    Ta klasa celowo NIE zawiera żadnych ustawień specyficznych
    dla Allegro czy innego marketplace - tylko wybór, KTÓRY plugin
    ma zostać załadowany.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    marketplace_provider: str = Field(..., alias="MARKETPLACE_PROVIDER")


class AllegroSettings(BaseSettings):
    """
    Konfiguracja specyficzna dla pluginu Allegro (OAuth2 + PKCE).

    Docelowa konfiguracja pluginu żyje w
    infrastructure/plugins/allegro/config.py (AllegroConfig) - ta klasa
    jest zachowana dla spójności agregatora Settings.
    """

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
    token_encryption_key: SecretStr = Field(
        ..., alias="ALLEGRO_TOKEN_ENCRYPTION_KEY"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Waliduje, że środowisko Allegro to production lub sandbox."""
        allowed = {"production", "sandbox"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(
                f"environment musi być jednym z {allowed}, otrzymano: {value}"
            )
        return normalized

    @property
    def base_api_url(self) -> str:
        """Zwraca właściwy adres bazowy API Allegro w zależności od środowiska."""
        if self.environment == "sandbox":
            return "https://api.allegro.pl.allegrosandbox.pl"
        return "https://api.allegro.pl"

    @property
    def auth_url(self) -> str:
        """Zwraca właściwy adres bazowy serwera autoryzacji Allegro."""
        if self.environment == "sandbox":
            return "https://allegro.pl.allegrosandbox.pl/auth/oauth"
        return "https://allegro.pl/auth/oauth"


class TelegramSettings(BaseSettings):
    """Konfiguracja bota Telegram (aiogram) - TOOM."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr = Field(..., alias="TELEGRAM_BOT_TOKEN")
    admin_chat_id: int = Field(..., alias="TELEGRAM_ADMIN_CHAT_ID")


class DatabaseSettings(BaseSettings):
    """Konfiguracja połączenia z bazą danych SQLite."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/toom.db",
        alias="DATABASE_URL",
    )
    echo: bool = Field(default=False, alias="DATABASE_ECHO")

    @field_validator("database_url")
    @classmethod
    def ensure_data_directory_exists(cls, value: str) -> str:
        """
        Upewnia się, że katalog docelowy pliku SQLite istnieje.

        Zapobiega to błędom przy pierwszym uruchomieniu na czystym
        systemie (Raspberry Pi), gdzie folder `data/` może jeszcze
        nie istnieć.
        """
        if value.startswith("sqlite"):
            path_part = value.split("///")[-1]
            db_path = Path(path_part)
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return value


class SchedulerSettings(BaseSettings):
    """Konfiguracja harmonogramu zadań (APScheduler)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sync_orders_interval_seconds: int = Field(
        default=60, alias="SYNC_ORDERS_INTERVAL_SECONDS", ge=10
    )


class BackupSettings(BaseSettings):
    """Konfiguracja mechanizmu kopii zapasowych bazy danych."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backup_directory: Path = Field(
        default=Path("./backups"), alias="BACKUP_DIRECTORY"
    )
    retention_days: int = Field(default=30, alias="BACKUP_RETENTION_DAYS", ge=1)

    @field_validator("backup_directory")
    @classmethod
    def ensure_backup_directory_exists(cls, value: Path) -> Path:
        """Tworzy katalog backupów, jeśli jeszcze nie istnieje."""
        value.mkdir(parents=True, exist_ok=True)
        return value


class SmsSettings(BaseSettings):
    """
    Konfiguracja bramki SMS wysyłającej powiadomienia do klientów.

    Domyślnie aktywny jest dostawca 'logging' (tryb testowy) - loguje
    treść SMS zamiast realnej wysyłki. Podpięcie realnego operatora
    sprowadza się do nowej implementacji SmsProvider i zmiany SMS_PROVIDER.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: str = Field(default="logging", alias="SMS_PROVIDER")
    sender_name: str = Field(default="TOOM", alias="SMS_SENDER_NAME")


class ApiSettings(BaseSettings):
    """
    Konfiguracja TOOM API - warstwy REST używanej przez aplikację mobilną
    TOOM Mobile (obok istniejącego bota Telegram).

    `host` domyślnie nasłuchuje na wszystkich interfejsach (0.0.0.0), a nie
    tylko na loopback - inaczej telefon nie połączy się z API nawet przez
    Tailscale. Bezpieczeństwo w tym modelu zapewnia sieć (Tailscale/LAN,
    patrz docs/01_app.md §4) oraz `api_token`, nie ograniczenie do
    loopback.

    `web_app_dist_path`, gdy ustawiona, wskazuje folder ze zbudowaną
    wersją TOOM Mobile (`npx expo export -p web` w `mobile/`) - backend
    serwuje go pod `/`, żeby telefon mógł otworzyć całą aplikację z
    tego samego adresu co API (jeden proces, jeden port, jeden wpis
    `tailscale serve` - patrz docs/01_app.md §6.5). Brak wartości (domyślnie)
    oznacza, że backend serwuje wyłącznie API - tak jak dotychczas.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_token: SecretStr = Field(..., alias="TOOM_API_TOKEN")
    host: str = Field(default="0.0.0.0", alias="TOOM_API_HOST")  # noqa: S104
    port: int = Field(default=8000, alias="TOOM_API_PORT")
    web_app_dist_path: Path | None = Field(default=None, alias="WEB_APP_DIST_PATH")


class WebPushSettings(BaseSettings):
    """
    Konfiguracja drugiego (opcjonalnego) kanału powiadomień - Web Push do
    TOOM Mobile uruchomionego jako PWA na iPhonie (obok bota Telegram).

    Klucze VAPID generuje się raz, poleceniem opisanym w
    `docs/01_app.md` (sekcja Web Push) - `webpush_enabled=False` (brak
    kluczy) oznacza, że `WebPushNotifier` nie robi nic, a jedynym kanałem
    powiadomień pozostaje Telegram.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vapid_public_key: str = Field(default="", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: SecretStr = Field(default=SecretStr(""), alias="VAPID_PRIVATE_KEY")
    vapid_claim_email: str = Field(
        default="mailto:admin@example.com", alias="VAPID_CLAIM_EMAIL"
    )

    @property
    def enabled(self) -> bool:
        """Web Push jest aktywny tylko, gdy oba klucze VAPID są ustawione."""
        return bool(self.vapid_public_key) and bool(
            self.vapid_private_key.get_secret_value()
        )


class LoggingSettings(BaseSettings):
    """Konfiguracja logowania (Loguru)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_directory: Path = Field(default=Path("./logs"), alias="LOG_DIRECTORY")
    rotation: str = Field(default="10 MB", alias="LOG_ROTATION")
    retention_days: int = Field(default=14, alias="LOG_RETENTION_DAYS", ge=1)

    @field_validator("log_directory")
    @classmethod
    def ensure_log_directory_exists(cls, value: Path) -> Path:
        """Tworzy katalog logów, jeśli jeszcze nie istnieje."""
        value.mkdir(parents=True, exist_ok=True)
        return value


class Settings:
    """
    Agregator wszystkich grup ustawień aplikacji.

    Ta klasa NIE dziedziczy po BaseSettings - jest kompozycją
    (composition) mniejszych klas Settings, każda odpowiedzialna
    za jeden spójny obszar konfiguracji (Single Responsibility
    Principle).
    """

    def __init__(self) -> None:
        self.app = AppSettings()
        self.marketplace = MarketplaceSettings()
        self.allegro = AllegroSettings()
        self.telegram = TelegramSettings()
        self.database = DatabaseSettings()
        self.scheduler = SchedulerSettings()
        self.backup = BackupSettings()
        self.sms = SmsSettings()
        self.logging = LoggingSettings()
        self.api = ApiSettings()
        self.web_push = WebPushSettings()


@lru_cache
def get_settings() -> Settings:
    """
    Zwraca singleton ustawień aplikacji.

    Używamy `lru_cache` zamiast globalnej zmiennej modułowej,
    ponieważ:
    1. Jest to jawne i łatwe do zresetowania w testach
       (`get_settings.cache_clear()`).
    2. Pozwala na łatwe podmienienie w Dependency Injection.
    3. Unika problemów z kolejnością importów.
    """
    return Settings()

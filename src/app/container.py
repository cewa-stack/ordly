"""
Kontener Dependency Injection - jedyne miejsce, gdzie tworzone są
konkretne implementacje (SQLite, Allegro, Telegram) i wstrzykiwane
w abstrakcje, których oczekują serwisy i handlery.

Celowo NIE używamy zewnętrznej biblioteki DI - prosty ręczny
kontener w pełni wystarcza dla skali tego projektu.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.event_bus.bus import EventBus
from app.database.engine import create_engine, create_session_factory
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.sms_provider import SmsProvider
from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.plugin import AllegroPlugin
from app.infrastructure.sms.logging_sms_provider import LoggingSmsProvider
from app.infrastructure.telegram.telegram_notifier import TelegramNotifier
from app.repositories.sqlite_event_repository import SqliteEventRepository
from app.repositories.sqlite_inventory_repository import SqliteInventoryRepository
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository
from app.repositories.sqlite_shipment_repository import SqliteShipmentRepository
from app.repositories.sqlite_sms_history_repository import SqliteSmsHistoryRepository
from app.repositories.sqlite_stock_sync_repository import SqliteStockSyncRepository
from app.repositories.sqlite_telegram_message_repository import (
    SqliteTelegramMessageRepository,
)
from app.repositories.sqlite_token_store import SqliteTokenStore
from app.services.backup_service import BackupService
from app.services.component_resolver import ComponentResolver
from app.services.events_service import EventsService
from app.services.health_service import HealthService, SyncStatus
from app.services.inventory_service import InventoryService
from app.services.search_service import SearchService
from app.services.shipping_reminder_service import ShippingReminderService
from app.services.sms_service import SmsService
from app.services.stats_service import StatsService
from app.services.stock_sync_service import StockSyncService
from app.services.sync_orders_service import SyncOrdersService
from app.services.telegram_cleanup_service import TelegramCleanupService
from app.services.tracking_service import TrackingService


class Container:
    """
    Centralny punkt składania zależności aplikacji.

    Metody zwracające serwisy (np. orders_service()) tworzą nową
    instancję repozytorium powiązaną z bieżącą sesją bazy danych -
    sesja jest tworzona per operacja, nigdy dzielona globalnie.
    """

    def __init__(self, settings: Settings, bot: Bot) -> None:
        """
        Buduje kontener na podstawie konfiguracji i gotowej instancji bota.

        Args:
            settings: Zwalidowana konfiguracja aplikacji.
            bot: Instancja bota aiogram (TOOM).
        """
        self._settings = settings
        self._bot = bot
        self._engine: AsyncEngine = create_engine(settings.database)
        self._session_factory: async_sessionmaker[AsyncSession] = (
            create_session_factory(self._engine)
        )
        self.event_bus = EventBus()
        self.sync_status = SyncStatus()

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession]:
        """
        Context manager dostarczający sesję z automatycznym commit/rollback.
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def build_plugin(self, session: AsyncSession) -> MarketplacePlugin:
        """
        Tworzy instancję aktywnego pluginu marketplace na podstawie konfiguracji.

        Dzisiaj zawsze zwraca AllegroPlugin (MARKETPLACE_PROVIDER=allegro).
        """
        allegro_config = AllegroConfig()
        token_store = SqliteTokenStore(session)
        return AllegroPlugin(config=allegro_config, token_store=token_store)

    def orders_service(self, session: AsyncSession) -> SyncOrdersService:
        """Buduje SyncOrdersService (używany też przez /orders i /order)."""
        order_repository = SqliteOrderRepository(session)
        return_repository = SqliteReturnRepository(session)
        plugin = self.build_plugin(session)
        return SyncOrdersService(
            plugin, order_repository, self.event_bus, return_repository
        )

    def sync_orders_service(self, session: AsyncSession) -> SyncOrdersService:
        """Alias semantyczny używany przez komendę /sync i scheduler."""
        return self.orders_service(session)

    def tracking_service(self, session: AsyncSession) -> TrackingService:
        """Buduje TrackingService dla komendy /tracking."""
        order_repository = SqliteOrderRepository(session)
        shipment_repository = SqliteShipmentRepository(session)
        plugin = self.build_plugin(session)
        return TrackingService(plugin, order_repository, shipment_repository)

    def stats_service(self, session: AsyncSession) -> StatsService:
        """Buduje StatsService dla komendy /stats."""
        return StatsService(SqliteOrderRepository(session))

    def search_service(self, session: AsyncSession) -> SearchService:
        """Buduje SearchService dla komendy /search."""
        return SearchService(SqliteOrderRepository(session))

    def events_service(self, session: AsyncSession) -> EventsService:
        """Buduje EventsService dla komendy /logs."""
        return EventsService(SqliteEventRepository(session))

    def health_service(self, session: AsyncSession) -> HealthService:
        """
        Buduje HealthService powiązany z bieżącą sesją.

        Znacznik czasu ostatniej synchronizacji żyje w self.sync_status
        (współdzielony przez cały czas działania aplikacji), więc sam
        HealthService może być bezpiecznie tworzony per żądanie.
        """
        plugin = self.build_plugin(session)
        return HealthService(session, plugin, self.sync_status)

    def backup_service(self, session: AsyncSession) -> BackupService:
        """Buduje BackupService dla ręcznego (API) lub zaplanowanego backupu."""
        return BackupService(
            session=session,
            backup_directory=self._settings.backup.backup_directory,
            retention_days=self._settings.backup.retention_days,
            event_bus=self.event_bus,
        )

    def inventory_service(self, session: AsyncSession) -> InventoryService:
        """Buduje InventoryService dla komend /stock."""
        return InventoryService(SqliteInventoryRepository(session))

    def stock_sync_service(self, session: AsyncSession) -> StockSyncService:
        """Buduje StockSyncService dla automatycznej synchronizacji stanów."""
        inventory_repository = SqliteInventoryRepository(session)
        return StockSyncService(
            inventory_repository=inventory_repository,
            stock_sync_repository=SqliteStockSyncRepository(session),
            component_resolver=ComponentResolver(inventory_repository),
        )

    def _build_sms_provider(self) -> SmsProvider:
        """
        Buduje bramkę SMS wskazaną w konfiguracji (SMS_PROVIDER).

        Domyślnie 'logging' (tryb testowy). Kolejne bramki dodaje się tutaj,
        rejestrując nową implementację SmsProvider - reszta systemu bez zmian.
        """
        provider_code = self._settings.sms.provider.lower()
        if provider_code == "logging":
            return LoggingSmsProvider(sender_name=self._settings.sms.sender_name)
        raise ValueError(f"Nieobsługiwany dostawca SMS: {provider_code}")

    def sms_service(self, session: AsyncSession) -> SmsService:
        """Buduje SmsService dla subskrybenta zdarzenia OrderPackingStarted."""
        return SmsService(
            provider=self._build_sms_provider(),
            history_repository=SqliteSmsHistoryRepository(session),
        )

    def shipping_reminder_service(
        self, session: AsyncSession
    ) -> ShippingReminderService:
        """Buduje ShippingReminderService dla przypomnienia o 20:00."""
        return ShippingReminderService(SqliteOrderRepository(session))

    def telegram_message_repository(
        self, session: AsyncSession
    ) -> SqliteTelegramMessageRepository:
        """Buduje repozytorium zapisanych wiadomości Telegram (nocne czyszczenie)."""
        return SqliteTelegramMessageRepository(session)

    def telegram_cleanup_service(
        self, session: AsyncSession
    ) -> TelegramCleanupService:
        """Buduje TelegramCleanupService dla nocnego czyszczenia czatu (02:00)."""
        return TelegramCleanupService(
            bot=self._bot,
            admin_chat_id=self._settings.telegram.admin_chat_id,
            order_repository=SqliteOrderRepository(session),
            message_repository=SqliteTelegramMessageRepository(session),
            notifier=self.notifier(),
        )

    def notifier(self) -> TelegramNotifier:
        """Buduje TelegramNotifier (bot TOOM) używany przez subskrybenta OrderCreated."""
        return TelegramNotifier(
            bot=self._bot, admin_chat_id=self._settings.telegram.admin_chat_id
        )

    async def dispose(self) -> None:
        """Zamyka silnik bazy danych - wywoływane przy zamykaniu aplikacji."""
        await self._engine.dispose()

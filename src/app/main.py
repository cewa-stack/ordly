"""
Punkt wejścia aplikacji TOOM.

Spina wszystkie moduły: konfigurację, logowanie, kontener DI, bota
Telegram, scheduler i API HTTP - i uruchamia je współbieżnie w jednym
procesie asyncio. Obsługuje graceful shutdown przy SIGTERM/SIGINT
(wysyłanym przez systemd przy zatrzymaniu).
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

import uvicorn
from aiogram import Dispatcher
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.bot.bot_instance import create_bot, create_dispatcher
from app.bot.handlers import (
    health as health_handler,
)
from app.bot.handlers import (
    help as help_handler,
)
from app.bot.handlers import (
    logs as logs_handler,
)
from app.bot.handlers import (
    orders as orders_handler,
)
from app.bot.handlers import (
    search as search_handler,
)
from app.bot.handlers import (
    start as start_handler,
)
from app.bot.handlers import (
    stats as stats_handler,
)
from app.bot.handlers import (
    stock as stock_handler,
)
from app.bot.handlers import (
    sync as sync_handler,
)
from app.bot.handlers import (
    tracking as tracking_handler,
)
from app.bot.middlewares.auth_middleware import AdminOnlyMiddleware
from app.bot.middlewares.di_middleware import ContainerMiddleware
from app.bot.middlewares.message_tracking_middleware import MessageTrackingMiddleware
from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.event_subscriptions import register_event_subscriptions
from app.scheduler.jobs.backup_job import run_backup_job
from app.scheduler.jobs.shipping_reminder_job import run_shipping_reminder_job
from app.scheduler.jobs.sync_orders_job import run_sync_orders_job
from app.scheduler.jobs.telegram_cleanup_job import run_telegram_cleanup_job
from app.scheduler.scheduler_setup import (
    create_scheduler,
    register_backup_job,
    register_shipping_reminder_job,
    register_sync_orders_job,
    register_telegram_cleanup_job,
)


def _register_bot_routers(dispatcher: Dispatcher) -> None:
    """Rejestruje wszystkie routery handlerów komend w dispatcherze."""
    for module in (
        start_handler,
        help_handler,
        orders_handler,
        tracking_handler,
        search_handler,
        stats_handler,
        stock_handler,
        health_handler,
        sync_handler,
        logs_handler,
    ):
        dispatcher.include_router(module.router)


def _create_fastapi_app(container: Container, settings: Settings) -> FastAPI:
    """Tworzy instancję FastAPI z podłączonym kontenerem DI w stanie aplikacji."""
    app = FastAPI(title="TOOM API", docs_url="/docs")
    app.state.container = container
    # TOOM Mobile uruchomiony jako PWA w przeglądarce woła to API z innego
    # originu (inny port niż backend) - bez CORS przeglądarka blokuje odczyt
    # odpowiedzi dla każdego zapytania z nagłówkiem Authorization (preflight).
    # Bezpieczeństwo i tak zapewnia token (require_api_token), nie CORS -
    # to jest osobisty, jednoużytkownikowy serwer w sieci domowej/Tailscale,
    # nigdy nie wystawiony publicznie (patrz docs/01_app.md §4), więc otwarty
    # `allow_origins` tutaj nie jest realnym ryzykiem.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    register_exception_handlers(app)

    # TOOM Mobile jako PWA - serwowane z tego samego procesu/portu co API,
    # żeby na Raspberry Pi wystarczył jeden systemd service i jeden wpis
    # `tailscale serve` (patrz docs/01_app.md §6.5). Mount MUSI być
    # zarejestrowany PO api_router - to jedyny sposób, żeby ścieżki API
    # miały pierwszeństwo, a StaticFiles("/") działał jako fallback dla
    # reszty (HTML, JS bundli, manifest.json, sw.js). Brak konfiguracji
    # (web_app_dist_path=None, domyślnie) = backend serwuje tylko API,
    # tak jak dotychczas.
    dist_path = settings.api.web_app_dist_path
    if dist_path is not None:
        if dist_path.is_dir():
            app.mount("/", StaticFiles(directory=dist_path, html=True), name="webapp")
            logger.info("TOOM Mobile (PWA) serwowany z {}", dist_path)
        else:
            logger.warning(
                "WEB_APP_DIST_PATH={} nie istnieje - backend serwuje wyłącznie API",
                dist_path,
            )

    return app


async def _run_application() -> None:
    """
    Buduje i uruchamia wszystkie komponenty aplikacji współbieżnie.
    """
    settings = get_settings()
    configure_logging(settings.logging, settings.app.debug)

    logger.info("=" * 60)
    logger.info("Uruchamianie TOOM")
    logger.info("=" * 60)

    bot = create_bot(settings.telegram)
    dispatcher = create_dispatcher()
    container = Container(settings=settings, bot=bot)

    register_event_subscriptions(container)
    _register_bot_routers(dispatcher)

    dispatcher.update.middleware(AdminOnlyMiddleware(settings.telegram.admin_chat_id))
    dispatcher.update.middleware(ContainerMiddleware(container))

    # Middleware sesji bota rejestruje ID każdej wysłanej wiadomości -
    # niezbędne dla nocnego czyszczenia czatu (02:00).
    bot.session.middleware(
        MessageTrackingMiddleware(container, settings.telegram.admin_chat_id)
    )

    scheduler = create_scheduler()

    async def scheduled_sync_job() -> None:
        """Wrapper wywoływany cyklicznie przez APScheduler."""
        await run_sync_orders_job(
            session_scope_factory=container.session_scope,
            build_sync_service=container.sync_orders_service,
            sync_status=container.sync_status,
        )

    async def scheduled_backup_job() -> None:
        """Wrapper wywoływany codziennie przez APScheduler."""
        await run_backup_job(
            session_scope_factory=container.session_scope,
            build_backup_service=container.backup_service,
        )

    async def scheduled_shipping_reminder_job() -> None:
        """Wrapper przypomnienia o niewysłanych zamówieniach (20:00)."""
        await run_shipping_reminder_job(
            session_scope_factory=container.session_scope,
            build_reminder_service=container.shipping_reminder_service,
            notifier=container.notifier(),
        )

    async def scheduled_telegram_cleanup_job() -> None:
        """Wrapper nocnego czyszczenia czatu Telegram (02:00)."""
        await run_telegram_cleanup_job(
            session_scope_factory=container.session_scope,
            build_cleanup_service=container.telegram_cleanup_service,
        )

    register_sync_orders_job(
        scheduler,
        scheduled_sync_job,
        interval_seconds=settings.scheduler.sync_orders_interval_seconds,
    )
    register_backup_job(scheduler, scheduled_backup_job)
    register_shipping_reminder_job(scheduler, scheduled_shipping_reminder_job)
    register_telegram_cleanup_job(scheduler, scheduled_telegram_cleanup_job)

    fastapi_app = _create_fastapi_app(container, settings)
    uvicorn_config = uvicorn.Config(
        fastapi_app,
        host=settings.api.host,
        port=settings.api.port,
        log_config=None,
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    stop_event = asyncio.Event()

    def _handle_shutdown_signal(sig_name: str) -> None:
        """Ustawia zdarzenie zatrzymania po otrzymaniu SIGTERM/SIGINT."""
        logger.info("Otrzymano sygnał {} - rozpoczynam zamykanie aplikacji", sig_name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_shutdown_signal, sig.name)
    except NotImplementedError:
        # Windows (środowisko deweloperskie): add_signal_handler nie jest
        # wspierane - fallback na signal.signal z bezpiecznym przekazaniem
        # do pętli asyncio.
        def _sync_signal_handler(signum: int, _frame: object) -> None:
            loop.call_soon_threadsafe(
                _handle_shutdown_signal, signal.Signals(signum).name
            )

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, _sync_signal_handler)

    scheduler.start()
    logger.info("Scheduler uruchomiony")

    bot_polling_task = asyncio.create_task(
        dispatcher.start_polling(bot, handle_signals=False)
    )
    api_task = asyncio.create_task(uvicorn_server.serve())

    logger.info("TOOM został w pełni uruchomiony i jest gotowy do pracy")

    await stop_event.wait()

    logger.info("Zamykanie aplikacji TOOM...")

    scheduler.shutdown(wait=False)

    await dispatcher.stop_polling()
    bot_polling_task.cancel()
    with suppress(asyncio.CancelledError):
        await bot_polling_task

    uvicorn_server.should_exit = True
    with suppress(asyncio.CancelledError):
        await api_task

    await bot.session.close()
    await container.dispose()

    logger.info("Aplikacja zamknięta poprawnie")


def main() -> None:
    """Synchroniczny punkt wejścia (wywoływany przez `python -m app.main`)."""
    asyncio.run(_run_application())


if __name__ == "__main__":
    main()

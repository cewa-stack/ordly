"""
Raport wysyłki Web Push - podstawa odpowiedzi przycisku „Wyślij testowe
powiadomienie" w Ustawieniach telefonu.

Zgłoszony błąd: po zmianie telefonu test mówił „wysłano do N urządzeń",
bo endpoint liczył wiersze w bazie - razem z martwą subskrypcją starego
telefonu. Tu sprawdzamy na prawdziwej bazie SQLite, że raport liczy
wyłącznie to, co serwer push faktycznie przyjął, i że martwe wpisy znikają.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from pywebpush import WebPushException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.database.models  # noqa: F401 - rejestruje tabele w Base.metadata
from app.database.base import Base
from app.domain.entities.push_subscription import PushSubscription
from app.infrastructure.webpush import web_push_notifier as notifier_module
from app.infrastructure.webpush.web_push_notifier import WebPushNotifier
from app.repositories.sqlite_push_subscription_repository import (
    SqlitePushSubscriptionRepository,
)

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]

_OLD_PHONE = "https://web.push.apple.com/stary-telefon"
_NEW_PHONE = "https://web.push.apple.com/nowy-telefon"


@pytest_asyncio.fixture
async def session_scope(tmp_path: Path) -> AsyncIterator[SessionScope]:
    """Ta sama semantyka co `Container.session_scope`: commit albo rollback."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'push.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def scope() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    yield scope
    await engine.dispose()


async def _subscribe(scope: SessionScope, *endpoints: str) -> None:
    async with scope() as session:
        repository = SqlitePushSubscriptionRepository(session)
        for endpoint in endpoints:
            await repository.add(
                PushSubscription(
                    endpoint=endpoint, p256dh="p256dh", auth="auth", created_at=datetime.now()
                )
            )


def _notifier(scope: SessionScope) -> WebPushNotifier:
    return WebPushNotifier(
        session_scope_factory=scope,
        vapid_private_key="klucz-testowy",
        vapid_claim_email="mailto:test@example.com",
    )


class TestSendTest:
    async def test_martwa_subskrypcja_starego_telefonu_nie_liczy_sie_jako_wyslana(
        self, session_scope: SessionScope, monkeypatch: pytest.MonkeyPatch
    ):
        await _subscribe(session_scope, _OLD_PHONE, _NEW_PHONE)

        def fake_webpush(subscription_info: dict, **_: object) -> None:
            if subscription_info["endpoint"] == _OLD_PHONE:
                raise WebPushException("Gone", response=SimpleNamespace(status_code=410))

        monkeypatch.setattr(notifier_module, "webpush", fake_webpush)

        report = await _notifier(session_scope).send_test()

        assert report.subscriptions == 2
        assert report.delivered == 1
        assert report.expired == 1
        assert report.failed == 0
        async with session_scope() as session:
            remaining = await SqlitePushSubscriptionRepository(session).get_all()
        assert [subscription.endpoint for subscription in remaining] == [_NEW_PHONE]

    async def test_blad_serwera_push_to_failed_a_subskrypcja_zostaje(
        self, session_scope: SessionScope, monkeypatch: pytest.MonkeyPatch
    ):
        """Chwilowa awaria (np. 500 u Apple) nie może kasować działającego telefonu."""
        await _subscribe(session_scope, _NEW_PHONE)

        def fake_webpush(**_: object) -> None:
            raise WebPushException("Server error", response=SimpleNamespace(status_code=500))

        monkeypatch.setattr(notifier_module, "webpush", fake_webpush)

        report = await _notifier(session_scope).send_test()

        assert (report.delivered, report.expired, report.failed) == (0, 0, 1)
        async with session_scope() as session:
            remaining = await SqlitePushSubscriptionRepository(session).get_all()
        assert len(remaining) == 1

    async def test_brak_subskrypcji_daje_pusty_raport(self, session_scope: SessionScope):
        report = await _notifier(session_scope).send_test()

        assert report.subscriptions == 0
        assert report.delivered == 0

    async def test_test_nie_jest_wyciszany_w_godzinach_ciszy(
        self, session_scope: SessionScope, monkeypatch: pytest.MonkeyPatch
    ):
        """Test o 23:30 bez dźwięku wyglądałby na niedziałający."""
        await _subscribe(session_scope, _NEW_PHONE)
        sent: list[dict] = []
        monkeypatch.setattr(
            notifier_module, "webpush", lambda data, **_: sent.append(json.loads(data))
        )
        monkeypatch.setattr(notifier_module, "local_now", lambda: datetime(2026, 9, 13, 23, 30))

        await _notifier(session_scope).send_test()

        assert sent[0]["silent"] is False

    async def test_zwykle_powiadomienie_w_godzinach_ciszy_dalej_jest_ciche(
        self, session_scope: SessionScope, monkeypatch: pytest.MonkeyPatch
    ):
        """Wyjątek dla testu nie może rozszczelnić godzin ciszy reszty katalogu."""
        await _subscribe(session_scope, _NEW_PHONE)
        sent: list[dict] = []
        monkeypatch.setattr(
            notifier_module, "webpush", lambda data, **_: sent.append(json.loads(data))
        )
        monkeypatch.setattr(notifier_module, "local_now", lambda: datetime(2026, 9, 13, 23, 30))

        await _notifier(session_scope).notify_sync_failed("allegro", 5)

        assert sent[0]["silent"] is True

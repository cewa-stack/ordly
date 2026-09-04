"""
Rejestracja subskrybentów Event Busa - "co się dzieje po zdarzeniu X".

Ten moduł jest jedynym miejscem spinającym zdarzenia domenowe
z konkretnymi akcjami (wysyłka Telegram przez bota ORDLY, zapis
do audytu). Wywoływane raz, przy starcie aplikacji, w app/main.py.
"""

from __future__ import annotations

from loguru import logger

from app.container import Container
from app.core.event_bus.events import (
    AllegroLokalnieEventDetected,
    DisputeNoticeDetected,
    LowStockDetected,
    NotificationSent,
    OlxEventDetected,
    OrderCancelled,
    OrderCreated,
    OrderPackingStarted,
    OrderReturnCreated,
    SyncFinished,
    SyncStarted,
)
from app.repositories.sqlite_event_repository import SqliteEventRepository
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.shared.dto.inventory_dto import StockSyncOutcome
from app.utils.time import utc_now


def register_event_subscriptions(container: Container) -> None:
    """
    Rejestruje wszystkich subskrybentów zdarzeń domenowych.

    Args:
        container: W pełni skonstruowany kontener DI aplikacji.
    """

    async def _record_stock_sync(
        event_repository: SqliteEventRepository, outcome: StockSyncOutcome
    ) -> None:
        """Zapisuje w audycie wynik automatycznej synchronizacji magazynu."""
        await event_repository.record(
            event_type="StockSynchronized",
            level="WARNING" if outcome.unmatched_products else "INFO",
            payload={
                "operation": outcome.operation,
                "reference": outcome.reference,
                "unmatched_products": list(outcome.unmatched_products),
            },
        )

    async def _warn_unmatched_products(outcome: StockSyncOutcome | None) -> None:
        """
        Ostrzega, że sprzedane pozycje nie ruszyły magazynu.

        Bez tego brak receptury oferty objawia się wyłącznie tym, że stan
        magazynowy stoi w miejscu - a to wygląda jak awaria, nie jak brak
        konfiguracji. Alarm wskazuje konkretną ofertę do powiązania.

        Treść buduje KANAŁ, nie to miejsce. Wcześniej powstawał tu jeden
        string sformatowany pod Telegram (`<b>`, `<code>`) i szedł do
        wszystkich kanałów naraz - Web Push nie renderuje HTML, więc na
        ekranie blokady lądowały dosłowne znaczniki. Teraz każdy kanał
        formatuje po swojemu: Telegram nadal HTML-em, push pozycją
        z katalogu `push_payload`.
        """
        if outcome is None or not outcome.unmatched_products:
            return

        try:
            await container.notifier().notify_unmatched_products(
                outcome.reference, list(outcome.unmatched_products)
            )
        except Exception:
            logger.exception(
                "Nie udało się wysłać ostrzeżenia o pozycjach bez mapowania magazynowego"
            )

    async def _publish_low_stock(outcome: StockSyncOutcome | None) -> None:
        """Publikuje LowStockDetected dla produktów, które osiągnęły minimum."""
        if outcome is None:
            return
        for item in outcome.low_stock_items:
            await container.event_bus.publish(
                LowStockDetected(
                    occurred_at=utc_now(),
                    sku=item.sku,
                    name=item.name,
                    stock=item.stock,
                    min_stock=item.min_stock,
                )
            )

    async def handle_order_created(event: OrderCreated) -> None:
        """
        Po zapisaniu nowego zamówienia: wysyła powiadomienie Telegram
        (ORDLY), oznacza zamówienie jako powiadomione, automatycznie
        odejmuje sprzedane produkty z magazynu i zapisuje fakt w audycie.
        """
        order = event.order
        notifier = container.notifier()

        try:
            await notifier.notify_new_order(order)
            notification_sent = True
        except Exception:
            logger.exception(
                "Nie udało się wysłać powiadomienia dla zamówienia {}",
                order.external_id,
            )
            notification_sent = False

        stock_outcome: StockSyncOutcome | None = None
        async with container.session_scope() as session:
            if notification_sent:
                order_repository = SqliteOrderRepository(session)
                await order_repository.mark_as_notified(order.marketplace, order.external_id)
                await container.event_bus.publish(
                    NotificationSent(
                        occurred_at=event.occurred_at,
                        order_external_id=order.external_id,
                    )
                )

            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="OrderCreated",
                level="INFO",
                payload={
                    "external_id": order.external_id,
                    "amount": str(order.total_amount),
                    "notification_sent": notification_sent,
                },
            )

            try:
                # Savepoint gwarantuje atomowość odejmowania komponentów:
                # błąd przy którymkolwiek składniku wycofuje całą operację
                # (znacznik + wszystkie zmiany stanów), umożliwiając ponowną
                # próbę przy następnej synchronizacji.
                async with session.begin_nested():
                    stock_sync = container.stock_sync_service(session)
                    stock_outcome = await stock_sync.process_order_created(order)
                if stock_outcome.processed:
                    await _record_stock_sync(event_repository, stock_outcome)
            except Exception:
                logger.exception(
                    "Synchronizacja magazynu dla zamówienia {} nie powiodła się",
                    order.external_id,
                )
                stock_outcome = None

        await _warn_unmatched_products(stock_outcome)
        await _publish_low_stock(stock_outcome)

    async def handle_order_cancelled(event: OrderCancelled) -> None:
        """
        Po wykryciu anulowania zamówienia: wysyła powiadomienie Telegram
        (ORDLY) i zapisuje fakt w audycie.
        """
        order = event.order
        notifier = container.notifier()

        try:
            await notifier.notify_order_cancelled(order)
            notification_sent = True
        except Exception:
            logger.exception(
                "Nie udało się wysłać powiadomienia o anulowaniu zamówienia {}",
                order.external_id,
            )
            notification_sent = False

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="OrderCancelled",
                level="WARNING",
                payload={
                    "external_id": order.external_id,
                    "amount": str(order.total_amount),
                    "notification_sent": notification_sent,
                },
            )

            try:
                async with session.begin_nested():
                    stock_sync = container.stock_sync_service(session)
                    stock_outcome = await stock_sync.process_order_cancelled(order)
                if stock_outcome.processed:
                    await _record_stock_sync(event_repository, stock_outcome)
            except Exception:
                logger.exception(
                    "Przywracanie stanów po anulowaniu zamówienia {} nie powiodło się",
                    order.external_id,
                )

    async def handle_order_return_created(event: OrderReturnCreated) -> None:
        """
        Po wykryciu nowego zwrotu klienta: wysyła powiadomienie Telegram
        (ORDLY) i zapisuje fakt w audycie.
        """
        order_return = event.order_return
        notifier = container.notifier()

        try:
            await notifier.notify_order_return(order_return)
            notification_sent = True
        except Exception:
            logger.exception(
                "Nie udało się wysłać powiadomienia o zwrocie {}",
                order_return.external_id,
            )
            notification_sent = False

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="OrderReturnCreated",
                level="WARNING",
                payload={
                    "return_external_id": order_return.external_id,
                    "order_external_id": order_return.order_external_id,
                    "status": order_return.status,
                    "notification_sent": notification_sent,
                },
            )

            try:
                async with session.begin_nested():
                    stock_sync = container.stock_sync_service(session)
                    stock_outcome = await stock_sync.process_return(order_return)
                if stock_outcome.processed:
                    await _record_stock_sync(event_repository, stock_outcome)
            except Exception:
                logger.exception(
                    "Przywracanie stanów po zwrocie {} nie powiodło się",
                    order_return.external_id,
                )

    async def handle_order_packing_started(event: OrderPackingStarted) -> None:
        """
        Po wykryciu rozpoczęcia pakowania zamówienia: wysyła SMS do klienta
        (przez SmsService, z gwarancją jednorazowości) i zapisuje wynik
        w audycie. Błąd bramki SMS nie przerywa dalszej obsługi.
        """
        order = event.order
        async with container.session_scope() as session:
            sms_service = container.sms_service(session)
            outcome = await sms_service.send_packing_started(order)

            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="OrderPackingStarted",
                level="INFO",
                payload={
                    "external_id": order.external_id,
                    "sms_sent": outcome.sent,
                    "skipped_reason": outcome.skipped_reason,
                },
            )

    async def handle_low_stock_detected(event: LowStockDetected) -> None:
        """
        Po osiągnięciu minimalnego stanu magazynowego: wysyła ostrzeżenie
        Telegram (ORDLY) i zapisuje fakt w audycie. Produkt jest już na
        liście zakupów (lista wynika bezpośrednio ze stanów w bazie).
        """
        notifier = container.notifier()
        try:
            await notifier.notify_low_stock(
                name=event.name,
                sku=event.sku,
                stock=event.stock,
                min_stock=event.min_stock,
            )
        except Exception:
            logger.exception(
                "Nie udało się wysłać ostrzeżenia o niskim stanie produktu {}",
                event.sku,
            )

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="LowStockDetected",
                level="WARNING",
                payload={
                    "sku": event.sku,
                    "name": event.name,
                    "stock": event.stock,
                    "min_stock": event.min_stock,
                },
            )

    async def handle_notification_sent(event: NotificationSent) -> None:
        """Loguje potwierdzenie pomyślnej wysyłki powiadomienia."""
        logger.info("Powiadomienie dla zamówienia {} zostało wysłane", event.order_external_id)

    async def handle_sync_started(event: SyncStarted) -> None:
        """Zapisuje w audycie moment rozpoczęcia synchronizacji."""
        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(event_type="SyncStarted", level="INFO")

    async def handle_allegro_lokalnie_event(event: AllegroLokalnieEventDetected) -> None:
        """
        Obsługuje zdarzenie z Allegro Lokalnie i zapisuje je w audycie.

        To jedyny sygnał, jaki ORDLY dostaje z tego serwisu - Allegro
        Lokalnie nie ma API, więc bez tego maila sprzedaż tam byłaby dla
        aplikacji niewidzialna.

        Sprzedaż z kompletem danych staje się PEŁNOPRAWNYM zamówieniem:
        publikujemy `OrderCreated`, czyli ten sam tor co przy Allegro.pl
        (odjęcie stanów magazynowych, statystyki, lista do spakowania,
        powiadomienie „Nowe zamówienie"). Wtedy `notify_allegro_lokalnie`
        NIE leci - inaczej użytkownik dostałby dwa powiadomienia o jednej
        sprzedaży.

        Wszystko inne - wiadomość od kupującego, pytanie o dostawę,
        doręczenie paczki, nierozpoznany szablon - zostaje powiadomieniem
        ze skrzynki, bo nie ma z tego czego odjąć ani czego policzyć.
        """
        detected = event.event
        created_order = None
        try:
            async with container.session_scope() as session:
                created_order = await container.allegro_lokalnie_orders_service(
                    session
                ).create_from_event(detected)
        except Exception:
            logger.exception(
                "Nie udało się zapisać zamówienia z Allegro Lokalnie {}",
                detected.message_id,
            )

        if created_order is not None:
            # Zdarzenie publikujemy PO zamknięciu sesji zapisu -
            # subskrybenci (magazyn, audyt) piszą we własnych sesjach
            # i muszą widzieć zatwierdzone zamówienie.
            await container.event_bus.publish(
                OrderCreated(occurred_at=utc_now(), order=created_order)
            )
        else:
            try:
                await container.notifier().notify_allegro_lokalnie(detected)
            except Exception:
                logger.exception(
                    "Nie udało się wysłać powiadomienia o zdarzeniu Allegro Lokalnie {}",
                    detected.message_id,
                )

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="AllegroLokalnieEventDetected",
                # Nierozpoznany szablon maila to sygnał do aktualizacji
                # wzorców - ma być widoczny w logach aplikacji, nie tylko
                # w treści powiadomienia.
                level="WARNING" if detected.event_type == "unknown" else "INFO",
                payload={
                    "message_id": detected.message_id,
                    "event_type": detected.event_type,
                    "subject": detected.subject,
                    "amount": str(detected.amount) if detected.amount is not None else None,
                    # Numer zamówienia, jeśli zdarzenie stało się sprzedażą -
                    # inaczej z audytu nie da się odtworzyć, czy mail tylko
                    # powiadomił, czy ruszył magazyn.
                    "order_external_id": (
                        created_order.external_id if created_order is not None else None
                    ),
                },
            )

    async def handle_olx_event(event: OlxEventDetected) -> None:
        """
        Powiadamia o zdarzeniu z OLX i zapisuje je w audycie.

        To jedyny sygnał, jaki ORDLY dostaje z OLX - serwis nie ma
        samoobsługowego API dla sprzedawców, więc bez tego maila
        wszystko, co się tam dzieje, byłoby dla aplikacji niewidzialne.
        Do niedawna właśnie tak było: poczta OLX nie generowała żadnych
        zdarzeń.

        W ODRÓŻNIENIU OD ALLEGRO LOKALNIE sprzedaż z OLX NIE staje się
        zamówieniem i nie rusza magazynu ani statystyk. Powód jest
        w danych, nie w kodzie: mail sprzedażowy z OLX nie podaje żadnej
        kwoty (patrz `domain/entities/olx_event.py`), a zamówienie
        wpisane z kwotą 0 zł zafałszowałoby przychód i nie dałoby się go
        potem poprawić z aplikacji. Powiadomienie mówi więc dokładnie
        tyle, ile mail: co i kiedy się sprzedało - stan odejmujesz sam.
        """
        detected = event.event
        try:
            await container.notifier().notify_olx_event(detected)
        except Exception:
            logger.exception(
                "Nie udało się wysłać powiadomienia o zdarzeniu OLX {}",
                detected.message_id,
            )

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="OlxEventDetected",
                # Nierozpoznany szablon maila to sygnał do uzupełnienia
                # wzorców - ma być widoczny w logach aplikacji, nie tylko
                # w treści powiadomienia.
                level="WARNING" if detected.event_type == "unknown" else "INFO",
                payload={
                    "message_id": detected.message_id,
                    "event_type": detected.event_type,
                    "subject": detected.subject,
                    "listing_title": detected.listing_title,
                    # UUID transakcji - po nim odnajdziesz sprzedaż
                    # w panelu OLX, gdy trzeba sprawdzić kwotę.
                    "order_id": detected.order_id,
                },
            )

    async def handle_dispute_notice(event: DisputeNoticeDetected) -> None:
        """
        Powiadamia o rozpoczętej dyskusji i zapisuje ją w audycie.

        Do tej pory ORDLY nie mówił o dyskusjach nic - wątki pobierał
        dopiero wtedy, gdy sam otworzyłeś ekran Dyskusji. Termin
        odpowiedzi („inaczej włączymy się do rozmowy") jest wyłącznie
        w mailu, więc to jedyne miejsce, z którego można go wziąć.
        """
        notice = event.notice
        try:
            await container.notifier().notify_new_dispute(notice)
        except Exception:
            logger.exception(
                "Nie udało się wysłać powiadomienia o dyskusji {}", notice.issue_id
            )

        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="DisputeNoticeDetected",
                level="WARNING",
                payload={
                    "issue_id": notice.issue_id,
                    "buyer_login": notice.buyer_login,
                    "order_external_id": notice.order_external_id,
                    "reason": notice.reason,
                    "respond_by": (
                        notice.respond_by.isoformat() if notice.respond_by else None
                    ),
                },
            )

    async def handle_sync_finished(event: SyncFinished) -> None:
        """Zapisuje w audycie podsumowanie zakończonej synchronizacji."""
        async with container.session_scope() as session:
            event_repository = SqliteEventRepository(session)
            await event_repository.record(
                event_type="SyncFinished",
                level="INFO",
                payload={
                    "new_orders_count": event.new_orders_count,
                    "checked_orders_count": event.checked_orders_count,
                },
            )

    container.event_bus.subscribe(OrderCreated, handle_order_created)
    container.event_bus.subscribe(OrderCancelled, handle_order_cancelled)
    container.event_bus.subscribe(OrderPackingStarted, handle_order_packing_started)
    container.event_bus.subscribe(OrderReturnCreated, handle_order_return_created)
    container.event_bus.subscribe(LowStockDetected, handle_low_stock_detected)
    container.event_bus.subscribe(NotificationSent, handle_notification_sent)
    container.event_bus.subscribe(SyncStarted, handle_sync_started)
    container.event_bus.subscribe(SyncFinished, handle_sync_finished)
    container.event_bus.subscribe(AllegroLokalnieEventDetected, handle_allegro_lokalnie_event)
    container.event_bus.subscribe(OlxEventDetected, handle_olx_event)
    container.event_bus.subscribe(DisputeNoticeDetected, handle_dispute_notice)

    logger.info("Zarejestrowano subskrybentów Event Busa")

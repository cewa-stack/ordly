# Architektura projektu - ORDLY

Pełny opis architektury Clean Architecture + Plugin Architecture
zastosowanej w projekcie. Kluczowe punkty:

## Kierunek zależności

```
infrastructure/plugins/allegro  ->  domain/interfaces  <-  services
database/models                 ->  domain/entities     <-  repositories
```

Domain nigdy nie zależy od infrastructure. Zawsze odwrotnie.

## Warstwy

| Warstwa | Odpowiedzialność | Przykładowe pliki |
|---|---|---|
| domain | Encje biznesowe, kontrakty (interfejsy) | `entities/order.py`, `interfaces/marketplace_plugin.py` |
| services | Logika aplikacyjna (use cases) | `sync_orders_service.py` |
| infrastructure | Integracje zewnętrzne (szczegóły) | `plugins/allegro/`, `telegram/` |
| repositories | Implementacje dostępu do danych | `sqlite_order_repository.py` |
| bot/api | Warstwa prezentacji (bot ORDLY + REST API) | `bot/handlers/`, `api/endpoints/` |
| scheduler | Wyzwalacze cykliczne | `jobs/sync_orders_job.py` |

## Event Bus

Komunikacja między modułami odbywa się przez zdarzenia
(`core/event_bus/`), nie przez bezpośrednie wywołania - pozwala to
dodawać nowe reakcje na zdarzenia biznesowe bez modyfikacji kodu,
który je emituje.

Zdarzenia: `OrderCreated`, `OrderUpdated`, `ShipmentChecked`,
`NotificationSent`, `PluginLoaded`, `BackupCreated`, `SyncStarted`,
`SyncFinished`.

## Dependency Injection

Cały graf zależności składany jest ręcznie w `app/container.py`
(`Container`) - bez zewnętrznej biblioteki DI, zgodnie z zasadą KISS.
Sesja bazy danych jest tworzona per operacja (komenda Telegram,
żądanie HTTP, cykl schedulera), nigdy dzielona globalnie.

## Plugin Architecture

Allegro to pierwszy plugin implementujący `MarketplacePlugin`.
Dodanie kolejnego marketplace (Amazon, eBay, Shopify...) opisane
jest w [adding_new_marketplace.md](adding_new_marketplace.md).

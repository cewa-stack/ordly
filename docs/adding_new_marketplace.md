# Dodawanie nowego marketplace

Ten przewodnik pokazuje, jak dodać integrację z nowym marketplace
(np. Amazon, eBay, Shopify) **bez modyfikowania** istniejącego kodu
aplikacji.

## Krok 1: Utwórz strukturę folderu pluginu

```
src/app/infrastructure/plugins/amazon/
├── __init__.py
├── config.py       # Konfiguracja specyficzna dla Amazon
├── auth.py         # Autoryzacja (np. Amazon SP-API auth)
├── client.py        # Klient HTTP do Amazon API
├── mapper.py         # Mapowanie JSON Amazon -> encje domenowe
├── plugin.py          # AmazonPlugin(MarketplacePlugin)
└── exceptions.py       # Wyjątki specyficzne dla Amazon
```

## Krok 2: Zaimplementuj interfejs `MarketplacePlugin`

Skopiuj strukturę z `infrastructure/plugins/allegro/plugin.py` jako
wzór. Każda metoda musi zwracać te same encje domenowe (`Order`,
`Product`, `Shipment`), zdefiniowane w `domain/entities/` - nigdy
surowy JSON z Amazon API.

## Krok 3: Napisz mapper

W `mapper.py` przetłumacz pola specyficzne dla Amazon na pola encji
domenowych. To jedyne miejsce, które powinno znać te szczegóły.

## Krok 4: Dodaj konfigurację do `.env`

```dotenv
AMAZON_CLIENT_ID=...
AMAZON_CLIENT_SECRET=...
```

## Krok 5: Zarejestruj plugin w Container

W `app/container.py`, metoda `build_plugin()`:

```python
def build_plugin(self, session: AsyncSession) -> MarketplacePlugin:
    provider = self._settings.marketplace.marketplace_provider
    if provider == "allegro":
        return AllegroPlugin(config=AllegroConfig(), token_store=SqliteTokenStore(session))
    if provider == "amazon":
        return AmazonPlugin(config=AmazonConfig(), token_store=SqliteTokenStore(session))
    raise ValueError(f"Nieznany dostawca marketplace: {provider}")
```

## Krok 6: Zmień `.env`

```dotenv
MARKETPLACE_PROVIDER=amazon
```

## Krok 7: Testy

Napisz `tests/unit/plugins/test_amazon_mapper.py` analogicznie do
`test_allegro_mapper.py`.

## Co NIE wymaga zmian

- `domain/` (encje i interfejsy)
- `services/` (cała logika biznesowa)
- `bot/handlers/` (komendy Telegram bota ORDLY)
- `scheduler/` (job synchronizacji)

Jeśli podczas dodawania nowego marketplace musisz zmodyfikować
którykolwiek z powyższych - to sygnał, że coś zostało zaprojektowane
niezgodnie z założeniami architektury.

# ORDLY — Naprawa powiadomień push (HTML w treści + wygląd niezgodny z iOS)

## Zgłoszony problem (ze zrzutu ekranu)

Dwa osobne, ale powiązane problemy w kanale Web Push (`ORDLY Mobile` PWA
na iPhone):

1. **Surowe tagi HTML widoczne w treści powiadomienia** — np.
   `⚠️ <b>Sprzedaż poza magazynem</b> Zamówienie ... zawiera pozycje bez
   powiązania z magazynem, więc st...` — `<b>` i `<code>` wychodzą jako
   dosłowny tekst, bo iOS/Web Push nie renderuje HTML.
2. **Ogólny wygląd nie przypomina natywnego powiadomienia iOS** — treść
   jest zbita w jeden ciąg, format nie trzyma spójnej konwencji
   tytuł/treść jak w prawdziwych aplikacjach.

## Zdiagnozowana przyczyna źródłowa

### Przyczyna #1 (HTML) — potwierdzona w kodzie
`event_subscriptions.py`, funkcja `_warn_unmatched_products` (linie ok.
52–76), buduje wiadomość **sformatowaną pod Telegram** (składnia HTML:
`<b>`, `<code>` — Telegram to renderuje, bo bot ustawia `parse_mode=HTML`)
i wysyła ją przez:

```python
await container.notifier().send_text(
    "⚠️ <b>Sprzedaż poza magazynem</b>\n"
    f"Zamówienie {outcome.reference} zawiera pozycje bez powiązania "
    ...
)
```

`container.notifier()` (`container.py`, metoda `notifier()`) zwraca
**`CompositeNotifier`**, który rozgłasza `send_text()` do WSZYSTKICH
aktywnych kanałów naraz — dziś: `TelegramNotifier` **i**
`WebPushNotifier` (`infrastructure/composite_notifier.py`). Telegram
poprawnie zinterpretuje HTML. `WebPushNotifier.send_text()`
(`infrastructure/webpush/web_push_notifier.py`, linia ~186) **wstawia
string jeden do jednego** jako `body` payloadu push, bez żadnego
oczyszczania z HTML:

```python
async def send_text(self, text: str) -> None:
    await self._send(PushPayload(title="ORDLY", body=text, ...))
```

Stąd dosłowne `<b>...</b>` na ekranie iPhone'a. To nie jest odosobniony
przypadek — **każde** wywołanie `notifier().send_text(...)` z HTML w
treści ma ten sam efekt na kanale push. Warto to potraktować jako klasę
błędu, nie punktowy fix jednego stringa.

### Przyczyna #2 (wygląd) — do przeglądu, nie pojedynczy bug
Właściwy katalog treści dla Web Push już istnieje i jest zaprojektowany
sensownie: `infrastructure/webpush/push_payload.py` — osobne buildery
(`new_order`, `many_new_orders`, `low_stock`, `new_return`,
`sync_failed`, `pending_packing`) z czystym tekstem (bez HTML), polską
odmianą liczebników, formatowaniem kwot itd. Problem w tym, że **nie
każde zdarzenie ma tam swój builder** — ostrzeżenie o niepowiązanych
produktach (Przyczyna #1) w ogóle omija ten katalog i leci przez
uniwersalny, telegramowy `send_text`. To samo dotyczy każdego innego
miejsca w kodzie, które używa `notifier().send_text(...)` zamiast
dedykowanej metody z katalogu.

## Rozwiązanie — dwa poziomy

### Poziom 1 — siatka bezpieczeństwa (natychmiastowy, defensywny fix)
`WebPushNotifier.send_text()` (i każde miejsce budujące `PushPayload`
z tekstu, który mógł przejść przez wspólną ścieżkę z Telegramem) ma
**zawsze** oczyszczać treść z HTML, zanim trafi do `body`. Dodaj
funkcję pomocniczą w `push_payload.py`:

```python
import re

_HTML_TAG = re.compile(r"<[^>]+>")

def strip_html(text: str) -> str:
    """
    Usuwa znaczniki HTML (np. <b>, <code>) z treści przeznaczonej pod
    Web Push - ten kanał nie renderuje HTML, w przeciwieństwie do
    Telegrama. Zabezpieczenie na wypadek, gdyby tekst formatowany pod
    Telegram trafił tu przez wspólną ścieżkę `send_text`.
    """
    return _HTML_TAG.sub("", text)
```

I użyj jej w `WebPushNotifier.send_text()`:
```python
async def send_text(self, text: str) -> None:
    await self._send(
        PushPayload(title="ORDLY", body=push_payload.strip_html(text), ...)
    )
```

To gwarantuje, że nawet jeśli ktoś w przyszłości doda kolejne
`send_text(...)` z HTML, na push i tak nie wyjdą surowe tagi. **To
jednak tylko plaster** — nie naprawia tego, że treść nie ma własnego,
przemyślanego formatu na push (patrz Poziom 2).

### Poziom 2 — właściwa naprawa: każde zdarzenie ma builder w katalogu
Zamiast przepuszczać telegramowy string przez `send_text`, dodaj do
`Notifier` (interfejs, `domain/interfaces/notifier.py`) nową metodę
dedykowaną dla tego konkretnego zdarzenia:

```python
async def notify_unmatched_products(
    self, reference: str, product_names: list[str]
) -> None:
    """Ostrzega, że sprzedane pozycje nie mają powiązania z magazynem."""
    ...
```

- **`TelegramNotifier`**: implementacja zachowuje dotychczasowy,
  bogaty format z `<b>`/`<code>` (Telegram sobie z tym radzi).
- **`WebPushNotifier`**: implementacja korzysta z NOWEGO buildera w
  `push_payload.py`, np.:
  ```python
  def unmatched_products(*, reference: str, product_names: list[str]) -> PushPayload:
      """Sprzedaż bez powiązania z magazynem - stan się nie zmienił."""
      names = ", ".join(product_names[:2])
      extra = f" i {len(product_names) - 2} innych" if len(product_names) > 2 else ""
      return PushPayload(
          title="Sprzedaż poza magazynem",
          body=f"Zamówienie #{reference[:8].upper()}: {names}{extra} — stan bez zmian.",
          thread="stock",
          url=f"/orders/{reference}",
          collapse_key=f"unmatched:{reference}",
      )
  ```
  (Konkretne brzmienie do ustalenia w podglądzie — patrz niżej. To
  jest punkt wyjścia, nie ostateczna treść.)
- `event_subscriptions.py`: `_warn_unmatched_products` przestaje wołać
  `notifier().send_text(...)` z ręcznie sklejonym HTML-em, zamiast
  tego woła `container.notifier().notify_unmatched_products(reference, names)`.

Zastosuj tę samą zasadę do **każdego innego** miejsca w kodzie, które
dziś woła generyczny `send_text()` z formatowaniem pod Telegram
(przeszukaj `send_text(` w całym `backend/src/app` — lista z grepa
niżej), i oceń dla każdego, czy zasługuje na własny wpis w katalogu
`push_payload.py`, czy wystarczy mu przejście przez oczyszczony
`strip_html` (Poziom 1) jako fallback.

## WYMÓG PRZED WDROŻENIEM — podgląd HTML wszystkich powiadomień

**Nie wdrażaj tej zmiany na produkcję, dopóki nie dostanę wizualnej
akceptacji.** Zanim zaczniesz zmieniać kod produkcyjny:

1. Zbuduj **jeden statyczny plik HTML** (np.
   `docs/podglad-powiadomien-push.html`, poza katalogiem `app/` — to
   narzędzie do przeglądu, nie część aplikacji), który renderuje
   **każdy typ powiadomienia z katalogu `push_payload.py`** (obecne +
   nowo dodane, w tym `unmatched_products`) jako realistyczny dymek
   powiadomienia iOS: ikona aplikacji ORDLY (maskotka Ordlak, jest w
   `bot_ordlak/`), nazwa aplikacji/wątku, tytuł pogrubiony, treść,
   znacznik czasu (np. „teraz”) — wizualnie zbliżone do prawdziwego
   Centrum Powiadomień iOS (zaokrąglone rogi, blur/tło, typografia
   San Francisco lub zbliżona systemowa).
2. Dla każdego buildera użyj **realistycznych przykładowych danych**
   (prawdziwe nazwy produktów z tego projektu — butelki, nakrętki,
   kroplomierze — kwoty w PLN, sensowne loginy kupujących), żeby dało
   się ocenić długość treści i zawijanie tekstu, nie lorem ipsum.
3. Pokaż WSZYSTKIE warianty, łącznie z tymi rzadziej używanymi:
   `new_order`, `many_new_orders`, `low_stock`, `new_return`,
   `sync_failed`, `pending_packing`, `wholesaler_confirmed`,
   `unanswered_question`, oraz nowy `unmatched_products`.
4. Plik ma być samodzielny (jeden `.html`, inline CSS, bez zależności
   sieciowych) — mam go otworzyć lokalnie w przeglądarce i ocenić.
5. **Dopiero po mojej akceptacji** tego podglądu wprowadzaj zmiany w
   `push_payload.py` / `event_subscriptions.py` / `notifier.py` /
   `web_push_notifier.py` / `telegram_notifier.py` na produkcyjnym
   kodzie backendu.

Jeśli po podglądzie zdecyduję o zmianie treści/formatu konkretnego
powiadomienia — najpierw zaktualizuj podgląd HTML, poczekaj na
akceptację, potem dopiero kod.

## Kryteria akceptacji (po wdrożeniu, gdy podgląd zaakceptowany)

1. Żadne powiadomienie push nie zawiera surowych tagów HTML (`<b>`,
   `<code>`, `<i>` itd.) w treści widocznej na telefonie — sprawdź
   testem jednostkowym na `strip_html()` i/albo testem integracyjnym
   wysyłającym `notify_unmatched_products` i asertującym brak `<` w
   wynikowym `body`.
2. `_warn_unmatched_products` w `event_subscriptions.py` nie buduje już
   ręcznie stringa z HTML-em do wysyłki generycznej — korzysta z
   dedykowanej metody `Notifier`.
3. Telegram (bot) nadal wygląda tak jak dziś — pogrubienia, `<code>`
   z numerem oferty do skopiowania — ta zmiana dotyczy WYŁĄCZNIE
   kanału Web Push, nie ogranicza Telegrama.
4. Podgląd HTML z sekcji wyżej istnieje w repo (`docs/`) i pokrywa
   wszystkie buildery z `push_payload.py`, żeby przy kolejnych
   zmianach treści dało się go łatwo odświeżyć i znów pokazać do
   akceptacji, zamiast zgadywać jak coś wygląda na żywym telefonie.

## Czego NIE robić

- Nie wdrażaj żadnej zmiany treści/formatu na produkcję przed
  akceptacją podglądu HTML — to warunek twardy, nie sugestia.
- Nie usuwaj formatowania HTML z `TelegramNotifier` — tam działa
  poprawnie i jest pożądane (Telegram je renderuje).
- Nie ograniczaj się do zaklejenia jednego stringa w
  `_warn_unmatched_products` — napraw klasę problemu (Poziom 1 +
  Poziom 2), inaczej kolejny podobny `send_text()` z HTML-em w
  przyszłości znów wypłynie na telefon.

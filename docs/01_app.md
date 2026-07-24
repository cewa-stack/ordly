# TOOM Mobile — plan projektu

> Dokument żywy. Każda decyzja architektoniczna dotycząca aplikacji mobilnej
> TOOM ma trafiać najpierw tutaj, zanim trafi do kodu. Jeśli coś tu opisane
> przestaje być prawdą (zmiana decyzji, zmiana zakresu), ten plik ma zostać
> zaktualizowany w tym samym commicie/zadaniu, a nie "przy okazji później".

## 1. Cel

Zastąpienie Telegrama jako interfejsu użytkownika dla TOOM dedykowaną
aplikacją mobilną ("TOOM Mobile"). TOOM Core (backend: FastAPI + aiogram +
SQLAlchemy, opisany w [architecture.md](architecture.md)) pozostaje bez
zmian koncepcyjnych — dochodzi do niego jedna nowa warstwa: **TOOM API**,
czyli pełne REST API wystawiające funkcje, które dziś istnieją wyłącznie
jako handlery komend Telegram.

Telegram **nie znika w Fazie 1** — zostaje jako awaryjny kanał powiadomień,
dopóki TOOM Mobile nie ma powiadomień push (patrz Faza 2). Nazwy, branding,
paleta kolorów i logo TOOM pozostają identyczne we wszystkich kanałach —
zasady w [branding.md](branding.md).

## 2. Dlaczego nie da się tego zrobić "tylko frontendem"

Zanim zaczęliśmy pisać apkę, sprawdziliśmy stan `app/api/` — dziś istnieją
tam wyłącznie `GET /health` i `POST /backup/trigger`. Cała reszta logiki
(zamówienia, magazyn, statystyki, sync, tracking, wyszukiwanie, logi) żyje
wyłącznie wewnątrz handlerów `app/bot/handlers/*.py`, wywoływanych
bezpośrednio przez aiogram. Aplikacja mobilna nie może rozmawiać z
Telegramem zamiast z użytkownikiem — potrzebuje własnego REST API.

Z tego wynika, że projekt ma **dwa równoległe tory pracy**:

1. **TOOM API** — nowa warstwa REST w istniejącym repo backendu
   (`src/`), używająca tych samych serwisów co bot (`Container` z
   `app/container.py`), bez duplikowania logiki biznesowej.
2. **TOOM Mobile** — nowa aplikacja (osobny projekt, patrz §6).

## 3. Zasady (niepodlegające dyskusji)

- **Jedno źródło prawdy dla logiki biznesowej.** API nie zawiera własnej
  logiki — woła te same serwisy (`OrdersService`/`SyncOrdersService`,
  `InventoryService`, `StatsService`, `TrackingService`, `SearchService`,
  `EventsService`, `HealthService`), które dziś wołają handlery bota.
  Jeśli czegoś serwisom brakuje, dokładamy metodę do serwisu — nigdy logiki
  wprost w endpointzie.
- **TOOM jest osobistym asystentem jednej osoby** (patrz
  `AdminOnlyMiddleware` w bocie) — API dziedziczy tę zasadę: jeden token
  dostępowy, żadnej rejestracji, żadnych kont wielu użytkowników.
- **Zero nowych zależności zewnętrznych bez potrzeby.** Backend zostaje na
  FastAPI + SQLAlchemy + Pydantic, zgodnie z istniejącym stackiem.
- **Branding jeden do jednego z `branding.md`.** Neon Lime `#C6FF00`, tło
  `#111111`, logo TOOM — bez wariacji "na telefon".
- **Styl UI: zatwierdzony wariant "Bento v2"** (patrz
  [02_appdesign.md](02_appdesign.md)) — ostateczna specyfikacja komponentów
  i typografii żyje w tamtym pliku, nie tutaj.

## 4. Zdalny dostęp — Raspberry Pi ↔ telefon

TOOM Core działa na Raspberry Pi w sieci domowej i **nie jest** wystawiony
publicznie do internetu (brak port-forwardingu, brak certyfikatu TLS na
routerze). Żeby telefon (poza siecią domową) mógł się połączyć, potrzebny
jest jeden z poniższych mechanizmów — **to decyzja użytkownika, wymaga
konta w zewnętrznej usłudze, więc nie mogę tego skonfigurować sam**:

| Opcja | Rekomendacja | Dlaczego |
|---|---|---|
| **Tailscale** (WireGuard mesh VPN) | ✅ Rekomendowane | Zero konfiguracji routera, szyfrowane end-to-end, apka na iOS/Android, RPi widoczny pod stałym adresem `100.x.x.x` niezależnie od sieci. Darmowy plan wystarcza (1 użytkownik, kilka urządzeń). |
| Cloudflare Tunnel | Alternatywa | Też nie wymaga port-forwardingu, ale wystawia usługę pod publicznym URL (większa powierzchnia ataku niż VPN mesh dla prywatnego API). |
| Port-forwarding + Caddy/TLS | Odradzane | Wymaga stałego IP lub DDNS, ręcznego zarządzania certyfikatem, i wystawia RPi bezpośrednio do internetu. |

**Rekomendacja: Tailscale.** Instalujesz `tailscale` na Raspberry Pi i na
telefonie, logujesz się tym samym kontem — apka łączy się z API pod adresem
`http://100.x.x.x:8000` (albo nazwą MagicDNS, np. `toom-pi:8000`). TOOM API
w takim modelu **nie musi** samo obsługiwać TLS — ruch jest już szyfrowany
przez WireGuard.

> Status: ⏳ do zrobienia przez użytkownika (konto Tailscale + instalacja na
> RPi). Adres API jest polem konfiguracyjnym w apce (patrz §6.4), więc nie
> blokuje to prac nad kodem.

## 5. TOOM API — kontrakt

Prefiks: `/api/v1`. Wszystkie endpointy poza `/api/v1/health` wymagają
nagłówka `Authorization: Bearer <TOOM_API_TOKEN>` (token generowany raz,
zapisany w `.env` backendu jako `TOOM_API_TOKEN`, wklejany ręcznie w apce
przy pierwszym uruchomieniu — analogicznie do wklejania tokena bota w
BotFatherze). Brak/zły token → `401`. Zły format żądania → `422`
(natywna walidacja Pydantic/FastAPI). Błąd domenowy (np.
`OrderNotFoundError`) → `404` z czytelnym komunikatem w `detail`.

| Endpoint | Metoda | Serwis źródłowy | Odpowiednik w bocie |
|---|---|---|---|
| `/api/v1/health` | GET | `HealthService` | `/health` |
| `/api/v1/dashboard` | GET | `StatsService` + `InventoryService` + `SyncStatus` | (nowy, agreguje kilka komend na potrzeby ekranu Start) |
| `/api/v1/orders` | GET `?limit=&offset=` | `SyncOrdersService.get_recent_orders` | `/orders` |
| `/api/v1/orders/{external_id}` | GET | `SyncOrdersService.get_order_by_external_id` | `/order [numer]` |
| `/api/v1/orders/search` | GET `?q=` | `SearchService` | `/search` |
| `/api/v1/orders/sync` | POST | `SyncOrdersService.sync_new_orders` | `/sync` |
| `/api/v1/orders/{external_id}/tracking` | GET | `TrackingService` | `/tracking [numer]` |
| `/api/v1/stock` | GET | `InventoryService.get_stock_overview` | `/stock` |
| `/api/v1/stock` | POST | `InventoryService.create_item` | `/stock new` |
| `/api/v1/stock/{sku}` | GET | `InventoryService` (nowa metoda `get_item`) | — |
| `/api/v1/stock/{sku}/adjust` | POST `{op,quantity,reason?}` | `set_stock`/`add_stock`/`remove_stock`/`set_min_stock` | `/stock set|add|remove|min` |
| `/api/v1/stock/{sku}/history` | GET | `InventoryService.get_history` | `/stock history` |
| `/api/v1/stock/report` | GET | `InventoryService.get_report` | `/stock report` |
| `/api/v1/stock/shopping-list` | GET | `InventoryService.get_shopping_list` | `/stock buy` |
| `/api/v1/stock/links` | POST/DELETE | `InventoryService.link_offer`/`unlink_offer` | `/stock link|unlink` |
| `/api/v1/stats` | GET | `StatsService.get_summary` | `/stats` |
| `/api/v1/logs` | GET `?limit=` | `EventsService.get_recent_events` | `/logs` |
| `/api/v1/push/vapid-public-key` | GET | `WebPushSettings` (konfiguracja) | — (nowe, Web Push) |
| `/api/v1/push/subscribe` | POST/DELETE | `PushSubscriptionRepository` | — (nowe, Web Push) |
| `/api/v1/push/test` | POST | `WebPushNotifier` | — (nowe, Web Push) |

Pełne schematy request/response (Pydantic) żyją w kodzie
(`app/api/schemas/`) — ten plik dokumentuje *zakres*, nie utrzymuje
kopii typów, żeby nie rozjeżdżały się z rzeczywistością.

## 5a. Web Push (PWA) — drugi kanał powiadomień

Poza Telegramem, TOOM ma teraz drugi, opcjonalny kanał powiadomień:
**Web Push** (RFC 8030) do TOOM Mobile uruchomionego jako PWA w
przeglądarce. Powód: natywny push na iOS wymaga płatnego konta Apple
Developer (99$/rok) — Web Push do przeglądarki działa **za darmo**, bez
żadnej zewnętrznej usługi (nie jest to Pushover/ntfy/Firebase — to
standard W3C obsługiwany bezpośrednio przez Safari od iOS 16.4).

**Architektura** (zgodnie z zasadą "jedno źródło prawdy dla logiki
biznesowej" z §3): `WebPushNotifier` implementuje ten sam interfejs
`Notifier` co `TelegramNotifier` (`app/domain/interfaces/notifier.py`) —
oba są spinane w `CompositeNotifier` (`app/infrastructure/composite_notifier.py`),
który rozgłasza każde zdarzenie do wszystkich kanałów równolegle i uznaje
wysyłkę za udaną, jeśli **choćby jeden** kanał zadziałał. `WebPushNotifier`
dołącza się automatycznie tylko, gdy w `.env` ustawiono klucze VAPID
(`Settings.web_push.enabled`) — bez kluczy jedynym kanałem pozostaje
Telegram, bez żadnych zmian w kodzie wywołującym.

**Konfiguracja backendu** — wygeneruj raz parę kluczy VAPID:

```bash
uv run python -c "
from py_vapid import Vapid02
import base64
v = Vapid02(); v.generate_keys()
priv = v.private_key.private_numbers().private_value.to_bytes(32, 'big')
print('VAPID_PRIVATE_KEY=' + base64.urlsafe_b64encode(priv).decode().rstrip('='))
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
print('VAPID_PUBLIC_KEY=' + base64.urlsafe_b64encode(pub).decode().rstrip('='))
"
```

Wklej wynik do `.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
`VAPID_CLAIM_EMAIL`) i uruchom `uv run alembic upgrade head` (migracja
`0005_create_push_subscriptions`).

**Strona apki (PWA, `mobile/`)**: `src/push/webPush.ts` rejestruje
`public/sw.js` (service worker obsługujący tylko `push`/`notificationclick`,
celowo bez cache'owania app shellu — to osobny temat, patrz Faza 3) i
wstrzykuje `<link rel="manifest">` + meta-tagi `apple-mobile-web-app-*`
wymagane przez iOS Safari, żeby "Dodaj do ekranu początkowego" otwierało
PWA w trybie standalone. Włączanie/wyłączanie i test wysyłki: karta
"Powiadomienia push" w ekranie Ustawienia (`PushNotificationsCard.tsx`),
widoczna wyłącznie w kompilacji web.

**Jak uruchomić PWA na iPhonie**: zbuduj i wystaw wersję web backendu tak,
żeby telefon mógł ją otworzyć w Safari pod tym samym adresem co TOOM API
(Tailscale) — `npx expo export -p web` w `mobile/`, wynik wystawiony jako
pliki statyczne (np. przez `StaticFiles` w FastAPI albo osobny serwer),
otwórz w Safari, "Udostępnij → Dodaj do ekranu początkowego".

## 6. TOOM Mobile — aplikacja

### 6.1 Lokalizacja w repo

Backend (`src/`) ma **własne** repozytorium git (`src/.git`) i własny cykl
wydań (Raspberry Pi, `systemd`, `uv`). Aplikacja mobilna to inny język,
inny runtime i inny cykl wydań (App Store/Play Store) — dostaje **osobny
katalog na tym samym poziomie co `src/`**:

```
toom/
├── docker/
├── docs/            <- dokumentacja ogólna repo (ten poziom)
├── scripts/
├── src/             <- TOOM Core + TOOM API (Python, osobne repo git)
├── mobile/          <- TOOM Mobile (Expo/React Native, TypeScript) - NOWY
└── tests/
```

`mobile/` dostaje własny `README.md` z instrukcją uruchomienia — nie
miesza się z `uv`/`pytest` backendu.

### 6.2 Stack technologiczny i uzasadnienie

| Warstwa | Wybór | Dlaczego |
|---|---|---|
| Framework | **Expo (React Native) + TypeScript** | Jeden kod na iOS i Android, budowa binarek bez własnego macOS (EAS Build), duże wsparcie bibliotek. Alternatywa (Flutter) też była brana pod uwagę, ale RN/Expo ma prostszy start dla jednoosobowego, osobistego projektu i łatwiejsze OTA-update (`expo-updates`) bez przechodzenia przez sklep przy drobnych poprawkach. |
| Nawigacja | `@react-navigation` (bottom tabs + native stack) | Standard w ekosystemie RN, zgodny z projektem UI (dolna nawigacja z 02_appdesign.md). |
| Stan/dane serwerowe | `@tanstack/react-query` | Cache, refetch, pull-to-refresh i stany ładowania/błędu "za darmo" — kluczowe dla ekranu z danymi live z Allegro. |
| Wykresy | `react-native-svg` (sparkline rysowany ręcznie, zgodnie z mockupem) | Mockup używa prostej polylinii — nie potrzeba całej biblioteki wykresów na start. |
| Bezpieczne przechowywanie tokena | `expo-secure-store` (natywnie), `localStorage` (web) | Token API w Keychain/Keystore na iOS/Androidzie. **Uwaga:** `expo-secure-store` nie ma działającej implementacji web (rzuca błąd przy każdym wywołaniu) — `src/utils/secureStorage.ts` przełącza się na `localStorage` na `Platform.OS === "web"`, jedyny realistyczny odpowiednik w przeglądarce. |
| Ikony | Wektorowe SVG 1:1 z mockupu (`react-native-svg`), nie biblioteka ikon "z automatu" | Zachowanie dopracowanego stylu ikon ustalonego w mockupie, bez podmiany na generyczny zestaw. |

### 6.3 Mapa ekranów (zgodna z zatwierdzonym mockupem "Bento v2")

1. **Logowanie / parowanie** — pole na adres API (Tailscale) + token,
   zapisywane w `expo-secure-store`. Ekran pokazuje się tylko przy braku
   zapisanego tokena.
2. **Start** (`/`) — hero sprzedaży dnia + sparkline + trend, dwie karty
   (niski stan / do wysłania), status synchronizacji, podgląd ostatnich
   zamówień, podgląd magazynu.
3. **Zamówienia** — lista (nieskończone przewijanie / `limit`+`offset`),
   wyszukiwarka (`/orders/search`), pull-to-refresh, przycisk "Synchronizuj
   teraz".
4. **Szczegóły zamówienia** — dane kupującego, produkty, status, przycisk
   "Sprawdź przesyłkę" (`/orders/{id}/tracking`, pobierane na żądanie, tak
   jak dziś w bocie — **nie** cache'ujemy statusu przesyłki trwale).
5. **Magazyn** — pasek podsumowania (wartość, liczba produktów, poniżej
   minimum), wyszukiwarka, filtry (Wszystkie / Niski stan / Bez sprzedaży /
   Zestawy), lista produktów z paskiem stanu.
6. **Szczegóły produktu magazynowego** — korekta stanu (set/add/remove),
   ustawienie minimum, historia zmian, mapowania ofert (link/unlink).
7. **Statystyki** — dziś / miesiąc / łącznie (`/stats`), raport magazynowy
   (`/stock/report`): niski stan, prognoza wyczerpania, produkty bez
   sprzedaży.
8. **Ustawienia** — adres API, token (podgląd/zmiana), wylogowanie
   (czyszczenie sesji — Keychain/Keystore na natywnych platformach,
   `localStorage` na webie, patrz §6.2), karta "Powiadomienia push"
   (włącz/wyłącz + testowa wysyłka, tylko web/PWA, patrz §5a), link do
   `/logs` (ostatnie zdarzenia systemowe).

### 6.4 Konfiguracja środowiska w apce

Adres API **nie jest** zaszyty na sztywno w kodzie (RPi w sieci Tailscale
ma zmienny, prywatny adres zależny od instalacji użytkownika) — jest polem
w ekranie logowania, zapisywanym lokalnie. Domyślna wartość placeholder:
`http://toom-pi:8000` (MagicDNS Tailscale).

### 6.5 Wdrożenie 24/7 na Raspberry Pi (bez zależności od komputera)

Cel: telefon ma się łączyć wyłącznie z Raspberry Pi — appka webowa (PWA)
**i** TOOM API mają działać z tego samego procesu/portu, żeby wystarczył
jeden `systemd` service i jeden wpis `tailscale serve` (bez trzymania
`npx expo start` wiecznie odpalonego na czyimś komputerze).

**Backend** (`app/main.py`, `_create_fastapi_app`): gdy zmienna
`WEB_APP_DIST_PATH` w `.env` wskazuje na folder ze zbudowaną wersją
TOOM Mobile, backend montuje go jako `StaticFiles("/")` **po**
zarejestrowaniu `api_router` — dzięki kolejności rejestracji ścieżki API
(`/api/v1/*`, `/health`, `/docs`) mają pierwszeństwo, a mount na `/` łapie
resztę (HTML, JS bundle, `manifest.json`, `sw.js`, `icon.png`) jako
fallback. Brak zmiennej (domyślnie) = backend serwuje wyłącznie API, bez
zmiany zachowania.

**Proces wdrożenia** (jednorazowo, potem tylko przy zmianach w `mobile/`):

1. Zbuduj statyczną wersję appki **na komputerze** (Raspberry Pi nie
   potrzebuje Node.js/Expo do niczego poza tym krokiem, a i to można zrobić
   gdzie indziej):
   ```bash
   cd mobile
   npx expo export -p web
   ```
   Wynik ląduje w `mobile/dist/`.
2. Skopiuj `mobile/dist/` na Raspberry Pi, np.:
   ```bash
   scp -r mobile/dist pi@<host>:~/toom/webapp_dist
   ```
3. W `.env` na Raspberry Pi ustaw:
   ```
   WEB_APP_DIST_PATH=/home/pi/toom/webapp_dist
   ```
4. Zrestartuj usługę (`sudo systemctl restart toom`).
5. `tailscale serve --bg --https=443 http://localhost:8000` — **jeden**
   wpis wystarcza teraz na wszystko (wcześniej, w wersji deweloperskiej z
   osobnym `npx expo start --web`, potrzebne były dwa porty/dwa wpisy).
6. Na telefonie: Safari → `https://<nazwa-pi>.<tailnet>.ts.net` → Dodaj do
   ekranu początkowego. Adres API w ekranie logowania to **ten sam** adres
   (appka i API są teraz tym samym originem, więc CORS nawet nie wchodzi
   w grę przy typowym użyciu — middleware zostaje jako zabezpieczenie na
   wypadek dostępu z innego originu, np. w trybie deweloperskim).

**Aktualizacja appki później**: powtórz kroki 1-2 (eksport + kopiowanie) -
to tylko pliki statyczne, restart usługi nie jest nawet konieczny (chyba
że zmieniło się coś w samym backendzie).

## 7. Fazy realizacji

| Faza | Zakres | Status |
|---|---|---|
| **0** | Wybór stylu UI (mockup) | ✅ zatwierdzone — wariant "Bento v2" |
| **1** | TOOM API (wszystkie endpointy z §5) + TOOM Mobile: ekrany Start / Zamówienia / Magazyn / Statystyki, logowanie tokenem, dane live | 🚧 w budowie |
| **2** | Powiadomienia push jako odpowiednik dzisiejszych powiadomień Telegram (`TelegramNotifier`) | 🚧 częściowo: **Web Push (PWA) zrobiony** (`WebPushNotifier` + `CompositeNotifier`, patrz §5a) — darmowy, działa już dziś na iOS/Android przez przeglądarkę. Natywny push (Expo Push) do zbudowanej binarki (EAS Build) wciąż ⏳ nie zaczęty — potrzebny tylko, jeśli/gdy zdecydujemy się na płatny build zamiast PWA. |
| **3** | Tryb offline (cache `react-query` + wskaźnik "dane sprzed X min" gdy brak połączenia z RPi) | ⏳ zaplanowane, nie zaczęte |
| **4** | Wygaszenie Telegrama jako głównego kanału (zostaje jako fallback powiadomień awaryjnych, np. gdy push się nie dostarczy) | ⏳ zależne od Fazy 2 |

## 8. Co NIE wchodzi w zakres (świadomie)

- Wielu użytkowników/kont — TOOM jest i zostaje asystentem jednej osoby.
- Publiczne wystawienie API do internetu bez VPN.
- Zmiana logiki biznesowej backendu — API tylko ją **udostępnia**.
- Natywne moduły spoza Expo Managed Workflow, chyba że coś wymusi "eject"
  (na dziś żadna z wybranych bibliotek tego nie wymaga).

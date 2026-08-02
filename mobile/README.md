<p align="center">
  <img src="../src/assets/branding/logo.png" alt="ORDLY" width="220">
</p>

# ORDLY Mobile

Aplikacja mobilna (Expo/React Native + TypeScript), zastępująca Telegram
jako interfejs użytkownika dla ORDLY. Rozmawia z **ORDLY API** (`/api/v1/*`)
wystawionym przez backend w [`../src/`](../src/).

Zanim zaczniesz cokolwiek zmieniać w tym projekcie, przeczytaj:
- [`../src/docs/01_app.md`](../src/docs/01_app.md) — zakres, kontrakt API, fazy realizacji.
- [`../src/docs/02_appdesign.md`](../src/docs/02_appdesign.md) — kolory, typografia, komponenty, zasady UI.

## Wymagania

- Node.js 18+ i npm
- [Expo Go](https://expo.dev/go) na telefonie (najszybszy sposób testowania
  bez budowania natywnej binarki) **albo** Android Studio / Xcode dla
  emulatora, **albo** przeglądarka (patrz sekcja PWA/iPhone poniżej)
- Uruchomiony backend ORDLY (`../src/`) z ustawionym `ORDLY_API_TOKEN`
  w `.env` — patrz [`../src/README.md`](../src/README.md)

## Instalacja i uruchomienie

```bash
cd mobile
npm install
npx expo start
```

Zeskanuj kod QR aplikacją Expo Go (Android) lub aparatem (iOS, otwiera
Expo Go automatycznie). Aplikacja i telefon muszą widzieć ORDLY API pod tym
samym adresem — patrz sekcja "Zdalny dostęp" w `01_app.md` §4 (rekomendacja:
Tailscale).

## Pierwsze logowanie

Przy pierwszym uruchomieniu aplikacja poprosi o:
1. **Adres API**, np. `http://ordly-pi:8000` (Tailscale MagicDNS) albo
   `http://192.168.x.x:8000` (ta sama sieć lokalna).
2. **Token** — wartość `ORDLY_API_TOKEN` z pliku `.env` backendu.

Oba są zapisywane lokalnie (Keychain/Keystore na iOS/Androidzie,
`localStorage` na webie — patrz `src/utils/secureStorage.ts`). Wylogowanie
(ekran Ustawienia) je usuwa.

## PWA na iPhonie + powiadomienia push (za darmo, bez konta Apple Developer)

ORDLY Mobile działa też jako **Progressive Web App** w Safari, z prawdziwymi
powiadomieniami push (Web Push, RFC 8030) — bez płacenia Apple'owi za
Developer Program. Szczegóły architektury: `01_app.md` §5a.

```bash
npx expo start --web
```

1. Wygeneruj klucze VAPID i wpisz je do `.env` backendu (patrz
   `01_app.md` §5a) - bez nich karta "Powiadomienia push" w Ustawieniach
   pokaże, że backend nie jest jeszcze skonfigurowany.
2. Do realnego użycia (nie tylko dev-server) zbuduj statyczną wersję:
   `npx expo export -p web` i wystaw wynikowy folder `dist/` tam, gdzie
   telefon go zobaczy (np. przez Tailscale, obok ORDLY API).
3. Na iPhonie: otwórz adres w Safari → **Udostępnij → Dodaj do ekranu
   początkowego**. Otwórz appkę z ekranu głównego (nie z Safari) i w
   Ustawieniach włącz "Powiadomienia push".

## Struktura katalogów

```
mobile/
├── App.tsx                 # punkt wejścia: providery + nawigacja + PWA head tags
├── public/                 # manifest.json, sw.js, icon.png - kopiowane 1:1 do web builda
├── src/
│   ├── api/                # klient HTTP, sesja, hooki react-query, typy odpowiedzi
│   ├── components/         # komponenty współdzielone (karty, wiersze, stany)
│   ├── icons/               # zestaw ikon SVG 1:1 z 02_appdesign.md §4
│   ├── navigation/          # RootNavigator (stack) + MainTabs (dolna nawigacja)
│   ├── push/                # Web Push (rejestracja SW, subskrypcja) - tylko Platform.OS==="web"
│   ├── screens/             # ekrany: Login, Home, Orders, OrderDetail, Stock, StockItem, Stats, Settings
│   ├── store/               # AuthProvider (sesja: adres API + token)
│   ├── theme/                # tokeny kolorów i typografii (źródło: 02_appdesign.md)
│   └── utils/                # formatowanie kwot/dat, secureStorage (native+web)
```

## Sprawdzanie typów

```bash
npm run typecheck
```

## Stan weryfikacji

Zweryfikowane w tej sesji, naprawdę uruchomione (nie tylko przejrzane):
- `npm install` (1186+ pakietów) i `npm run typecheck` — czysto.
- `npx expo start --web` uruchomiony i sprawdzony w przeglądarce: ekran
  logowania renderuje się, błąd sieciowy pokazuje poprawny komunikat,
  `manifest.json`/`sw.js`/`icon.png` serwowane poprawnie, service worker
  faktycznie się rejestruje.
- Po drodze wyłapany i naprawiony realny błąd: `expo-secure-store` nie ma
  działającej implementacji web (rzuca wyjątek) — stąd
  `src/utils/secureStorage.ts` z fallbackiem na `localStorage`.

Niezweryfikowane w tej sesji (wymaga fizycznego telefonu):
- Natywna kompilacja iOS/Android przez Expo Go.
- Faktyczne dostarczenie powiadomienia Web Push na prawdziwy iPhone
  (backend do testu potrzebuje realnego, publicznie osiągalnego adresu -
  w tej sesji nie uruchamiałem pełnego `app.main`, bo używa prawdziwych
  danych z `.env` - tokena bota Telegram i danych Allegro - i uruchomienie
  go wywołałoby realne wywołania zewnętrznych API).

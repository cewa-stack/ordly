# APPPLANS 00 — OVERVIEW ARCHITEKTURY (Cewastack / Allegro Manager)

> Ten plik jest punktem wejścia. Claude Code powinien przeczytać go PRZED rozpoczęciem pracy nad
> jakimkolwiek modułem z plików `appplans_01` … `appplans_06`. Każdy kolejny plik zakłada, że
> decyzje architektoniczne opisane tutaj zostały zaakceptowane i wdrożone jako fundament.

## 1. Stan obecny (baseline)

- **Desktop app** ("Cewastack" / "Allegro Manager"): Electron + React + TypeScript + Vite +
  TailwindCSS. OAuth2 PKCE do Allegro obsługiwany wyłącznie w main procesie
  (`electron/allegroAuth.js`), redirect URI `http://localhost:53682/auth/callback`.
  Komunikacja renderer ↔ main wyłącznie przez `contextBridge` (IPC), zero bezpośrednich
  wywołań API z rendera (unikanie CORS + bezpieczeństwo tokenów).
- **Backend Raspberry Pi ("Comcio")**: Python 3.12, FastAPI, aiogram, SQLAlchemy 2.0 (async),
  APScheduler, Loguru, uv jako package manager. Działa jako `systemd` service
  (`comcio-assistant.service`) na Raspberry Pi OS 64-bit **Desktop/full** (nie Lite).
  SQLite w trybie WAL, tokeny OAuth2 Allegro szyfrowane Fernetem, backup przez `VACUUM INTO`.
  Architektura pluginowa (dodanie nowego marketplace = nowy folder pluginu, zero zmian w core).

## 2. Kluczowa decyzja architektoniczna: Raspberry Pi = jedyne źródło prawdy

To jest **najważniejsza zasada** dla wszystkich modułów poniżej:

- **Comcio (RPi)** jest jedynym procesem, który odpytuje zewnętrzne API (Allegro, OLX, IMAP).
  Robi to raz na 60s (patrz `appplans_02`), zapisuje wynik do SQLite i emituje eventy.
- **Desktop app** NIE wykonuje własnego pollingu Allegro/OLX. Łączy się z Comcio przez REST +
  WebSocket i tylko odczytuje/aktualizuje dane.
- **Mobile app** analogicznie — tylko klient Comcio, zero własnej logiki synchronizacji.

Powód: Allegro i OLX mają limity rate-limit per token/per IP. Trzy niezależne pollery
(desktop, mobile, RPi) szybko doprowadzą do 429 i zablokowanych tokenów. Jeden centralny
scheduler eliminuje ten problem i upraszcza deduplikację powiadomień.

```
                    ┌─────────────────────┐
                    │   Allegro API        │
                    │   OLX API / partner   │
                    │   IMAP (poczta)       │
                    └──────────┬───────────┘
                               │ polling co 60s (APScheduler)
                    ┌──────────▼───────────┐
                    │   Comcio (RPi)        │
                    │   FastAPI + SQLite    │
                    │   WebSocket hub       │
                    │   FCM/push sender     │
                    └───┬───────────────┬───┘
                        │ REST+WS       │ push (FCM)
              ┌─────────▼───┐     ┌─────▼──────┐
              │ Desktop app │     │ Mobile app │
              │ (Electron)  │     │ (Expo/RN)  │
              └─────────────┘     └────────────┘
```

## 3. Wymagana rozbudowa Comcio (wspólna dla wszystkich modułów)

Zanim zacznie się wdrażanie modułów 01-06, w Comcio trzeba dodać:

1. **WebSocket hub** (`app/api/ws.py`) — endpoint `/ws/events`, broadcast eventów typu
   `stock_changed`, `new_order`, `return_opened`, `dispute_opened`, `new_mail`.
2. **Warstwa REST API dla klientów** (`app/api/v1/`) — wersjonowane endpointy, osobne od
   wewnętrznej logiki pluginów. To jest kontrakt, którego desktop i mobile będą używać.
3. **Tabela `notifications`** w SQLite — log wszystkich wysłanych powiadomień (dedupe +
   historia na mobile).
4. **Auth między aplikacjami a Comcio**: prosty API key / JWT wydawany przy parowaniu
   urządzenia (desktop i telefon muszą się "sparować" z RPi przy pierwszym uruchomieniu —
   QR code z adresem IP + kluczem, wyświetlony w Comcio przy starcie, zeskanowany w mobile app).

Szczegóły implementacyjne każdego z powyższych — patrz odpowiednie pliki modułów, bo
przenikają się z konkretnymi funkcjami (np. WebSocket hub jest rozwijany razem z `appplans_02`).

## 4. Kolejność wdrażania (ważne — nie przeskakiwać)

| # | Moduł | Plik | Zależy od |
|---|-------|------|-----------|
| 1 | Sync engine (60s) + WebSocket hub | `appplans_02_sync_engine.md` | fundament z pkt 3 |
| 2 | Zwroty / anulowane / dyskusje Allegro | `appplans_04_returns_cancellations_disputes.md` | modułu 1 |
| 3 | Mail hurtownia (przycisk "napisz maila") | `appplans_03_wholesaler_email.md` | brak (niezależny) |
| 4 | Unified inbox (mail Allegro/OLX) | `appplans_06_unified_mail_inbox.md` | modułu 1 |
| 5 | OLX integracja | `appplans_05_olx_integration.md` | modułu 1 |
| 6 | Aplikacja mobilna (powiadomienia + stan magazynowy) | `appplans_01_mobile_companion_app.md` | modułów 1, 2 |

Powód takiej kolejności: sync engine i WebSocket hub to fundament, na którym stoi wszystko
inne. Mail do hurtowni jest w pełni niezależny, więc można go zrobić "w międzyczasie" jako
szybki win. Mobile app jest na końcu, bo wymaga stabilnego API kontraktu z punktów 1-2.

## 5. Zasady jakości (obowiązują we wszystkich modułach)

- Każda nowa funkcja: najpierw typy/interfejsy (TS) lub Pydantic modele (Python), potem
  implementacja, na końcu testy.
- Żadnych `any` w TypeScript. Żadnych gołych `except:` w Pythonie — zawsze konkretny wyjątek +
  `logger.exception(...)`.
- Każdy nowy endpoint REST: happy path + walidacja błędnych danych + test timeout/retry przy
  wołaniu zewnętrznego API.
- Migracje bazy danych: zawsze przez Alembic (jeśli jeszcze nie ma — dodać w module 02 jako
  krok zerowy), nigdy ręczne `ALTER TABLE` bez wersjonowania.
- Sekrety (klucze API, hasła SMTP, tokeny) — zawsze w `.env`, nigdy w kodzie ani w gicie.
- Każdy moduł kończy się sekcją "Definition of Done" w swoim pliku — Claude Code ma się do
  niej odnieść zanim uzna zadanie za zakończone.

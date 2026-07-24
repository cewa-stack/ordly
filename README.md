<!-- Logo TOOM: podmień plik assets/branding/logo.png, aby zaktualizować logo -->
<p align="center">
  <img src="assets/branding/logo.png" alt="TOOM" width="320">
</p>

# TOOM

**Personal Commerce Intelligence Platform**

Osobisty asystent sprzedaży e-commerce działający 24/7 na Raspberry Pi 4,
zbudowany zgodnie z Clean Architecture i architekturą pluginów.
Bot Telegram występuje pod nazwą **TOOM**.

## Spis treści

- [Architektura](#architektura)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Konfiguracja](#konfiguracja)
- [Uruchomienie](#uruchomienie)
- [Struktura folderów](#struktura-folderów)
- [Dodawanie nowego marketplace](#dodawanie-nowego-marketplace)
- [Backup i odzyskiwanie](#backup-i-odzyskiwanie)
- [Aktualizacja](#aktualizacja)
- [Testy](#testy)
- [Deployment](#deployment)
- [Jakość kodu](#jakość-kodu)
- [Branding](#branding)

## Architektura

Projekt zbudowany jest zgodnie z Clean Architecture i architekturą
pluginów - szczegóły w [docs/architecture.md](docs/architecture.md).

Kluczowe zasady:
- Logika biznesowa (`domain/`, `services/`) nie zależy od żadnego
  konkretnego marketplace.
- Allegro to plugin implementujący interfejs `MarketplacePlugin` -
  dodanie Amazon/eBay/Shopify wymaga jedynie nowego folderu w
  `infrastructure/plugins/`, bez zmiany istniejącego kodu.
- Komunikacja między modułami odbywa się przez Event Bus.
- Cała aplikacja wykorzystuje Dependency Injection przez `app/container.py`.

## Wymagania

- Raspberry Pi 4 Model B (4GB) z SSD podłączonym przez USB 3.0
- Raspberry Pi OS 64-bit (pełna wersja, nie Lite)
- Python 3.13 (instalowany przez `uv`)
- Konto deweloperskie Allegro (produkcyjne lub sandbox)
- Bot Telegram (utworzony przez [@BotFather](https://t.me/BotFather)) -
  nazwij go np. "TOOM"

## Instalacja

Pełna instrukcja przygotowania Raspberry Pi znajduje się w
[docs/deployment.md](docs/deployment.md). Skrócona wersja:

```bash
git clone https://github.com/TWOJA_NAZWA/toom.git
cd toom
uv sync
cp .env.example .env
# Uzupełnij .env swoimi danymi (patrz sekcja Konfiguracja)
uv run alembic upgrade head
```

## Konfiguracja

Wszystkie zmienne środowiskowe opisane są w `.env.example`. Kluczowe kroki:

1. **Allegro**: zarejestruj aplikację na
   https://apps.developer.allegro.pl/ (typ "Allegro Auth Code with PKCE"),
   redirect URI: `http://localhost:53682/auth/callback`.
2. **Telegram**: utwórz bota przez @BotFather (np. pod nazwą TOOM),
   pobierz token, oraz swój `chat_id` (np. przez
   [@userinfobot](https://t.me/userinfobot)).
3. **Klucz szyfrowania tokenów**:
   ```bash
   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

## Uruchomienie

### Pierwsza autoryzacja Allegro (jednorazowo)

Przy pierwszym uruchomieniu aplikacja poprosi o autoryzację OAuth2 -
otwórz wyświetlony link w przeglądarce i zaloguj się na konto Allegro.

### Uruchomienie testowe

```bash
uv run python -m app.main
```

### Uruchomienie produkcyjne (systemd)

Zobacz [docs/deployment.md](docs/deployment.md).

## Struktura folderów

```
src/app/
├── api/               # Endpointy FastAPI (health, backup)
├── bot/                # Komendy i middleware Telegram (bot TOOM, aiogram)
├── core/               # Konfiguracja, logowanie, Event Bus
├── database/            # Silnik SQLAlchemy, modele ORM
├── domain/              # Encje biznesowe i interfejsy (serce aplikacji)
├── infrastructure/       # Pluginy marketplace, integracja Telegram
├── repositories/         # Implementacje dostępu do danych (SQLite)
├── scheduler/            # Zadania cykliczne (APScheduler)
├── services/             # Logika aplikacyjna (use cases)
├── shared/               # DTO współdzielone między warstwami
└── utils/                # Funkcje pomocnicze
```

Pełny opis każdego folderu: [docs/architecture.md](docs/architecture.md).

## Dodawanie nowego marketplace

Zobacz [docs/adding_new_marketplace.md](docs/adding_new_marketplace.md).

## Backup i odzyskiwanie

```bash
./scripts/backup_db.sh
./scripts/restore_db.sh backups/toom_manual_20260717_030000.db
```

Szczegóły: [docs/backup.md](docs/backup.md).

## Aktualizacja

```bash
cd toom
sudo systemctl stop toom
git pull
uv sync
uv run alembic upgrade head
sudo systemctl start toom
sudo systemctl status toom
```

## Testy

```bash
uv run pytest -v
uv run pytest --cov=app --cov-report=term-missing
```

## Deployment

Pełna instrukcja: [docs/deployment.md](docs/deployment.md).

## Jakość kodu

```bash
uv run black src/ tests/
uv run ruff check src/ tests/
uv run mypy src/
uv run pre-commit run --all-files
```

## Branding

Zasoby marki (logo, paleta kolorów) znajdują się w
[assets/branding/](assets/branding/). Kolor przewodni: Neon Lime
`#C6FF00` na tle `#111111`. Szczegóły: [docs/branding.md](docs/branding.md).

## Magazyn (IMS)

TOOM zawiera Inventory Management System - centralny magazyn produktów
niezależny od marketplace. Stany są automatycznie synchronizowane po
każdym zamówieniu, anulowaniu i zwrocie (z ochroną przed podwójnym
odjęciem), a przy osiągnięciu minimalnego stanu bot wysyła ostrzeżenie
i dodaje produkt do listy zakupów.

Najważniejsze komendy:

```
/stock                      # aktualny stan magazynu
/stock new PET60 Butelka    # nowy produkt
/stock set|add|remove PET60 100
/stock min PET60 20         # próg ostrzeżeń
/stock report               # raport z prognozą zapasów
/stock buy                  # lista zakupów
/stock history [SKU]        # historia zmian
/stock link 12345678 PET60 2  # mapowanie oferty (zestawy)
```

Oferty marketplace są dopasowywane do produktów magazynowych po
mapowaniu `/stock link` (obsługa zestawów wieloskładnikowych), a gdy go
brak - po SKU równym identyfikatorowi produktu z oferty. Odejmowanie
składników zestawu jest w pełni transakcyjne (savepoint) - błąd przy
którymkolwiek składniku wycofuje całą operację.

## Automatyzacje

TOOM wykonuje kilka zadań automatycznie, opartych na etapie realizacji
zamówienia (`fulfillment_status` z Allegro: NEW → PROCESSING → SENT):

- **SMS o pakowaniu** - gdy zamówienie wchodzi w etap pakowania
  (PROCESSING), klient otrzymuje jednorazowy SMS. Domyślnie działa bramka
  testowa (`SMS_PROVIDER=logging`) logująca treść; realnego operatora
  podłącza się nową implementacją `SmsProvider`.
- **Przypomnienie o wysyłce (20:00)** - jeśli któreś z dzisiejszych
  zamówień nie zostało jeszcze wysłane, bot wysyła listę do spakowania.
  Gdy wszystko wysłane (lub brak zamówień) - nie wysyła nic.
- **Nocne czyszczenie czatu (02:00)** - usuwa wszystkie wcześniejsze
  wiadomości bota i publikuje ponownie wyłącznie aktualne (nowe/pakowane)
  zamówienia, aby rano czat pokazywał tylko to, co wymaga obsługi.

## Aplikacja mobilna (TOOM Mobile)

Telegram jest stopniowo zastępowany dedykowaną aplikacją mobilną. Backend
zyskuje w tym celu pełne REST API (`/api/v1/...`, zabezpieczone tokenem
`TOOM_API_TOKEN`) obok istniejącego bota. Plan projektu i system
projektowy aplikacji:

- [docs/01_app.md](docs/01_app.md) — zakres, architektura, kontrakt API, fazy.
- [docs/02_appdesign.md](docs/02_appdesign.md) — kolory, typografia, komponenty.

Kod aplikacji: [`../mobile/`](../mobile/) (osobny projekt Expo/TypeScript,
poza tym repozytorium Python).

Drugi, opcjonalny kanał powiadomień obok Telegrama: **Web Push** do TOOM
Mobile uruchomionego jako PWA (za darmo, bez konta Apple Developer) -
`WebPushNotifier` + `CompositeNotifier`, konfiguracja kluczy VAPID opisana
w [docs/01_app.md](docs/01_app.md) §5a.

## Status projektu

✅ Backend (Etapy 1-16) w pełni funkcjonalny · 🚧 TOOM API + TOOM Mobile w budowie

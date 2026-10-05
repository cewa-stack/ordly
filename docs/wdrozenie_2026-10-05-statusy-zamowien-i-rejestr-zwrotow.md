# ORDLY — 5 października 2026: statusy zamówień, podzakładki i rejestr zwrotów

Cztery pozycje z Notion (ORDLY - APP Features Notes) i dwie poprawki od Fixera w jednej paczce.

**Co zmienia ta paczka:**

1. **Ręczny status zamówienia w aplikacji** (Nowe / W realizacji / Zrealizowane / Anulowane) — tylko w ORDLY, bez wywołań Allegro. Ręczny status wygrywa ze statusem Allegro; synchronizacja uzgadnia tylko „do przodu”; „Przywróć status z Allegro” kasuje ręczną zmianę. Zrealizowane i Anulowane znikają z licznika „do spakowania”, plakietki, raportu 9:00, przypomnienia 20:00 i nie generują push/Telegram/SMS. Desktop: sekcja „Status w aplikacji”, „Ustaw status” dla zaznaczonych. Telefon i bot: podgląd.
2. **Podzakładki zamówień** „Wszystkie | Nowe | W realizacji | Zrealizowane” z licznikami (desktop i telefon), zamiast filtrów „Do spakowania / Gotowe do wysyłki / Wysłane”.
3. **Rejestr anulowań i zwrotów pieniędzy** (`customer_cases`): data, numer zamówienia, powód, status obsługi, login Allegro. Bez telefonu, e-maila i imienia kupującego (decyzja D7). Uzupełnienie wsteczne w migracji. Desktop: sekcja „Anulowania i zwroty pieniędzy” z filtrami i edycją.
4. **Zwroty i anulowane w podzakładkach** „Zgłoszony | W trakcie realizacji | Zakończony” (desktop i telefon).

5. **Poprawka desktop (Fixer):** karta powitalna na Starcie rośnie z treścią (`min-h-[204px]`, `py-5`) zamiast ucinać etykietę i przyciski przy krawędzi.
6. **Poprawka telefon (Fixer):** list przewozowy na ekranie blokady na całą szerokość ekranu i wyśrodkowany w wolnym miejscu (`LockScreen.tsx`).

**Migracje: TAK** — `0014` (hub_events, już na Pi) -> `0015` (order_app_status) -> `0016` (customer_cases). **Nowych zależności i zmiennych `.env`: brak.** **Backend + PWA + desktop.**

## Kontrola przed wdrożeniem (release manager)

- Merge `feat/zwroty-podzakladki` (zawiera 4 gałęzie, 3879d60) do `main`: fast-forward, jeden head Alembic `0016`.
- pytest 766 passed; ruff OK; mypy 35 błędów (wszystkie znane sprzed zmian); desktop i mobile typecheck OK.
- Migracja na czystej bazie: upgrade do `0016`, downgrade do `0014`, upgrade — OK.
- Push feat: `063f4bb..3879d60 main -> main`. **Commit do rollbacku: `063f4bb`.**
- Dołożone poprawki Fixera: merge `fix/desktop-karta-powitalna-krawedzie` (ca774b8) i `fix/mobile-list-przewozowy-dopasowanie` (b9c5426); w historii main nie ma 42f9298 (gałąź `fix/desktop-karta-powitalna-odstepy` pominięta). Desktop i mobile typecheck OK, jeden head `0016`.
- Lokalnie komendy `uv run pytest` / `uv run alembic` milczą — działa `uv run python -m ...`.

## Rollback

`sudo systemctl stop ordly`, `cd ~/ordly/backend`, `uv run alembic downgrade 0014` (usuwa statusy ręczne i rejestr zwrotów z ręcznymi powodami), `git checkout 063f4bb`, `uv sync`, `sudo systemctl start ordly`, potem `git checkout main`. Poprzednia paczka PWA i .exe z `063f4bb`.

## Do zgłoszenia w trackerze

`map_checkout_form_to_order` (`backend/src/app/infrastructure/plugins/allegro/mapper.py`) bierze datę zamówienia z `updatedAt` przed `boughtAt`.

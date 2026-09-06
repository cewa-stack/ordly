# ORDLY — 7 września 2026: katalog pobiera tylko aktywne oferty

**Zmiana 1 (dotyczy aplikacji):** magazyn pobierał z Allegro wszystkie
oferty, łącznie z zakończonymi. Teraz `GET /sale/offers` pyta Allegro
tylko o oferty ze statusem `ACTIVE` lub `ACTIVATING` (w trakcie
wystawiania) — zakończone w ogóle nie schodzą.

**Bez migracji bazy.** Zmiana jest wyłącznie w kodzie backendu (filtr
w zapytaniu do Allegro) plus drobne sprzątanie w desktopie (usunięta
martwa etykieta „zakończona" — i tak nigdy by się już nie pokazała, bo
backend takich ofert nie zwróci). Przebudowa `.exe` jest więc opcjonalna;
bez niej nic w aplikacji nie wygląda ani nie działa inaczej.

**Zmiana 2 (dotyczy tylko testów, nic nie wdrażasz):** naprawiony test
`test_dzisiejsza_data_trafia_do_system_promptu`, który sam był zepsuty —
porównywał datę z Ordlaka (liczoną w czasie polskim, `local_now()`)
z datą UTC (`utc_now()`). Latem różnica to 2 godziny, więc między 22:00
a 23:59 UTC test fałszywie padał, mimo że asystent pokazywał poprawną,
polską datę. Kod aplikacji się nie zmienił — poprawiony jest sam test.
Ta zmiana **nie wymaga żadnego kroku na Pi** (testy tam nie działają),
jedzie tylko razem w commicie dla porządku w repo.

> To poprawka do wdrożenia z 6 września (`docs/wdrozenie_2026-09-06-katalog-allegro.md`)
> — jeśli tamta paczka jest już na Pi, ta wymaga tylko `git pull` + restart.

---

## CZĘŚĆ A — na komputerze

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Commit i push

```bash
git add backend desktop docs
```

```bash
git commit -m "Katalog Allegro pobiera tylko oferty aktywne i naprawa testu daty Ordlaka"
```

```bash
git push origin main
```

---

## CZĘŚĆ B — Raspberry Pi (przez SSH)

### B1. Połącz się i wejdź do backendu

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### B2. Sprawdź, czy nic nie blokuje pobrania

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env`):

```bash
git restore .
```

### B3. Pobierz i zrestartuj

**Migracji nie ma** — pomiń krok `alembic upgrade`.

```bash
git pull
```

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager
```

### B4. Sprawdź, że wraca mniej ofert

Token (skopiuj wartość z `{"token":"..."}`):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Pobierz katalog ponownie (wklej token zamiast `TU_TOKEN`):

```bash
curl -s -X POST http://localhost:8000/api/v1/stock/catalog/sync -H "Authorization: Bearer TU_TOKEN"
```

Liczba przy `"fetched"` powinna teraz być **mniejsza lub równa** tej
sprzed poprawki (albo taka sama, jeśli nie masz żadnych zakończonych
ofert) — nigdy większa.

---

## CZĘŚĆ C — w aplikacji (opcjonalnie)

Jeśli chcesz zobaczyć posprzątany kod w desktopie (wizualnie nic się nie
zmieni — usunięta etykieta i tak nigdy się nie pokazywały):

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`. **Nieobowiązkowe** —
możesz to pominąć, backend już filtruje sam.

---

## Czego ta paczka NIE zmienia

- **Nie usuwa już pobranych zakończonych ofert z bazy Pi.** Kolejne
  „Pobierz z Allegro" (albo B4 wyżej) nadpisuje cały katalog świeżą,
  odfiltrowaną listą — więc znikną przy najbliższej synchronizacji, nie
  same z siebie.
- **Nie rusza listy „Sprzedają się bez powiązania"** w zakładce
  Powiązania ofert — ta pochodzi z historii zamówień, nie z katalogu,
  więc zakończone oferty sprzed poprawki dalej tam są i dalej da się im
  zrobić korektę wsteczną.

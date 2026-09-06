# ORDLY — wdrożenie zmian z 6 września 2026

Ta paczka to dwie rzeczy, **obie wyłącznie w aplikacji desktopowej**:

1. **Ręczne wpisanie stanu magazynowego.** Dotąd jedyną drogą do zmiany
   zapasu było klikanie `+` i `−` po jednej sztuce — dostawa 500 butelek
   oznaczała 500 kliknięć. Teraz liczba w kolumnie **Korekta** jest
   klikalna (podkreślona kropkowaną linią) i otwiera okno **Korekta
   stanu** z trzema trybami: *Ustaw stan*, *Dostawa (+)*, *Zdejmij (−)*.
   Można też dopisać powód, który trafia do historii ruchów.
2. **Nowa ikona aplikacji** — Ordi z podkładką, plik przekazany jako
   `ordly_app_icon.ico`. Wchodzi na `.exe`, instalator, skrót na pulpicie
   i pasek zadań.

> **Pi NIE wymaga aktualizacji.** Endpoint `POST /api/v1/stock/{sku}/adjust`
> z operacjami `set`/`add`/`remove` istnieje w backendzie od dawna —
> aplikacja zaczyna go tylko wreszcie używać w komplecie. Migracji bazy
> nie ma, `.env` bez zmian.
>
> Jeśli nie wykonałeś jeszcze CZĘŚCI B z
> [wdrozenie_2026-09-05.md](wdrozenie_2026-09-05.md), zrób ją przy okazji —
> **usuwanie produktu** z tamtej paczki bez niej nie zadziała.

---

## CZĘŚĆ A — GitHub (na komputerze)

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Dodaj zmiany i zrób commit

```bash
git add desktop docs
```

```bash
git commit -m "Reczna korekta stanu magazynowego i nowa ikona aplikacji"
```

### A3. Wypchnij na GitHub

```bash
git push origin main
```

---

## CZĘŚĆ B — nowy `.exe` (na komputerze)

### B1. Zamknij działającą aplikację ORDLY

Bez tego `electron-builder` przerwie się na `EBUSY: resource busy or
locked`:

```bash
taskkill /IM ORDLY.exe /F
```

### B2. Wejdź do katalogu aplikacji

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

### B3. Zbuduj

```bash
npm run dist
```

Efekt w `desktop\release\` — `ORDLY-Setup-0.1.0.exe` (instalator) albo
`ORDLY-0.1.0-portable.exe` (bez instalacji).

Jeśli mimo `taskkill` dalej widzisz `EBUSY`, masz otwarty Eksplorator
w `release\win-unpacked`:

```bash
rmdir /s /q release\win-unpacked
```

### B4. Zainstaluj

Uruchom instalator i zaloguj się jak dotąd.

> **Stara ikona na pasku zadań po instalacji?** Windows trzyma własny
> cache ikon. Odepnij skrót z paska zadań i przypnij go ponownie —
> wtedy bierze ikonę z nowego `.exe`. Ikona w menu Start i na pulpicie
> odświeża się sama po instalacji.

---

## CZĘŚĆ C — sprawdzenie

### C1. Liczba w kolumnie „Korekta" jest klikalna

**Magazyn → Produkty.** Liczba między `−` i `+` ma kropkowane
podkreślenie. Kliknij ją — otworzy się okno **Korekta stanu** z kursorem
już w polu liczby i zaznaczoną wartością.

### C2. Dostawa 500 sztuk bez klikania

W oknie wybierz **Dostawa (+)**, wpisz `500`, popatrz na podgląd na dole:
ma pokazać `120 szt. → 620 szt. (+500)` (z Twoimi liczbami). Zatwierdź
Enterem albo przyciskiem **Zapisz stan**.

### C3. Powód trafia do historii

Ten sam wiersz → **Historia**. Ostatni wpis ma `+500` i powód, który
wpisałeś (albo domyślne „Dostawa", jeśli pole zostawiłeś puste).

### C4. Blokady działają

Wróć do okna korekty, wybierz **Zdejmij (−)** i wpisz liczbę większą niż
stan. Podgląd zamienia się w czerwony komunikat, a **Zapisz stan** jest
nieaktywny — to samo dzieje się, gdy wpisana wartość niczego nie zmienia.

### C5. Podprodukty też da się poprawić

Rozwiń strzałkę przy produkcie z podproduktami. Liczba `… szt.` przy
podprodukcie jest klikalna i otwiera to samo okno.

### C6. Ikona

Skrót na pulpicie i okno aplikacji na pasku zadań pokazują Ordiego
z podkładką.

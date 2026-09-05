# ORDLY — wdrożenie zmian z 5 września 2026

Ta paczka to jedna rzecz: **usuwanie pozycji z magazynu**. Dotąd produkt
raz dodany zostawał w ORDLY na zawsze — literówka w SKU, produkt wycofany
ze sprzedaży czy pozycja dodana na próbę siedziały na liście i zaniżały
raport magazynowy. Teraz każdy wiersz ma przycisk **Usuń**, a przed
usunięciem ORDLY mówi wprost, co zniknie razem z produktem.

**Co dokładnie robi usunięcie:**

- produkt znika z magazynu razem z **całą historią ruchów** (wpisy wiszą
  na jego SKU — nie ma ich gdzie zostawić),
- jego **podprodukty zostają w magazynie**, tracą tylko powiązanie:
  skasowanie butelki nie sprawia, że nakrętki przestaje być na półce,
- produkt **wypada z receptur ofert**, w których występował — te oferty
  dalej się sprzedają, ale przestają ruszać magazyn.

Potwierdzenie przed usunięciem wymienia to wszystko z konkretnymi
liczbami (stan, SKU podproduktów, liczba receptur), a komunikat po
usunięciu pokazuje, co faktycznie się stało. To jedyna operacja
magazynowa bez śladu w historii, więc jest to jedyny moment, żeby o tym
powiedzieć.

> **Kolejność ma znaczenie.** CZĘŚĆ A (GitHub) → CZĘŚĆ B (Pi) →
> CZĘŚĆ C (komputer, .exe) → CZĘŚĆ D (sprawdzenie). Bez CZĘŚCI B nowa
> aplikacja desktopowa dostanie z Pi `405 Method Not Allowed` — przycisk
> będzie, a usunięcie nie przejdzie.

**Migracji bazy w tej paczce NIE MA.** Żadna tabela się nie zmienia.
**Aplikacji mobilnej NIE trzeba przebudowywać** — w `mobile/` nic się nie
zmieniło.

---

## CZĘŚĆ A — wypchnięcie na GitHub (na komputerze)

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Zobacz, co pójdzie w commicie

```bash
git status --short
```

### A3. Dodaj zmiany

```bash
git add backend desktop docs
```

### A4. Zrób commit

```bash
git commit -m "Usuwanie pozycji z magazynu"
```

### A5. Wypchnij na GitHub

```bash
git push origin main
```

---

## CZĘŚĆ B — Raspberry Pi (przez SSH)

### B1. Połącz się z Pi

```bash
ssh cewastack2@cewastack2
```

### B2. Wejdź do katalogu backendu

```bash
cd ~/ordly/backend
```

### B3. Sprawdź, czy nie ma lokalnych zmian blokujących pobranie

```bash
git status --short
```

Jeśli pokaże zmodyfikowane pliki (linie z `M`), cofnij je — inaczej
`git pull` odmówi. **Nie cofa to `.env`**, bo ten plik nie jest
w repozytorium:

```bash
git restore .
```

### B4. Pobierz nową wersję i zależności

```bash
git pull && uv sync
```

### B5. Zrestartuj usługę

```bash
sudo systemctl restart ordly
```

### B6. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

Szukasz `Active: active (running)`. Jeśli `failed`:

```bash
journalctl -u ordly -n 50 --no-pager
```

### B7. Weź token do sprawdzenia

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Skopiuj wartość `token` — w kolejnym kroku wklejasz ją zamiast
`TU_TOKEN`.

### B8. Sprawdź nowy endpoint na produkcie testowym

Najpierw dodaj produkt, którego nie szkoda:

```bash
curl -s -X POST http://localhost:8000/api/v1/stock -H "Authorization: Bearer TU_TOKEN" -H "Content-Type: application/json" -d '{"sku":"TEST-DEL","name":"Produkt testowy","min_stock":0}'
```

Potem go usuń:

```bash
curl -s -X DELETE http://localhost:8000/api/v1/stock/TEST-DEL -H "Authorization: Bearer TU_TOKEN"
```

Poprawna odpowiedź to podsumowanie, a nie pusta linia:

```json
{"sku":"TEST-DEL","name":"Produkt testowy","stock":0,"detached_sub_items":[],"removed_offer_links":0}
```

Jeśli zamiast tego zobaczysz `{"detail":"Method Not Allowed"}` — usługa
wstała na starym kodzie. Wróć do B4 i B5.

---

## CZĘŚĆ C — komputer (aplikacja desktopowa)

### C1. Wejdź do katalogu aplikacji

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

### C2. Zainstaluj zależności (nowych nie ma, ale to nic nie kosztuje)

```bash
npm install
```

### C3. Zbuduj plik .exe

```bash
npm run dist
```

Efekt w `desktop\release\` — `ORDLY-Setup-0.1.0.exe` (instalator) albo
`ORDLY-0.1.0-portable.exe` (bez instalacji).

Jeśli zobaczysz `EBUSY: resource busy or locked` — masz uruchomioną starą
wersję ORDLY albo otwarty Eksplorator w `release\win-unpacked`:

```bash
taskkill /IM ORDLY.exe /F
```

```bash
rmdir /s /q release\win-unpacked
```

### C4. Zainstaluj i zaloguj się

Adres `https://cewastack2.tail7f5a20.ts.net`, login jak dotąd.

---

## CZĘŚĆ D — sprawdzenie w aplikacji

### D1. Przycisk jest na miejscu

**Magazyn → Produkty.** W ostatniej kolumnie każdego wiersza (nazywa się
teraz **Akcje**, nie „Historia") obok „Historia" siedzi **Usuń**.
Podprodukty mają swój przycisk po rozwinięciu strzałki przy produkcie
głównym.

### D2. Potwierdzenie mówi konkret, nie „czy na pewno"

Kliknij **Usuń** przy produkcie, który ma podprodukty albo występuje
w recepturze oferty. Okno ma wymienić:

- stan, który przestanie być liczony,
- SKU podproduktów, które zostaną w magazynie bez powiązania,
- liczbę receptur ofert, z których produkt wypadnie.

Możesz teraz zamknąć okno przyciskiem **Anuluj** — nic się nie stanie.

### D3. Usunięcie naprawdę usuwa

Dodaj produkt testowy (**Nowy produkt**, SKU `TEST-DEL2`), a potem usuń
go. Wiersz znika z listy od razu, a komunikat na dole ekranu mówi
`TEST-DEL2 zniknął z magazynu`.

### D4. Podprodukt przeżywa produkt główny

Jeśli usuwałeś produkt z podproduktami: przełącz filtr na **Wszystkie**.
Dawne podprodukty stoją teraz na liście jako samodzielne pozycje ze swoim
stanem — to jest zachowanie poprawne, nie błąd.

---

## Czego ta paczka NIE robi

- **Nie usuwa produktu z bota Telegram.** Komendy `/stock` dalej nie mają
  odpowiednika `delete` — usuwanie żyje na razie tylko w aplikacji
  desktopowej i w API.
- **Nie usuwa produktów z aplikacji mobilnej.** Telefon dalej służy do
  podglądu i korekt stanu.
- **Nie da się cofnąć usunięcia.** Nie ma kosza ani „przywróć". Jedyny
  ratunek po pomyłce to kopia bazy z `~/ordly/backend/backups/`.

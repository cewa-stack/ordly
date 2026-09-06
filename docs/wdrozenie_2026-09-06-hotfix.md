# ORDLY — hotfix z 6 września 2026: SKU z ukośnikiem

**Objaw:** korekta stanu produktów `KRO10/30` i `NAK10/30` kończyła się
komunikatem „Korekta nie przeszła — **Method Not Allowed**". Stare
produkty (`PET30`, `PET60`, `NAK60`…) działały normalnie.

**Przyczyna.** Ukośnik w SKU trafia do adresu jako `%2F`, ale serwer
(uvicorn) **dekoduje ścieżkę, zanim router dopasuje trasę**. Żądanie
`/stock/KRO10%2F30/adjust` docierało więc do routera jako
`/stock/KRO10/30/adjust` — o jeden segment za dużo. Nie pasowało do
żadnej trasy API i spadało na sam dół, do serwera plików statycznych,
który serwuje aplikację mobilną. Ten na POST odpowiada `405 Method Not
Allowed` — i dokładnie to widziałeś w aplikacji.

To trafiało **wszystkie** operacje na takim produkcie: korekta, historia,
podprodukty, produkt główny i usuwanie. Nie tylko stan.

**Naprawa.** Trasy per-SKU (i per-oferta) używają teraz `{sku:path}`,
czyli wzorca, który przyjmuje ukośnik jako część identyfikatora. Przy
okazji to samo dostała poczta: `Message-ID` z ukośnikiem (legalny nagłówek,
np. `<abc/def@host>`) blokował podgląd treści maila tym samym mechanizmem.

**Twoje dane zostają bez zmian.** Nie trzeba zmieniać SKU ani nic
przepisywać — `KRO10/30` po tej poprawce po prostu działa.

> **Aplikacji desktopowej NIE trzeba przebudowywać.** Zmiana jest w całości
> po stronie backendu — plik `.exe` z dzisiaj zostaje. Migracji bazy nie ma,
> `.env` bez zmian.

---

## CZĘŚĆ A — GitHub (na komputerze)

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Commit i push

```bash
git add backend docs
```

```bash
git commit -m "Naprawa tras API dla SKU i Message-ID z ukosnikiem"
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

### B2. Pobierz i zrestartuj

```bash
git pull && uv sync
```

```bash
sudo systemctl restart ordly
```

### B3. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

### B4. Sprawdź poprawkę bez ruszania stanów

Token (wklejasz go w kolejnym poleceniu zamiast `TU_TOKEN`):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Podgląd produktu z ukośnikiem — to samo, co wcześniej dawało 404:

```bash
curl -s "http://localhost:8000/api/v1/stock/KRO10%2F30" -H "Authorization: Bearer TU_TOKEN"
```

Ma wrócić JSON produktu (`"sku":"KRO10/30"`), a nie `{"detail":"Not Found"}`.

---

## CZĘŚĆ C — sprawdzenie w aplikacji

Aplikację wystarczy zamknąć i otworzyć (albo poczekać — dane odświeżają
się same).

### C1. Korekta na produkcie z ukośnikiem

**Magazyn → Produkty →** wiersz *Kroplomierz 10ml/30ml*. Kliknij `+`.
Stan ma wzrosnąć do 1 zamiast pokazać czerwony komunikat.

### C2. Ręczne wpisanie stanu

Kliknij liczbę w kolumnie **Korekta**, wybierz **Dostawa (+)**, wpisz
`500`, zatwierdź. Podgląd ma pokazać `0 szt. → 500 szt. (+500)`.

### C3. To samo dla nakrętki

*Nakrętka 10ml/30ml* — ta sama operacja.

### C4. Butelka 30ml gorilla (SKU `B30`)

Ten produkt **nie ma ukośnika w SKU**, więc jego korekta nie powinna była
paść z tego powodu. Sprawdź go osobno: kliknij `+`. Jeśli mimo to
wyskoczy błąd, **przepisz dokładną treść komunikatu z czerwonego okienka**
— przy innym komunikacie (np. „Nie znaleziono produktu" albo błąd 422)
przyczyna jest inna niż ta naprawiona tutaj.

### C5. Poczta

**Poczta →** otwórz dowolną wiadomość. Podgląd treści działa jak
dotychczas; poprawka dotyczy maili, których `Message-ID` zawiera ukośnik —
te wcześniej nie chciały się otworzyć.

---

## Czego ta paczka NIE zmienia

- **Nie rusza `/orders/{external_id}`.** Ten sam wzorzec siedzi
  w zamówieniach. W lokalnej kopii bazy (50 zamówień) żaden numer nie ma
  ukośnika — produkcyjnej bazy na Pi nie sprawdzałem — a poprawka
  wymagałaby przestawienia kolejności tras razem z testami, więc zostaje
  na osobną decyzję. Gdyby kiedyś pojawiło się zamówienie z ukośnikiem
  w numerze, objawi się dokładnie tak samo: „Method Not Allowed" przy
  zmianie statusu.
- **Nie zmienia niczego w aplikacji desktopowej ani mobilnej.**

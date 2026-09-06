# ORDLY — wdrożenie zmian z 6 września 2026 (asystent Ordlaka)

Trzy rzeczy z jednego zgłoszenia:

1. **`NaN zł` w Statystykach.** Na liście „Najczęściej sprzedawane" kwoty
   pokazywały się jako `NaN zł` wszędzie tam, gdzie produkt sprzedał się
   w więcej niż jednym zamówieniu. Backend oddawał kwoty jako **tekst**
   (`"19.99"`), a nie liczbę — w JavaScripcie `0 + "19.99" + "19.99"` to
   nie dodawanie, tylko sklejanie napisów: `"019.9919.99"`. Stąd `NaN`.
   Naprawione po stronie backendu (kwoty w JSON-ie są teraz liczbami)
   **i** aplikacji (kwoty z API są przeliczane, więc starszy backend na Pi
   też się wyświetli poprawnie).
2. **Przycisk „Napisz zamówienie" w Hurtowniach.** Był wyłączany, gdy nic
   nie było poniżej progu — a to najczęstszy stan przy pełnym magazynie.
   Teraz jest zawsze aktywny, a w oknie wiadomości pozycje **zaznacza się
   ptaszkiem**: braki są zaznaczone z góry, resztę dodajesz kliknięciem.
   Mail bez ani jednej pozycji też wyjdzie — do hurtowni pisze się też po
   to, żeby zapytać o cennik albo termin.
3. **Ordlak jest teraz asystentem aplikacji.** Zakładka **Ordlak** to
   czat, który odpowiada na pytania o Twój sklep: ile się sprzedało, co ma
   niski stan, co czeka na wysyłkę, jakie dni sprzedażowe się zbliżają.
   **Generator ofert został usunięty** — cały jego kod, ekran i endpointy
   znikają z aplikacji.
4. **Ordlak umie sześć nowych rzeczy** (Twój wybór z listy propozycji):
   - **odpowiedzi na dyskusje i reklamacje** — czyta wątek z Allegro
     i pisze gotową treść; wysyłasz Ty, na ekranie Dyskusje,
   - **kalkulator ceny** — „za ile wystawić rzecz kupioną za 12 zł przy
     prowizji 10% i marży 30%"; liczy Python wzorem z prowizją naliczaną
     też od wysyłki, nie model na oko,
   - **czytanie skrzynki** — co przyszło, co nieprzeczytane, o co chodzi
     w tym mailu,
   - **szukanie zamówień i klientów** — „co kupił jan_kowalski", „znajdź
     zamówienie z butelką 60 ml",
   - **zapisywanie rozmów** — wątki przeżywają restart aplikacji, lista po
     lewej stronie ekranu,
   - **zapis odpowiedzi do pliku** — przycisk pod każdą odpowiedzią.

> **Co z zapisanymi ofertami?** Tabela `ordlak_generations` **zostaje
> w bazie na Pi** nietknięta razem z historią wygenerowanych ofert —
> usunąłem tylko kod, nie dane. Gdybyś chciał ją skasować, powiedz:
> to osobna migracja i osobna decyzja, bo tego się nie cofa.

> **Pi WYMAGA aktualizacji I MIGRACJI BAZY.** Bez `git pull` czat zwróci
> 404; bez `alembic upgrade head` (migracja `0010`, tabele rozmów) czat
> wywali się przy pierwszym pytaniu, bo nie będzie gdzie zapisać wątku.
> `.env` bez zmian, żadnych nowych zależności.
>
> **Kolejność ma znaczenie:** CZĘŚĆ A (GitHub) → CZĘŚĆ B (Pi) →
> CZĘŚĆ C (komputer, `.exe`) → CZĘŚĆ D (sprawdzenie).

> **Asystent potrzebuje `ANTHROPIC_API_KEY`** w `~/ordly/backend/.env` —
> tego samego, co generator ofert. Jeśli generator u Ciebie działa, klucz
> już tam jest i nic nie musisz robić. Jeśli nie — czat powie o tym wprost
> na ekranie, zamiast milczeć.

---

## CZĘŚĆ A — GitHub (na komputerze)

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Dodaj zmiany i zrób commit

```bash
git add backend desktop mobile docs bot_ordlak
```

```bash
git commit -m "Ordlak jako asystent, kwoty jako liczby i mail do hurtowni bez blokady"
```

### A3. Wypchnij na GitHub

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

Jeśli pokaże zmodyfikowane pliki (linie z `M`), cofnij je — inaczej
`git pull` odmówi. **Nie cofa to `.env`**, bo tego pliku nie ma
w repozytorium:

```bash
git restore .
```

### B3. Pobierz nową wersję

```bash
git pull
```

### B4. Zrób migrację bazy

Tworzy tabele `ordlak_conversations` i `ordlak_messages` na zapisane
rozmowy. **Bez tego kroku czat wywali się przy pierwszym pytaniu.**

```bash
uv run alembic upgrade head
```

Ostatnia linia ma brzmieć `Running upgrade 0009 -> 0010, create
ordlak_conversations and ordlak_messages`.

### B5. Zrestartuj usługę

```bash
sudo systemctl restart ordly
```

### B6. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

Gdyby coś było nie tak:

```bash
journalctl -u ordly -n 50 --no-pager
```

### B7. Sprawdź, czy klucz do asystenta jest na miejscu

```bash
grep -c ANTHROPIC_API_KEY ~/ordly/backend/.env
```

`1` = klucz jest wpisany. `0` = trzeba go dodać (osobny klucz
z `console.anthropic.com`, **nie** subskrypcja Claude) i zrestartować
usługę jeszcze raz.

### B8. Sprawdź, że czat odpowiada

Token (wklejasz go w kolejnym poleceniu zamiast `TU_TOKEN`):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

```bash
curl -s -X POST http://localhost:8000/api/v1/ordlak/chat -H "Authorization: Bearer TU_TOKEN" -H "Content-Type: application/json" -d '{"message":"Co ma niski stan?"}'
```

Ma wrócić JSON z polami `conversation_id`, `reply` i `used_tools` — a nie
`{"detail":"Not Found"}`.

---

## CZĘŚĆ C — nowy `.exe` (na komputerze)

### C1. Zamknij działającą aplikację ORDLY

Bez tego `electron-builder` przerwie się na `EBUSY: resource busy or
locked`:

```bash
taskkill /IM ORDLY.exe /F
```

### C2. Wejdź do katalogu aplikacji

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

### C3. Zbuduj

```bash
npm run dist
```

Efekt w `desktop\release\` — `ORDLY-Setup-0.1.0.exe` (instalator) albo
`ORDLY-0.1.0-portable.exe` (bez instalacji).

### C4. Zainstaluj

Uruchom instalator i zaloguj się jak dotąd.

---

## CZĘŚĆ D — sprawdzenie w aplikacji

### D1. Kwoty w Statystykach

**Statystyki → Najczęściej sprzedawane.** Każdy wiersz ma kwotę w złotówkach.
Ani jednego `NaN zł`.

### D2. Mail do hurtowni wychodzi przy pełnym magazynie

**Hurtownie.** Karta „Butelki Hurtowni WiM" pokazuje `0 poniżej progu`,
a przycisk **Napisz zamówienie** jest mimo to aktywny. Kliknij go —
w oknie zobaczysz listę produktów tej hurtowni z ptaszkami. Odznacz
wszystkie: temat zmienia się na „Zapytanie", treść zostaje samym
powitaniem, a **Wyślij maila** dalej działa.

### D3. Braki są zaznaczone same

Zdejmij chwilowo tyle sztuk, żeby produkt hurtowni zszedł poniżej progu
(**Magazyn → kliknij liczbę w kolumnie Korekta → Zdejmij (−)**), wróć do
Hurtowni i otwórz to samo okno. Ten produkt jest zaznaczony od razu, ma
czerwony dopisek `poniżej progu`, a ilość jest policzona tak, żeby dobić
do progu. Po sprawdzeniu dodaj sztuki z powrotem (**Dostawa (+)**).

### D4. Ordlak to czat

**Ordlak.** Zamiast formularza oferty widzisz listę rozmów po lewej,
Ordlaka na środku i pięć podpowiedzi do kliknięcia. Nagłówek ekranu mówi
„Asystent sprzedaży". Po generatorze ofert nie ma śladu.

### D5. Asystent odpowiada z danych, nie z głowy

Kliknij podpowiedź **„Co ma niski stan?"**. Pod odpowiedzią pojawi się
szara linijka `na podstawie: niskie stany` — to znaczy, że Ordlak
naprawdę odczytał magazyn. Sprawdź wynik na ekranie **Magazyn**: musi się
zgadzać co do sztuki.

### D6. Kalendarz sprzedażowy

Zapytaj: **„Jakie dni sprzedażowe się zbliżają?"**. Ordlak wymieni
najbliższe wydarzenia z datami i z informacją, od kiedy warto mieć
wystawione oferty. Porównaj z ekranem **Kalendarz** — daty muszą być te
same.

### D7. Raport ze sprzedaży

Zapytaj: **„Ile sprzedałem w tym tygodniu?"**. Liczba zamówień i przychód
mają zgadzać się z kafelkami na ekranie **Statystyki**.

### D8. Rozmowy przeżywają restart aplikacji

Zamknij ORDLY i otwórz ponownie. Wejdź w **Ordlak** — po lewej stronie
stoją Twoje wcześniejsze wątki, z tytułem wziętym z pierwszego pytania
i datą ostatniej wiadomości. Kliknij któryś: cała historia jest na miejscu.

Przycisk **Nowa rozmowa** zaczyna świeży wątek (Ordlak nie pamięta wtedy
poprzednich pytań). Kosz przy wierszu na liście kasuje wątek na dobre —
zapyta o potwierdzenie.

### D9. Kalkulator ceny liczy, a nie zgaduje

Zapytaj: **„Za ile wystawić rzecz kupioną za 25 zł, sprowadzenie 8 zł,
wysyłka 12 zł, prowizja 10%, marża 30%?"**. Ma wyjść **57,00 zł**
i prowizja **6,90 zł** — to dokładnie te liczby, które dawał generator
ofert. Pod odpowiedzią zobaczysz `na podstawie: kalkulator ceny`.

### D10. Odpowiedź na dyskusję do skopiowania

Jeśli masz otwartą dyskusję na Allegro, zapytaj: **„Mam jakieś dyskusje do
odpisania?"**, a potem **„Napisz odpowiedź do tej pierwszej"**. Ordlak
przeczyta wątek i zaproponuje treść. Najedź myszką na odpowiedź — pod nią
pojawi się **Kopiuj** i **Zapisz do pliku**. Wysyłasz sam, na ekranie
**Dyskusje** — Ordlak nigdy nie odpisuje za Ciebie.

### D11. Skrzynka i szukanie

**„Co przyszło na skrzynkę?"** — wypisze ostatnie maile z oznaczeniem,
które są nieprzeczytane. Jeśli IMAP nie jest skonfigurowany na Pi, powie
to wprost, zamiast twierdzić, że nie masz maili.

**„Co kupił <login jakiegoś klienta>?"** — wypisze jego zamówienia z sumą.

### D12. Zapis raportu do pliku

Pod dowolną odpowiedzią kliknij **Zapisz do pliku**. Otworzy się okno
zapisu z nazwą wziętą z tytułu rozmowy i rozszerzeniem `.md`. Plik otwiera
się w Notatniku z polskimi znakami.

---

## Co dalej (świadomie NIE zrobione)

- **Aplikacja mobilna nie dostała asystenta.** Zgłoszenie dotyczyło
  desktopu, a czat na telefonie to osobny ekran do zaprojektowania.
  Poprawka `NaN` działa na telefonie sama z siebie — siedzi w backendzie,
  więc wystarczy CZĘŚĆ B. Przebudowa PWA nie jest potrzebna.
- **Tabela `ordlak_generations` została w bazie.** Kod generatora zniknął,
  dane nie. Usunięcie tabeli to osobna migracja — do zrobienia wtedy, gdy
  powiesz, że historia ofert nie jest już potrzebna.
- **`python-multipart` wypadł z `pyproject.toml`** (był potrzebny tylko do
  wysyłania zdjęć do generatora). **Nie musisz robić `uv sync`** — paczka
  po prostu zostanie w środowisku na Pi i nikomu nie przeszkadza.
- **Asystent niczego nie zapisuje.** Nie wyśle maila, nie poprawi stanu
  magazynowego, nie wystawi oferty. Poproszony o akcję, powie, na którym
  ekranie zrobisz ją sam. Dopóki tylko czyta, jego pomyłka kosztuje jedno
  zdanie, a nie rozjechany magazyn — to można poluzować później, ale
  świadomie, a nie przy okazji.
- **Ordlak nie odzywa się sam.** Twoja decyzja z listy propozycji: żadnego
  porannego briefingu ani alertów — asystent czeka, aż go zapytasz.
  Powiadomienia można dołożyć później, to osobny kawałek.

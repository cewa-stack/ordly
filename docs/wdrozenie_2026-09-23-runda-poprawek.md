# ORDLY — 23 września 2026: runda poprawek

Wszystko, co zaakceptowałeś w przeglądzie z 22.09, w jednej paczce:
pasek synchronizacji, ekran blokady „List przewozowy” (wariant C) i 12
ulepszeń z listy.

**Co zmienia ta paczka:**

*Telefon*

1. **Pasek synchronizacji** wypełnia kartę Ordlaka od lewej do prawej:
   szybko do 70%, potem powoli dalej, a 100% dopiero po odpowiedzi Allegro.
   Bez synchronizacji karta jest gładka — zniknęła poświata, która
   wyglądała jak pasek zatrzymany w połowie.
2. **Ekran blokady, logowania i włączania Face ID** — zamiast trzech kółek
   etykieta nadawcza z dzisiejszą datą w kodzie kreskowym. Po udanym
   Face ID taśmy się odklejają, a Ordlak budzi się i podskakuje, zanim
   wejdziesz do aplikacji.
3. **Face ID nie odpala się już sam** przy otwarciu i nie wita czerwonym
   „Nie rozpoznano”. Dotykasz przycisku — dopiero wtedy pyta.
4. **Pasek stanu iOS** jest czarny zamiast jasnego pasa nad ciemną
   aplikacją (znaczniki są teraz w samym HTML-u, iOS czyta je przy starcie).
5. **„Allegro sprawdzone 1 min temu”** na karcie Start — z danych Pi.
   Po kwadransie bez synchronizacji napis robi się koralowy.
6. **Logowanie** startuje od `https://`, a podpowiedź „admin / admin”
   zniknęła.
7. **Odpowiedź na dyskusję z telefonu** — pole pod wątkiem, szablony nad
   nim, okno potwierdzenia przed wysłaniem (kupujący to widzi).
8. **Tryb bez połączenia** — gdy telefon nie widzi Pi, pokazuje ostatnio
   pobrane dane i pasek „Brak połączenia z Pi · stan z 14:32”.
9. **„czeka 3 h”** przy zamówieniach do spakowania, po dobie koralowo.
10. **Liczby na kafelkach przeliczają się** po synchronizacji, a nowe
    zamówienie na liście raz mignie.
11. **Ordlak z rekwizytami** w pustych stanach: koperta w Poczcie, karton
    w Magazynie i Zwrotach, lupa przy pustym wyszukiwaniu.
12. Poprawiona odmiana: „2 zamówienia czekają”, „dyskusja jest otwarta”.

*Desktop*

13. **Ten sam pasek synchronizacji** na karcie powitalnej.
14. **Szablony odpowiedzi** przychodzą z Pi (te same co na telefonie),
    a **Ustawienia → Szablony odpowiedzi** pozwalają je dodawać,
    zmieniać i usuwać. Login i numer przesyłki wstawiają się same; gdy
    zamówienie nie ma jeszcze numeru, w tekście zostaje luka `‹…›`
    i odpowiedź się nie wyśle, dopóki jej nie uzupełnisz.
15. **Czas czekania, przeliczające się liczby, mignięcie nowych zamówień,
    rekwizyty Ordlaka** — tak jak na telefonie.

*Pi*

16. **Nowa tabela `reply_templates`** z pięcioma szablonami: cztery
    dotychczasowe z desktopu (bez zmian treści) i nowy „Wysłane — numer
    przesyłki”.

**Migracja bazy: TAK** (`0012 -> 0013`). **Nowych zależności: brak** —
ani na Pi, ani w `npm`.

---

## Kolejność: Pi → telefon → desktop

Najpierw Pi: telefon i desktop pobierają szablony z nowego adresu
`/api/v1/reply-templates`. Na starym backendzie menu szablonów pokaże błąd.

---

## CZĘŚĆ A — scal i wypchnij (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

```bash
git checkout main
```

```bash
git merge runda-poprawek-2026-09-23
```

Ma napisać `Fast-forward`. Jeśli zobaczysz `CONFLICT` — zatrzymaj się
i wklej mi output.

Na liście zmian dalej będą usunięte pliki `bot_ordlak/mascot_*.png`
i `mascot_*-removebg-preview.png` — nie są częścią tej paczki i nic ich
nie używa. Zostawiam je Tobie.

```bash
git push
```

---

## CZĘŚĆ B — Raspberry Pi: backend i migracja (przez SSH)

### B1. Połącz się

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### B2. Kopia bazy — obowiązkowo, jest migracja

```bash
cp data/ordly.db ~/ordly-przed-runda-2026-09-23.db
```

```bash
ls -lh ~/ordly-przed-runda-2026-09-23.db
```

Ma pokazać plik o rozmiarze podobnym do `data/ordly.db`.

### B3. Lokalne zmiany na Pi

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env` ani `data/`):

```bash
git restore .
```

### B4. Pobierz kod

```bash
git pull
```

```bash
uv sync
```

### B5. Zatrzymaj usługę i uruchom migrację

```bash
sudo systemctl stop ordly
```

```bash
uv run alembic upgrade head
```

Ostatnia linia ma zawierać **`Running upgrade 0012 -> 0013, szablony
odpowiedzi w dyskusjach`**. Jeśli pojawi się błąd — **nie uruchamiaj
usługi**, wklej mi cały output.

```bash
uv run alembic current
```

Ma pokazać `0013 (head)`.

### B6. Uruchom usługę

```bash
sudo systemctl start ordly
```

```bash
sudo systemctl status ordly --no-pager | head -3
```

Ma być `active (running)`.

### B7. Sprawdź, że szablony są pod nowym adresem

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/reply-templates
```

Ma pokazać **`401`** — „adres jest, ale nie podałeś tokena”. To wynik
prawidłowy. `404` znaczy, że usługa chodzi na starym kodzie — wróć do B4.

```bash
journalctl -u ordly --since "2 min ago" | grep -i "error\|traceback"
```

Brak wyniku = dobrze. Jeśli coś się wypisze, wklej mi to.

---

## CZĘŚĆ C — telefon: nowa paczka PWA

### C1. Zbuduj (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Sprawdź, że znaczniki iOS trafiły do strony (to one usuwają jasny pas pod
zegarem):

```bash
findstr "status-bar-style" dist\index.html
```

Ma wypisać linię z `content="black"`. Jeśli nic nie wypisze —
zatrzymaj się tutaj.

### C2. Spakuj i wyślij

**Nie używaj `Compress-Archive`** — gubi bit wykonywalności na katalogach.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

### C3. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Ma pokazać `/home/cewastack2/ordly/webapp_dist`. Jeśli coś innego —
podmień ścieżkę w komendzie niżej.

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C4. Dodaj ORDLY do ekranu początkowego jeszcze raz

> ⚠️ **iOS czyta kolor paska stanu w chwili dodania aplikacji do ekranu
> początkowego.** Bez tego kroku jasny pas pod zegarem zostanie.

1. Przytrzymaj ikonę ORDLY → **Usuń aplikację** → **Usuń z ekranu
   początkowego**. (Usuwa tylko skrót — dane zostają na Pi.)
2. **Safari** → `https://cewastack2.tail7f5a20.ts.net`.
3. **Udostępnij** → **Do ekranu początkowego** → **Dodaj**.
4. Otwórz ORDLY z ikony. Zobaczysz ekran logowania z etykietą nadawczą
   i polem adresu zaczynającym się od `https://` — zaloguj się.
5. Włącz Face ID, gdy aplikacja zaproponuje.
6. **Włącz powiadomienia ponownie**: Ustawienia w ORDLY → Powiadomienia →
   Wyślij test. Dla iOS to nowa aplikacja — stara subskrypcja nie
   przechodzi.

---

## CZĘŚĆ D — desktop: nowy `.exe`

Zamknij działające ORDLY, potem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`. Nowych paczek nie
ma, więc `npm install` nie jest potrzebne.

---

## CZĘŚĆ E — sprawdzenie

### E1. Telefon

- **Ekran blokady** (zamknij ORDLY całkiem i otwórz): etykieta z dzisiejszą
  datą, **bez** czerwonego „Nie rozpoznano”. Dotknij „Odblokuj przez
  Face ID” → taśmy odlatują, Ordlak otwiera oczy i podskakuje, potem
  wchodzisz do aplikacji.
- **Pasek stanu** nad ekranem jest czarny z białym zegarem — bez jasnego
  pasa.
- **Start**: pod treścią karty Ordlaka szara linia „Allegro sprawdzone
  1 min temu”. Dotknij karty → pasek wypełnia się od lewej, potem
  „Zsynchronizowano”.
- **Wymaga uwagi / Zamówienia**: przy czekających zamówieniach „czeka N h”
  zamiast godziny, po dobie na koralowo.
- **Dyskusje → wątek**: nad polem odpowiedzi szablony. „Wysłane — numer
  przesyłki” wstawia numer z zamówienia. Wyślij → okno potwierdzenia
  z początkiem treści → Wyślij. Odpowiedź pojawia się w wątku.
- **Bez połączenia**: wyłącz Tailscale na telefonie i otwórz ORDLY. Mają
  się pokazać ostatnie dane i żółty pasek „Brak połączenia z Pi · stan
  z …”. Włącz Tailscale, dotknij paska — pasek znika.

### E2. Desktop

- **Start** → Synchronizuj: karta powitalna wypełnia się od lewej.
- **Ustawienia → Szablony odpowiedzi**: pięć szablonów. Dodaj własny,
  wstaw przyciskiem „numer przesyłki” — ten sam szablon pojawia się na
  telefonie po ponownym wejściu w wątek.
- **Dyskusje**: ikona szablonu nad polem odpowiedzi pokazuje listę z Pi.
  Przy zamówieniu bez numeru przesyłki w tekście zostaje
  `‹uzupełnij numer przesyłki›`, a „Wyślij” jest wyłączone, dopóki tego nie
  poprawisz.
- **Zamówienia**: kolumna „Czas” przy zamówieniach do spakowania mówi, ile
  czekają (najedź, żeby zobaczyć od kiedy).

---

## Gdyby coś poszło nie tak

```bash
journalctl -u ordly -f
```

Powrót do stanu sprzed paczki — jedna komenda na raz. **Kolejność ma
znaczenie**: migrację cofa się, zanim cofnie się kod, bo plik migracji
jest tylko w nowym kodzie.

```bash
sudo systemctl stop ordly
```

```bash
cd ~/ordly/backend
```

```bash
uv run alembic downgrade 0012
```

```bash
git checkout 33aff1f
```

```bash
uv sync
```

```bash
sudo systemctl start ordly
```

Downgrade usuwa tabelę szablonów razem z Twoimi szablonami — reszta bazy
zostaje nietknięta, więc kopii z B2 nie trzeba przywracać. Po takim
cofnięciu napisz do mnie: trzeba jeszcze wrócić z „odłączonego” stanu
gita (`git checkout main`) i wgrać poprzednią paczkę PWA.

---

## Pliki

| Plik | Do czego |
|---|---|
| `mobile/src/screens/StartScreen.tsx` | pasek synchronizacji, „Allegro sprawdzone…”, przeliczane kafle |
| `mobile/src/components/Waybill.tsx` | etykieta nadawcza na ekranach blokady, logowania i Face ID |
| `mobile/src/screens/LockScreen.tsx` | Face ID dopiero po dotknięciu, budzenie Ordlaka |
| `mobile/public/index.html` | znaczniki iOS w statycznym HTML-u (pasek stanu) |
| `mobile/src/store/offlineCache.ts` | ostatni stan danych bez połączenia z Pi |
| `mobile/src/screens/IssueDetailScreen.tsx` | odpowiedź na dyskusję z telefonu |
| `desktop/src/renderer/src/components/ReplyTemplatesSettings.tsx` | edycja szablonów w Ustawieniach |
| `desktop/src/renderer/src/components/SyncSweep.tsx` | pasek synchronizacji na desktopie |
| `backend/alembic/versions/0013_create_reply_templates.py` | tabela szablonów + pięć startowych |
| `backend/src/app/api/endpoints/reply_templates.py` | `/api/v1/reply-templates` |

# ORDLY — wdrożenie zmian z 4 września 2026

Ta paczka to cztery rzeczy:

1. **Magazyn na telefonie — czytelność stanu.** Pasek zapasu pokazywał
   100% dla każdego produktu bez ustawionego progu alertu, więc produkt
   z 5 sztukami wyglądał identycznie jak ten z 500. Teraz pasek liczy
   się od stanu docelowego (`max_stock`), a bez żadnego progu znika
   zamiast kłamać. Liczba sztuk urosła i przy niskim stanie przejmuje
   kolor statusu.
2. **Magazyn na telefonie — przewijanie.** Pasek KPI, ostrzeżenie
   o ofertach poza magazynem, wyszukiwarka i filtry były przyklejone do
   góry ekranu i zabierały **311 pt** — na liście zostawało miejsce na
   trzy karty. Teraz przewijają się razem z listą: widać siedem kart.
3. **Marketing nie zaśmieca skrzynki.** `powiadomienia@marketing.olx.pl`
   („Wow — 70% rabatu") i `hello@newsletter.allegro.pl` („Odbierz
   kupon") przechodziły dotąd tym samym filtrem co prawdziwe
   powiadomienia. Od teraz nie trafiają nawet do bazy. Wymaga JEDNEJ
   nowej linii w `.env` na Pi — krok B5.
4. **Poczta OLX przestaje być niema.** Na podstawie czterech
   przekazanych maili ORDLY rozpoznaje sprzedaż i wiadomość od
   kupującego, wyciąga tytuł ogłoszenia i numer transakcji, i wysyła
   powiadomienie (Telegram + push). Przy okazji zwrot na Allegro
   Lokalnie dostał własny tytuł powiadomienia.

> **SPRZEDAŻ Z OLX NIE TWORZY ZAMÓWIENIA I NIE ODEJMUJE STANÓW.** To
> decyzja podjęta po przeczytaniu Twoich próbek: **mail sprzedażowy
> z OLX nie zawiera żadnej kwoty** — ani ceny ogłoszenia, ani sumy
> zapłaconej; mówi tylko „Płatność została dokonana". Nie ma też
> kupującego ani liczby sztuk. Zamówienie zbudowane z takiego maila
> weszłoby do przychodu z kwotą 0 zł, a kwoty zamówienia nie da się
> potem poprawić z aplikacji. Powiadomienie mówi więc dokładnie tyle,
> ile mail: co się sprzedało i kiedy — a treść wprost przypomina, że
> **stan magazynowy trzeba poprawić ręcznie**.

> **Kolejność ma znaczenie.** CZĘŚĆ A (GitHub) → CZĘŚĆ B (Pi) →
> CZĘŚĆ C (telefon) → CZĘŚĆ D (sprawdzenie). Bez CZĘŚCI B nowa zmienna
> `.env` nie zadziała i marketing dalej będzie wpadał do skrzynki.

**Migracji bazy w tej paczce NIE MA.** Żadna tabela się nie zmienia.

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
git add backend desktop mobile docs features_folder
```

### A4. Zrób commit

```bash
git commit -m "Poczta OLX, filtr marketingu i czytelny magazyn na telefonie"
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

### B5. DOPISZ `MAIL_EXCLUDE_SENDERS` — bez tego kroku marketing zostaje

To jedyna zmiana konfiguracji w całej paczce. Sprawdź, czy zmiennej
jeszcze nie ma:

```bash
grep MAIL_EXCLUDE_SENDERS ~/ordly/backend/.env
```

Jeśli nic nie wypisze (spodziewane), otwórz plik:

```bash
nano ~/ordly/backend/.env
```

Znajdź linię `MAIL_WATCH_SENDERS=allegro,olx` i **pod nią** dopisz:

```
MAIL_EXCLUDE_SENDERS=marketing.olx.pl,newsletter.allegro.pl
```

Zapisz i wyjdź: `Ctrl+O`, `Enter`, `Ctrl+X`.

> **Dlaczego osobna zmienna, a nie zwężenie `MAIL_WATCH_SENDERS`.** IMAP
> dopasowuje nagłówek `From` po **podciągu**, więc `olx` łapie zarówno
> `noreply@olx.pl`, jak i `powiadomienia@marketing.olx.pl`. Zwężenie
> `MAIL_WATCH_SENDERS` do pełnych domen odcięłoby prawdziwych nadawców —
> `allegro.pl` nie występuje przecież ani w `allegromail.pl`, ani
> w `allegrolokalnie.pl`. Dlatego zapytanie do serwera zostaje szerokie,
> a marketing odsiewamy po pobraniu, przed zapisem do bazy.
>
> Gdy pojawi się kolejny nadawca marketingowy, dopisujesz go tu po
> przecinku i restartujesz usługę. Nic więcej.

### B6. Zrestartuj usługę

```bash
sudo systemctl restart ordly
```

### B7. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

Szukasz `Active: active (running)`. Jeśli `failed`:

```bash
journalctl -u ordly -n 50 --no-pager
```

### B8. Weź token do dalszych sprawdzeń

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Skopiuj wartość `token` — w kolejnych krokach wklejasz ją zamiast
`TU_TOKEN`.

### B9. Wymuś pobranie maili

```bash
curl -s -X POST http://localhost:8000/api/v1/mail/sync -H "Authorization: Bearer TU_TOKEN"
```

Jeśli w skrzynce leżały niepobrane maile marketingowe, **nie powinny się
tu doliczyć**. Weryfikacja w kroku D3.

---

## CZĘŚĆ C — telefon (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Backend
> serwuje ją jako zbudowaną, statyczną paczkę z osobnego katalogu. Bez
> tego kroku magazyn zostanie taki, jaki był.

### C1. Zbuduj aplikację mobilną (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Trwa 1–2 minuty. Efekt trafia do `mobile\dist\`.

### C2. Spakuj i wyślij na Pi

Uruchom z katalogu `mobile`. **Nie używaj `Compress-Archive`** — gubi bit
wykonywalności na katalogach, przez co backend nie wejdzie w rozpakowaną
paczkę i telefon dostanie biały ekran.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

Zanim pójdziesz dalej, upewnij się, że plik doleciał:

```bash
ssh cewastack2@cewastack2 "ls -lh ~/mobile-dist.tgz"
```

Ma pokazać kilka megabajtów. Jeśli `No such file` — **zatrzymaj się
tutaj**, nie wykonuj C3, bo skasujesz działającą aplikację.

### C3. Podmień paczkę na Pi

Najpierw sprawdź, gdzie backend NAPRAWDĘ szuka tych plików — to nie jest
`~/ordly/mobile/dist`:

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Odpowiedź to `WEB_APP_DIST_PATH=/home/cewastack2/ordly/webapp_dist`.
Podmień zawartość TEGO katalogu:

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C4. Odśwież aplikację na telefonie

PWA cache'uje pliki. Zamknij aplikację do końca (nie tylko zminimalizuj)
i otwórz ponownie. Jeśli magazyn dalej wygląda po staremu — w Safari
przytrzymaj przycisk odświeżania i wybierz przeładowanie bez cache.

---

## CZĘŚĆ D — sprawdzenie, że działa

### D1. Magazyn — przewijanie

Wejdź w zakładkę **Magazyn**. Na górze zostaje tylko tytuł „Magazyn"
i przycisk `+`. Pasek KPI, ostrzeżenie o ofertach poza magazynem,
wyszukiwarka i chipy filtrów są **nad pierwszą kartą i przewijają się
razem z listą** — znikają przy przewijaniu w dół i wracają, gdy
wrócisz na górę.

Na ekranie mieści się teraz 7 kart zamiast 3.

### D2. Magazyn — czytelność stanu

Przewiń listę i sprawdź:

- produkty **bez ustawionego progu alertu** nie mają już paska pod liczbą
  sztuk — została sama liczba, teraz większa,
- produkty z ustawionym **stanem docelowym** mają pasek proporcjonalny do
  niego, a nie stale pełny,
- produkt na zerze albo poniżej minimum ma liczbę sztuk w kolorze
  (pomarańczowa/czerwona), nie czarną.

Porównanie przed/po dla obu poprawek jest tutaj:
`mobile/docs/podglad-magazyn-stan.html` (otwórz w przeglądarce).

**Jeśli pasek zniknął z większości magazynu i Ci to przeszkadza** — to
znaczy, że warto uzupełnić `max_stock` (stan docelowy) na produktach;
pasek wróci sam i wtedy będzie coś znaczył. Progi ustawia się na
desktopie.

### D3. Marketing nie wchodzi do skrzynki

Na Pi:

```bash
curl -s "http://localhost:8000/api/v1/mail/messages?limit=50" -H "Authorization: Bearer TU_TOKEN" | grep -o "marketing.olx.pl\|newsletter.allegro.pl"
```

**Nic nie powinno się wypisać.** Jeśli coś wypisze — to stare maile,
zapisane przed wdrożeniem; nowe już nie wejdą. Filtr działa od momentu
restartu, nie kasuje wstecz.

Kontrola od drugiej strony — prawdziwa poczta ma dalej przychodzić:

```bash
curl -s http://localhost:8000/api/v1/mail/status -H "Authorization: Bearer TU_TOKEN"
```

`"watch_senders":["allegro","olx"]` bez zmian.

### D4. Powiadomienia z OLX

Czeka na kolejny prawdziwy mail z OLX. Gdy przyjdzie:

| Co przyszło | Tytuł push | Treść |
|---|---|---|
| ktoś kupił Twoje ogłoszenie | **Sprzedano · OLX** | tytuł ogłoszenia + `— stan bez zmian` |
| kupujący napisał | **Nowa wiadomość · OLX** | tytuł ogłoszenia, którego dotyczy |
| zwrot / reklamacja | **Zwrot / reklamacja · OLX** | tytuł ogłoszenia |
| nieznany szablon | **OLX** | temat maila |

Na Telegramie przy sprzedaży dochodzi zdanie **„Stan magazynowy bez
zmian — odejmij go ręcznie"** wraz z wyjaśnieniem dlaczego.

Podgląd wszystkich powiadomień push (łącznie z nowymi kartami OLX
i zwrotem z Allegro Lokalnie): `backend/docs/podglad-powiadomien-push.html`.

Sprzedaż odnajdziesz w panelu OLX po numerze transakcji — ORDLY zapisuje
go w audycie zdarzenia (`OlxEventDetected`, pole `order_id`).

### D5. Zwrot z Allegro Lokalnie ma własny tytuł

Też czeka na prawdziwy mail. Do tej pory zwrot, doręczenie paczki
i anulowanie miały **ten sam** tytuł „Zmiana zamówienia" — teraz zwrot
dostaje „Zwrot / reklamacja".

> **Zastrzeżenie.** W próbkach z Allegro Lokalnie
> (`backend/tests/fixtures/allegro_lokalnie/`) **nie ma ani jednego
> zwrotu**. Wzorzec „zwrot" siedział w kodzie już wcześniej (w grupie
> „zmiana zamówienia") i tylko dostał teraz trafniejszą etykietę. Jeśli
> Allegro Lokalnie nazywa te maile inaczej, zdarzenie wpadnie tam, gdzie
> wpadało dotąd — bez regresu, ale i bez nowego tytułu. Gdy przyjdzie
> pierwszy prawdziwy zwrot, prześlij mi go.

---

## Czego jeszcze brakuje przy OLX

**Zwrotu i reklamacji z OLX nie widzieliśmy** — z czterech przekazanych
maili dwa to sprzedaż, dwa to wiadomość od kupującego. Wzorce „zwrot"
i „reklamacja" są w kodzie, bo te słowa w temacie maila nie znaczą nic
innego, ale nie są potwierdzone na prawdziwej próbce. Jeśli OLX nazywa
je inaczej, taki mail dostanie neutralny tytuł „OLX" zamiast własnego —
czyli powiadomienie dojdzie, tylko mniej precyzyjne. Prześlij pierwszy
taki mail, a dopiszę wzorzec.

**Kwota sprzedaży.** Gdyby OLX kiedyś zaczął podawać ją w mailu, otwiera
się droga do pełnoprawnych zamówień z tego kanału (odjęcie stanów,
przychód, lista „do spakowania") — tak jak działa to dziś dla Allegro
Lokalnie. Pilnuje tego test `TestCzegoWMailuNieMa` w
`backend/tests/unit/infrastructure/test_olx.py`: gdy w mailu pojawi się
kwota, test upadnie i będzie to sygnał, że decyzję warto podjąć od nowa.

---

## Co dokładnie się zmieniło w kodzie

**Telefon**
- `mobile/src/components/StockRow.tsx` — nowa funkcja `stockRatio`
  (`max_stock` → `min_stock * 2` → brak paska), liczba sztuk 21 px
  z kolorem statusu przy niskim stanie. Globalna `typography.statValue`
  nietknięta.
- `mobile/src/screens/StockScreen.tsx` — KPI, ostrzeżenie, wyszukiwarka
  i filtry przeniesione do `ListHeaderComponent`; `keyboardShouldPersistTaps`
  i `keyboardDismissMode` dla listy z wyszukiwarką w środku.
- `mobile/docs/podglad-magazyn-stan.html` — porównanie przed/po.

**Skrzynka**
- `backend/src/app/core/config.py` — `MAIL_EXCLUDE_SENDERS`.
- `backend/src/app/services/mailbox_service.py` — filtr marketingu przed
  zapisem do bazy; publikacja `OlxEventDetected` dla poczty z OLX.
- `backend/src/app/infrastructure/mail/mime.py` + `imap_watcher.py` —
  `looks_like_markup()`. Część `text/plain` maili z OLX zawiera dosłowne
  `<a href="…">Potwierdź sprzedaż</a>`, więc podgląd w Skrzynce
  pokazywałby surowe znaczniki. Teraz „tekst" ze znacznikami przechodzi
  przez ten sam konwerter co HTML.

**OLX**
- `backend/src/app/domain/entities/olx_event.py` — encja zdarzenia
  (tylko pola, które w mailu FAKTYCZNIE są).
- `backend/src/app/infrastructure/mail/olx.py` — parser: klasyfikacja po
  temacie, tytuł ogłoszenia, UUID transakcji z linku.
- `backend/src/app/event_subscriptions.py` — `handle_olx_event`.
- `backend/tests/fixtures/olx/` — cztery przekazane próbki.

**Powiadomienia**
- `notifier.py` + `composite_notifier.py` + Telegram + Web Push —
  `notify_olx_event`.
- `push_payload.py` — builder `olx_event` i katalog `_OLX_TITLES`; nowy
  tytuł `"return"` dla Allegro Lokalnie.
- `infrastructure/mail/allegro_lokalnie.py` + `allegro_lokalnie_event.py`
  — `EVENT_RETURN` wydzielony z `EVENT_ORDER_STATUS`.

**Testy** — 558 przechodzi (przed paczką: 505). Nowe: filtr wykluczeń,
parser OLX na czterech prawdziwych mailach, publikacja zdarzeń OLX,
tytuły i treści push, zwrot z Lokalnie, brak kwoty w mailu OLX.

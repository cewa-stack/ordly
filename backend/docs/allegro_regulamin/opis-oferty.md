# Zasady opisu oferty Allegro (snapshot 2026-08-09)

> Streszczenie oficjalnych zasad Allegro na potrzeby budowy Ordlaka (prompt
> AI + walidacja), nie kopia regulaminu. W razie wątpliwości sprawdź źródła
> poniżej.

**Źródła:**
- [Jakie są zasady dotyczące wystawiania i opisu – Pomoc dla sprzedających](https://help.allegro.com/sell/pl/a/jakie-sa-zasady-dotyczace-wystawiania-i-opisu-6M9EGaKm1SV)
- Regulamin Allegro, Załącznik nr 2 (zasady wystawiania ofert) — [allegro.pl/regulamin/zalacznik/2](https://allegro.pl/regulamin/zalacznik/2)

## Czego nie wolno w opisie oferty

- **Danych kontaktowych**: numer telefonu, adres e-mail, numer konta
  bankowego.
- **Zachęcania do kontaktu/zakupu poza Allegro**: sformułowania typu
  "napisz prywatnie", "kontakt na priv", "zapraszam poza Allegro" —
  traktowane jak dane kontaktowe/elementy ułatwiające transakcję poza
  platformą, niezgodne z regulaminem.
- **Fraz reklamowych i marketingowych**: "gratis", "tanio", "promocja",
  "hit", "prezent" i podobne.
- **Manipulacji wynikami wyszukiwania**: upychanie słów kluczowych
  niezwiązanych bezpośrednio z produktem.
- **Linków**: adresy stron WWW dozwolone tylko gdy nie prowadzi się przez
  nie działalności komercyjnej i treść tylko poszerza wiedzę o produkcie —
  w praktyce dla Ordlaka: **nie generujemy żadnych linków**.
- **Informacji o innych produktach/ofertach** sprzedawcy.
- **Warunków niezwiązanych z samym produktem**: gwarancja, urlopy/przerwy
  w sprzedaży, dane ze stopki "O sprzedającym", **warunki i koszty
  wysyłki/dostawy** — to należy do dedykowanych pól oferty (czas wysyłki,
  cennik dostawy), nie do treści opisu produktu.

## Konsekwencje dla Ordlaka

Prompt do AI (sekcja 6 w `bot.md`) musi jawnie zakazywać:
1. jakichkolwiek danych kontaktowych i zachęt do kontaktu poza Allegro,
2. fraz reklamowych/marketingowych z listy powyżej,
3. wzmianek o wysyłce, dostawie, czasie realizacji, odbiorze osobistym —
   to nie jest treść opisu produktu,
4. linków,
5. informacji o innych ofertach sprzedawcy, gwarancji, warunkach sprzedaży
   niezwiązanych z samym przedmiotem.

Opis ma się skupiać wyłącznie na **cechach i stanie produktu**.

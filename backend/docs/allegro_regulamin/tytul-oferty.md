# Zasady tytułu oferty Allegro (snapshot 2026-08-09)

> To jest streszczenie oficjalnych zasad Allegro na potrzeby budowy Ordlaka
> (żeby prompt AI i walidacja w kodzie zgadzały się z regulaminem), nie
> kopia regulaminu. W razie wątpliwości sprawdź źródła poniżej — Allegro
> mogło zaktualizować zasady.

**Źródła:**
- [Jak stworzyć dobry tytuł oferty – Pomoc dla sprzedających](https://help.allegro.com/sell/pl/a/jak-stworzyc-dobry-tytul-oferty-LR8WePjnbIl)
- [Zmienimy minimalną liczbę znaków i słów w tytule oferty – Allegro Developer Portal](https://developer.allegro.pl/news/zmienimy-minimalna-liczbe-znakow-i-slow-w-tytule-oferty-rjbbekBPohA) (zmiana weszła w życie 7 maja 2025)

## Limity długości

- **Minimum: 12 znaków ze spacjami i 3 słowa** (3 ciągi znaków oddzielone spacjami).
- **Maksimum: 75 znaków.**
- Edycja samej liczby sztuk lub ceny w istniejącej ofercie nie wymusza
  dostosowania tytułu do tych limitów (wyjątek dla starych ofert).

## Czego nie wolno w tytule

- Powtórzeń słów kluczowych (keyword stuffing).
- Informacji o obniżkach cenowych: "tanio", "najtaniej" itp.
- Słów typu "okazja", "nowość", "promocja", "hit".
- Dodatkowych informacji niezwiązanych z samym produktem: login sprzedawcy,
  miasto/odbiór osobisty, wzmianki o fakturach, informacje o wysyłce.
- Numerów magazynowych / oznaczeń wewnętrznych sklepu.
- Znaków specjalnych jako ozdobników (np. `@`, `!`, `[ ]`).
- Nazw marek niezwiązanych z wystawianym produktem.

## Zasada pozytywna

- Tytuł ma dotyczyć **wyłącznie** wystawianego produktu.
- Najważniejsze słowa kluczowe umieszczać **na początku** tytułu.

## Konsekwencje dla Ordlaka

- Twardy limit w promptcie i walidacji backendu: **12–75 znaków, min. 3 słowa**.
- **Decyzja produktowa (2026-08-09): Ordlak celuje zawsze w 74–75 znaków**,
  nie tylko w minimum regulaminowe — im więcej realnych atrybutów produktu
  w tytule, tym więcej fraz wyszukiwania, na które oferta może się trafić.
  Dopisywane atrybuty muszą być prawdziwe i różne od siebie (marka, model,
  kolor, rozmiar, materiał, pojemność, przeznaczenie) — nie wolno wypełniać
  długości powtórzeniami tego samego słowa (to jest keyword stuffing,
  zakazane niżej).
- Blacklista fraz do odrzucenia/przefiltrowania w wygenerowanym tytule:
  `tanio`, `najtaniej`, `okazja`, `nowość`, `promocja`, `hit`, `gratis`.
- Zakaz wzmianek o wysyłce/odbiorze osobistym/fakturach w tytule.

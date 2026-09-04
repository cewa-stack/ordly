# ORDLY Mobile — Słabo widoczny stan magazynowy przy przewijaniu listy

## Zgłoszony problem
Nagranie ekranu pokazuje listę „Magazyn” w aplikacji mobilnej — podczas
przewijania stan poszczególnych produktów (pasek zapasu przy każdej
karcie) jest słabo widoczny/nieczytelny.

## Przyczyna znaleziona w kodzie (potwierdzona, nie domysł)

`mobile/src/components/StockRow.tsx`, linia 21 — wzór na wypełnienie
paska zapasu przy każdej karcie produktu:

```tsx
const ratio = item.min_stock > 0 ? item.stock / (item.min_stock * 2) : item.stock > 0 ? 1 : 0;
```

**Gdy produkt nie ma ustawionego progu minimalnego (`min_stock === 0`,
co jest naturalnym stanem — pole jest opcjonalne przy tworzeniu
produktu, patrz `StockScreen.tsx` „Próg alertu w szt. (opcjonalnie)”),
`ratio` wynosi `1` dla KAŻDEJ dodatniej ilości.** Pasek pokazuje więc
100% wypełnienia niezależnie od tego, czy na stanie jest 5 sztuk, czy
5000 — pasek nie niesie żadnej informacji o faktycznej ilości. Przy
przewijaniu listy wszystkie takie karty wyglądają identycznie (pełny,
zielony pasek), więc „stan” faktycznie nie jest widoczny — dokładnie
objaw z nagrania.

To nie jest kwestia kontrastu kolorów czy animacji przy scrollu (paleta
`theme/colors.ts` ma odpowiedni kontrast tekst/tło) — pasek po prostu
**nie odzwierciedla rzeczywistej ilości** dla produktów bez ustawionego
minimum, a to prawdopodobnie większość magazynu (próg jest opcjonalny).

## Rozwiązanie

### 1. Popraw wzór wypełnienia paska — użyj `max_stock`, gdy jest dostępny
`StockItem` (typ w `mobile/src/api/types.ts`) ma już pole `max_stock:
number | null`, ale `StockRow.tsx` go dziś nie używa. To najdokładniejszy
dostępny mianownik.

```tsx
function stockRatio(item: StockItem): number {
  if (item.max_stock && item.max_stock > 0) {
    return item.stock / item.max_stock;
  }
  if (item.min_stock > 0) {
    return item.stock / (item.min_stock * 2);
  }
  // Brak progu i brak max_stock - nie ma z czym porównać ilości.
  // Pasek NIE ma udawać 100%, żeby nie sugerować "pełnego stanu"
  // bez podstawy - patrz punkt 2.
  return -1; // sygnał "brak danych do proporcji", obsłużony niżej
}
```

### 2. Gdy nie ma ani `max_stock`, ani `min_stock` — nie udawaj paska
Zamiast fałszywego 100%, dla tego przypadku:
- pokaż pasek w stałej, niskiej, NEUTRALNEJ szerokości (np. 25%, kolor
  `colors.trackStock`/`textDim`, nie status), sygnalizującej „brak progu
  odniesienia” zamiast fałszywego „pełno”, **albo**
- (preferowane, prostsze i uczciwsze) ukryj pasek dla tych kart i
  pokaż tylko liczbę sztuk — użytkownik i tak widzi dokładną wartość w
  `styles.qty`, a pasek bez punktu odniesienia i tak nic nie wnosi.

Zdecyduj na etapie implementacji, które rozwiązanie lepiej komponuje
się wizualnie z resztą listy — obie opcje są poprawne, ważne żeby żadna
karta bez `max_stock`/`min_stock` nie pokazywała paska w 100%.

### 3. Zwiększ czytelność liczby sztuk podczas szybkiego przewijania
Skoro pasek nie zawsze będzie dostępny (punkt 2), liczba `{item.stock}
szt.` (`styles.qty`, `typography.statValue`, 18px/700) staje się
głównym nośnikiem informacji o stanie. Rozważ (do oceny wizualnej,
niekoniecznie wszystko naraz):
- Zwiększenie `fontSize` z 18 do ok. 20–22 dla `styles.qty` na karcie
  magazynowej (osobny wariant typografii, nie zmieniaj globalnego
  `typography.statValue` używanego gdzie indziej).
- Upewnij się, że kolor cyfry przy statusie `critical`/`warning`
  koresponduje z paskiem (dziś tylko pasek zmienia kolor przez
  `stockStatusColor`, tekst `qty` zawsze ma `colors.text`) — przy
  statusie krytycznym/niskim liczba też powinna przejąć kolor
  `colors.danger`/`colors.warning`, żeby rzucała się w oczy przy
  szybkim przewijaniu, nie tylko mały pasek 60px szerokości.

### 4. Sprawdź wydajność listy przy przewijaniu (drugorzędne, do weryfikacji)
Jeśli po poprawkach 1–3 podczas oglądania nagrania nadal widać
„migotanie”/urywanie się treści przy szybkim scrollu (a nie tylko
nieczytelność wynikającą z zawsze-pełnego paska) — sprawdź, czy `FlatList`
w `StockScreen.tsx` (linia ~224) korzysta z `getItemLayout` (karty mają
w praktyce zmienną wysokość przez `lowFlag`, więc `getItemLayout` może
nie być trywialne) oraz czy `windowSize`/`initialNumToRender` nie
wymagają dostrojenia dla list z dużą liczbą SKU. To osobny, potencjalnie
zbędny krok — zrób go TYLKO jeśli po naprawie punktu 1–2 problem nadal
widać na nagraniu; najpierw popraw dane, potem oceniaj wydajność.

## Kryteria akceptacji

1. Produkt z `stock=5`, bez ustawionego `min_stock` i `max_stock`, oraz
   produkt z `stock=500` w tym samym stanie NIE wyglądają identycznie na
   liście — różnica w ilości musi być widoczna (przez liczbę, i/lub
   przez pasek jeśli punkt 2 wybierze wariant z neutralnym paskiem
   zamiast ukrycia go).
2. Produkt z ustawionym `max_stock` pokazuje pasek proporcjonalny do
   `stock / max_stock`, nie do starego przybliżenia `min_stock * 2`.
3. Żaden produkt nie pokazuje paska 100% tylko dlatego, że nie ma
   ustawionego progu — to była realna przyczyna zgłoszonego problemu.
4. Wizualna kontrola na prawdziwej liście magazynu (z różnymi
   kombinacjami: sam `min_stock`, sam `max_stock`, oba, żadne) — najlepiej
   zrzut ekranu/nagranie porównawcze przed i po, do mojej akceptacji,
   analogicznie do podglądu wymaganego przy poprzedniej naprawie
   powiadomień push.

## Czego NIE robić

- Nie zmieniaj globalnej `typography.statValue` używanej w innych
  miejscach aplikacji (np. pasek KPI na górze ekranu) — jeśli zmieniasz
  rozmiar cyfry na karcie magazynowej, zrób to jako osobny, lokalny
  styl w `StockRow.tsx`.
- Nie usuwaj informacji o statusie (`is_low_stock`/`status`) — flaga
  „poniżej minimum — zamów dostawę” (`lowFlag`) zostaje bez zmian, to
  osobny, działający już mechanizm.
- Nie wprowadzaj żadnej zmiany bez pokazania mi porównania przed/po na
  realnych danych z magazynu — to samo podejście co przy poprzedniej
  naprawie (najpierw podgląd/akceptacja, potem wdrożenie), żeby uniknąć
  poprawki, która "działa w kodzie" ale wygląda inaczej niż oczekiwane.

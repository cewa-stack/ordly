# Bug #1 — Odwrócona kolejność wiadomości w zakładce "Dyskusja" + widoczne surowe tagi HTML

## 1. Opis problemu

W widoku pojedynczej dyskusji/czatu (zakładka **Dyskusja**) wiadomości są ułożone **najnowsze na górze, najstarsze na dole**. To odwrotnie niż w standardowych komunikatorach (Messenger, WhatsApp, iMessage), gdzie najnowsza wiadomość jest zawsze na dole, a użytkownik czyta od góry do dołu chronologicznie i scrolluje w dół po nową treść.

Dodatkowo w treści wiadomości systemowych (np. wiadomość od "Allegro" w dyskusji) widoczne są **surowe znaczniki HTML jako tekst**, np.:

```
Dyskusja trwa już 14 dni.<br>Rexpiot, czy udało Ci się porozumieć ze Sprzedającym?<br><br>Jeśli problem został rozwiązany, <strong>zakończ Dyskusję</strong>...
```

zamiast wyrenderowanej, czytelnej wiadomości z akapitami i pogrubieniem.

**Źródło problemu (zrzut ekranu):** widok dyskusji w aplikacji ORDLY (mobile), zamówienie `#deeb2fc0-8419-11f1-bed3-7de93eca4a57`.

## 2. Analiza przyczyny

### 2.1 Kolejność wiadomości
Allegro REST API (`GET /messaging/threads/{id}/messages` lub odpowiedni endpoint dyskusji) najprawdopodobniej zwraca wiadomości w kolejności **od najnowszej do najstarszej** (typowe dla API paginowanych — najnowsze rekordy pierwsze, żeby łatwo pobrać "co nowego"). Problem pojawia się, gdy ta kolejność z API jest **renderowana 1:1** w UI bez odwrócenia — czyli lista wiadomości nie jest sortowana/odwracana przed wyświetleniem w komponencie czatu.

### 2.2 Surowe tagi HTML
Treść wiadomości z Allegro (szczególnie automatyczne komunikaty systemowe, np. przypomnienia o dyskusji) przychodzi z API **jako HTML** (zawiera `<br>`, `<strong>`, czasem `<a href="...">`). Aplikacja najwyraźniej renderuje to pole jako **zwykły tekst** (`<Text>{message.content}</Text>` w React Native / zwykły string w JSX), zamiast:
- sparsować HTML i wyrenderować go jako faktyczny formatowany tekst, albo
- oczyścić/skonwertować HTML na czysty tekst przed wyświetleniem (strip tagów + zamiana `<br>` na znak nowej linii).

## 3. Sposób naprawy

### 3.1 Kolejność wiadomości — sortowanie po stronie klienta (lub backendu)

Niezależnie od kolejności zwracanej przez API Allegro, **przed renderem lista wiadomości musi być posortowana rosnąco po dacie** (`created_at` / `date`, najstarsza pierwsza), tak żeby ostatni element tablicy = najnowsza wiadomość = wyświetlana na dole.

Przykład (frontend, TypeScript/React):

```ts
// utils/sortMessages.ts
export function sortMessagesAscending<T extends { createdAt: string }>(messages: T[]): T[] {
  return [...messages].sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
  );
}
```

```tsx
// DiscussionThreadScreen.tsx
const sortedMessages = useMemo(
  () => sortMessagesAscending(rawMessages),
  [rawMessages]
);

<FlatList
  data={sortedMessages}
  keyExtractor={(item) => item.id}
  renderItem={({ item }) => <MessageBubble message={item} />}
  // kluczowe dla UX czatu: startuje wyscrollowany na dole (najnowsza wiadomość widoczna)
  inverted={false}
  onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
/>
```

**Alternatywa (często wygodniejsza w RN):** użyć `inverted` na `FlatList` z listą **odwróconą** (najnowsza na indeksie 0) — wtedy `FlatList` sam renderuje od dołu do góry i nowe wiadomości "wjeżdżają" na dół bez ręcznego `scrollToEnd`. Wybierz jedno podejście i bądź konsekwentny w całej apce (desktop Electron + mobile Expo powinny mieć tę samą logikę sortowania, żeby zachowanie było spójne między platformami).

**Ważne:** jeśli backend (ORDLY) cache'uje/zapisuje wiadomości w SQLite zanim trafią do UI, rozważ sortowanie **już na poziomie zapytania SQL** (`ORDER BY created_at ASC`), żeby frontend zawsze dostawał gotową, poprawną kolejność i nie musiał tego robić samodzielnie w kilku miejscach (mniej okazji do powielenia buga na nowym ekranie).

### 3.2 Renderowanie HTML zamiast surowego tekstu

Dwie opcje, w kolejności rekomendacji:

**Opcja A (zalecana) — wyrenderuj HTML jako faktyczny formatowany tekst**

- **Mobile (React Native / Expo):** biblioteka `react-native-render-html` — renderuje `<br>`, `<strong>`, `<a>` jako prawdziwe elementy UI (nowa linia, pogrubienie, klikalny link).
  ```bash
  npm install react-native-render-html
  ```
  ```tsx
  import RenderHTML from 'react-native-render-html';

  <RenderHTML
    contentWidth={width}
    source={{ html: message.content }}
    baseStyle={{ fontSize: 15, color: '#313E37' }}
  />
  ```

- **Desktop (Electron/React):** treść jest już w przeglądarce (Chromium), więc wystarczy **bezpieczne** wstawienie HTML — ale **nigdy** przez `dangerouslySetInnerHTML` bez sanitizacji (ryzyko XSS, jeśli kiedyś jakiś nadawca wstrzyknie złośliwy skrypt w treść wiadomości). Użyj `dompurify`:
  ```bash
  npm install dompurify
  ```
  ```tsx
  import DOMPurify from 'dompurify';

  <div
    className="message-content"
    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(message.content) }}
  />
  ```

**Opcja B (szybszy patch, mniej ładny UX)** — jeśli nie chcesz na razie renderować pełnego HTML, przynajmniej **oczyść tekst** przed wyświetleniem jako plain text:

```ts
function htmlToPlainText(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?strong>/gi, '')
    .replace(/<a[^>]*>(.*?)<\/a>/gi, '$1')
    .replace(/<[^>]+>/g, '') // usuń resztę nieznanych tagów
    .trim();
}
```
To rozwiązuje problem "widać `<br>` na ekranie", ale traci formatowanie (pogrubienie, linki). Opcja A jest docelowo lepsza — wybierz B tylko jako tymczasowy hotfix, jeśli czas naglący.

## 4. Jak zweryfikować, że wczytuje się poprawnie

1. Otwórz dyskusję z co najmniej 3 wiadomościami o różnych znacznikach czasu (najlepiej testową dyskusję z historycznymi wiadomościami z różnych dni).
2. Sprawdź, czy **najstarsza wiadomość jest na górze ekranu**, a **najnowsza na dole** — dokładnie przy polu do wpisania odpowiedzi (jak w Messengerze).
3. Wyślij nową (testową) wiadomość w dyskusji — powinna pojawić się **na dole**, a widok powinien automatycznie przescrollować, żeby ją pokazać.
4. Znajdź dyskusję z automatyczną wiadomością systemową od Allegro (typu przypomnienie "Dyskusja trwa już X dni") i sprawdź, czy:
   - **nie widać** surowych tagów `<br>`, `<strong>`, `<a href=...>` jako tekstu,
   - nowe linie / akapity są poprawnie widoczne (nie jeden zlepiony blok tekstu),
   - jeśli w treści jest link (np. do "Allegro Ochrona Kupujących") — jest on **klikalny**, a nie widoczny jako surowy `<a href="...">...</a>`.
5. Powtórz punkty 2–4 zarówno na **mobile (Expo)**, jak i **desktop (Electron)** — obie platformy powinny mieć identyczne zachowanie.
6. Regresja: sprawdź inne miejsca w apce, które renderują treść wiadomości z Allegro (np. podgląd ostatniej wiadomości na liście dyskusji/wątków) — jeśli tam też pojawia się surowy HTML, zastosuj tę samą naprawę (opcja A/B) w tym komponencie.

## 5. Checklist wdrożenia do ORDLY

- [ ] Dodaj/zweryfikuj sortowanie wiadomości rosnąco po dacie (frontend i/lub zapytanie SQL w backendzie)
- [ ] Zaimplementuj renderowanie HTML (`react-native-render-html` na mobile, `dompurify` + `dangerouslySetInnerHTML` na desktop)
- [ ] Upewnij się, że `scrollToEnd`/`inverted` działa poprawnie przy otwarciu ekranu i przy nowej wiadomości
- [ ] Sprawdź wszystkie miejsca z podglądem treści wiadomości (lista wątków, powiadomienia push) pod kątem tego samego problemu z surowym HTML
- [ ] Test na min. 1 realnej dyskusji z wiadomością systemową Allegro + min. 1 z wieloma wiadomościami użytkownika
- [ ] Test na obu platformach (mobile + desktop)

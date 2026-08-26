# Bug #2 — W zakładce "Wiadomość" (mail) widać surowy kod HTML zamiast treści maila

## 1. Opis problemu

W widoku pojedynczej wiadomości e-mail (zakładka **Wiadomość**, np. mail od `powiadomienia@allegro.pl` z tematem "Dyskusja - nowa wiadomość od naszego doradcy") aplikacja wyświetla **surowy kod źródłowy HTML** całej wiadomości:

```
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"...
<html lang="pl" xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html charset=UTF-8" />
    ...
```

zamiast wyrenderowanej, czytelnej treści maila (tak jak wygląda w Gmailu czy dowolnym kliencie pocztowym). Użytkownik dostaje link zastępczy "Otwórz pełną wiadomość w Gmail →", co pokazuje, że aplikacja **świadomie zrezygnowała** z renderowania treści i pokazuje surowy `.eml`/HTML source jako fallback.

**Źródło problemu (zrzut ekranu):** widok pojedynczego maila w module Unified Mail Inbox w aplikacji ORDLY (mobile).

## 2. Analiza przyczyny

To jest inny problem niż Bug #1 (tam chodziło o pojedyncze inline tagi typu `<br>` w krótkiej wiadomości z API Allegro). Tutaj mamy do czynienia z **pełnym dokumentem HTML** pobranym przez IMAP (cały `Content-Type: text/html` z nagłówkiem `<!DOCTYPE...>`, `<head>`, stylami itd.) — czyli treść całego maila w formacie MIME multipart, z którego aplikacja **nie wyciąga i nie renderuje** właściwej części HTML, tylko wrzuca surowy string na ekran jako plain text.

Najbardziej prawdopodobne przyczyny (jedna lub więcej):

1. **Brak parsowania MIME** — mail pobrany przez IMAP jest wielo-częściowy (multipart/alternative: część `text/plain` + część `text/html`), a kod parsujący bierze surowy `payload` całej wiadomości zamiast wyciągnąć konkretną część `text/html` i przekazać ją do renderera.
2. **Brak komponentu do renderowania HTML maila** — nawet jeśli treść HTML jest poprawnie wyciągnięta, jest wstawiana jako zwykły tekst (`<Text>{email.body}</Text>`) zamiast do WebView/iframe/render-HTML komponentu.
3. Fallback "Otwórz pełną wiadomość w Gmail" sugeruje, że deweloper **świadomie obszedł problem** zamiast go naprawić — czyli renderowanie HTML maili nie zostało jeszcze zaimplementowane, tylko dodano link ratunkowy.

## 3. Sposób naprawy

### 3.1 Backend (ORDLY) — poprawne parsowanie MIME

Mail pobrany przez IMAP musi być sparsowany jako wiadomość MIME, a nie traktowany jako jeden string. W Pythonie:

```python
import email
from email import policy
from email.parser import BytesParser

def parse_email_body(raw_bytes: bytes) -> dict:
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    html_body = None
    plain_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html" and html_body is None:
                html_body = part.get_content()
            elif content_type == "text/plain" and plain_body is None:
                plain_body = part.get_content()
    else:
        if msg.get_content_type() == "text/html":
            html_body = msg.get_content()
        else:
            plain_body = msg.get_content()

    return {
        "html_body": html_body,   # do renderowania w UI
        "plain_body": plain_body, # fallback / podgląd na liście
        "subject": msg["subject"],
        "from": msg["from"],
        "date": msg["date"],
    }
```

Endpoint API zwracający pojedynczy mail powinien zwracać **osobne pola** `html_body` i `plain_body` (nie jeden zlepiony string), żeby frontend mógł świadomie wybrać, co renderować.

### 3.2 Frontend — renderowanie `html_body` zamiast surowego tekstu

**Desktop (Electron/React):** najbezpieczniejsza opcja dla pełnych dokumentów HTML (ze stylami, `<head>`, czasem zewnętrznymi obrazkami) to **`<iframe sandboxed>`**, a nie `dangerouslySetInnerHTML` — bo maile mają własne style/CSS, które mogłyby "wyciec" i zepsuć resztę UI aplikacji, jeśli wstrzykniesz je bezpośrednio w DOM:

```tsx
function EmailBodyViewer({ htmlBody }: { htmlBody: string }) {
  return (
    <iframe
      title="email-content"
      sandbox="allow-same-origin" // BEZ allow-scripts — blokuje wykonanie JS z maila
      srcDoc={htmlBody}
      style={{ width: '100%', height: '100%', border: 'none' }}
    />
  );
}
```

`sandbox="allow-same-origin"` bez `allow-scripts` zapewnia, że nawet złośliwy JS wstrzyknięty w mail **nie wykona się** — kluczowe, bo maile to niezaufana treść z zewnątrz.

**Mobile (Expo/React Native):** użyj `react-native-webview` (nie da się bezpiecznie renderować pełnego HTML przez zwykły `<Text>` ani `react-native-render-html` przy dużych, złożonych mailach ze stylami — WebView jest właściwym narzędziem do pełnych dokumentów HTML):

```bash
npx expo install react-native-webview
```

```tsx
import { WebView } from 'react-native-webview';

<WebView
  originWhitelist={['*']}
  source={{ html: emailHtmlBody }}
  javaScriptEnabled={false}   // blokuj JS z maila — bezpieczeństwo
  style={{ flex: 1 }}
/>
```

### 3.3 Fallback, gdy `html_body` jest puste/uszkodzone

Jeśli parsowanie MIME się nie powiedzie (np. mail bez części `text/html`), pokaż `plain_body` jako zwykły tekst zamiast surowego źródła HTML lub linku "otwórz w Gmailu":

```tsx
{email.html_body ? (
  <EmailBodyViewer htmlBody={email.html_body} />
) : email.plain_body ? (
  <Text>{email.plain_body}</Text>
) : (
  <Text style={{ color: '#888' }}>Nie udało się wczytać treści wiadomości.</Text>
)}
```

To eliminuje potrzebę linku "Otwórz pełną wiadomość w Gmail" jako jedynej ścieżki — apka powinna umieć pokazać mail samodzielnie w >95% przypadków.

## 4. Jak zweryfikować, że wczytuje się poprawnie

1. Otwórz w Unified Mail Inbox mail, który wcześniej pokazywał surowy `<!DOCTYPE HTML...>` (np. ten sam mail od `powiadomienia@allegro.pl`).
2. Sprawdź, że treść jest **wyrenderowana wizualnie** (czcionki, akapity, ewentualne logo/kolory Allegro), a nie widoczna jako tekst źródłowy.
3. Sprawdź, że **żaden JavaScript z maila się nie wykonuje** (brak popupów, przekierowań) — celowo przetestuj na mailu z reklamowej wysyłki, jeśli taki masz w skrzynce, żeby upewnić się, że sandboxing działa.
4. Sprawdź mail, który **nie ma** części HTML (czysty plain text) — upewnij się, że pokazuje się jako zwykły tekst, a nie pusty ekran ani błąd.
5. Sprawdź długi mail ze zdjęciami/inline obrazkami — obrazki powinny się wczytać (o ile `WebView`/`iframe` ma dostęp do sieci) lub sensownie się nie wyświetlić bez wywalania całego widoku.
6. Powtórz test na **mobile (Expo/WebView)** i **desktop (Electron/iframe)** — upewnij się, że oba mają spójne zachowanie i że link "Otwórz pełną wiadomość w Gmail" nie jest już jedynym sposobem przeczytania maila (może zostać jako opcja dodatkowa, ale nie fallback na brak renderowania).
7. Sprawdź czas ładowania na słabszym połączeniu (np. LTE) — WebView/iframe z dużym mailem HTML nie powinien blokować UI apki (dodaj loader/spinner na czas ładowania).

## 5. Checklist wdrożenia do ORDLY

- [ ] Backend: parsowanie MIME wyciągające osobno `html_body` i `plain_body` z każdego pobranego maila (IMAP)
- [ ] API zwraca oba pola zamiast jednego zlepionego stringa
- [ ] Desktop: `iframe` z `sandbox="allow-same-origin"` (bez `allow-scripts`) do renderowania `html_body`
- [ ] Mobile: `react-native-webview` z `javaScriptEnabled={false}` do renderowania `html_body`
- [ ] Fallback na `plain_body`, gdy `html_body` brak/uszkodzone — bez linku "otwórz w Gmailu" jako jedynej opcji
- [ ] Test bezpieczeństwa: mail z osadzonym `<script>` nie wykonuje się w żadnym z widoków
- [ ] Test na min. 3 realnych mailach: HTML z Allegro, plain-text, mail z obrazkami inline
- [ ] Test na obu platformach (mobile + desktop)

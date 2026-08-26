/**
 * Przygotowanie treści maila do wyswietlenia w izolowanym `<iframe>`.
 *
 * Maila NIE wstawiamy do DOM-u aplikacji (`dangerouslySetInnerHTML`),
 * mimo ze mamy sanityzator - mail przynosi wlasny arkusz stylow, ktory
 * w jednym drzewie z aplikacja rozjechalby jej layout, a wyciecie tych
 * stylow zrobiloby z maila nieczytelna kolumne tekstu. `<iframe>` daje
 * mailowi wlasny dokument: jego style dzialaja u niego, a do aplikacji
 * nie siegaja.
 *
 * Wynik jest wstawiany jako `srcDoc` ramki z atrybutem
 * `sandbox="allow-popups allow-popups-to-escape-sandbox"` - bez
 * `allow-scripts`, wiec zaden skrypt z maila sie nie wykona (sprawdzone
 * w prawdziwym Chromium; CSP renderera blokuje to samo drugi raz).
 *
 * Odpowiednik po stronie PWA: `mobile/src/components/MailBodyFrame.tsx`.
 */

/**
 * Wstrzykiwane do dokumentu maila:
 * - wlasna CSP dokumentu maila: `default-src 'none'` odcina WSZYSTKIE
 *   zapytania do sieci z tresci maila (obrazki, fonty, ramki, skrypty).
 *   Zostaja tylko style inline (bez nich mail jest nieczytelny) i obrazki
 *   osadzone w tresci jako `data:`. Dzieki temu piksel sledzacy nie
 *   potwierdzi nadawcy, ze wiadomosc zostala otwarta - i zachowanie jest
 *   TAKIE SAMO na desktopie i w PWA, mimo ze tylko desktop ma wlasna CSP
 *   na poziomie aplikacji.
 * - `<base target="_blank">` sprawia, ze KAZDY link otwiera sie jako nowe
 *   okno, czyli trafia do `setWindowOpenHandler` w procesie glownym i dalej
 *   do systemowej przegladarki. Bez tego link probowalby przenawigowac sama
 *   ramke, co CSP i tak blokuje - klikniecie po prostu nic by nie robilo.
 * - styl `img{max-width:100%}` powstrzymuje szerokie obrazki maila przed
 *   rozpychaniem ramki w poziomie.
 *
 * Kolejnosc ma znaczenie: `<meta>` z CSP musi stac przed czymkolwiek, co
 * moglaby ograniczyc, wiec wstrzykujemy to zaraz za otwarciem `<head>`.
 */
const INJECTED_HEAD =
  '<meta http-equiv="Content-Security-Policy" ' +
  "content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'; " +
  'font-src data:">' +
  '<base target="_blank">' +
  "<style>html{background:#fff}body{margin:0;padding:14px;" +
  "font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:#111}" +
  "img{max-width:100%;height:auto}table{max-width:100%}</style>";

const HEAD_OPEN = /<head\b[^>]*>/i;
const HTML_OPEN = /<html\b[^>]*>/i;

/** Czy tresc maila odwoluje sie do obrazkow spoza wiadomosci. */
const REMOTE_IMAGE = /<img\b[^>]*\ssrc\s*=\s*["']?https?:/i;

export function buildMailDocument(html: string): string {
  if (HEAD_OPEN.test(html)) {
    return html.replace(HEAD_OPEN, (head) => head + INJECTED_HEAD);
  }
  if (HTML_OPEN.test(html)) {
    return html.replace(HTML_OPEN, (open) => `${open}<head>${INJECTED_HEAD}</head>`);
  }
  // Fragment bez wlasnego szkieletu dokumentu - dokladamy minimalny,
  // zeby przegladarka nie musiala zgadywac kodowania.
  return `<!doctype html><html lang="pl"><head><meta charset="utf-8">${INJECTED_HEAD}</head><body>${html}</body></html>`;
}

/**
 * Czy warto uprzedzic uzytkownika, ze obrazkow nie zobaczy.
 *
 * Obrazki z sieci sa blokowane celowo (patrz CSP w `INJECTED_HEAD`) - to
 * najczesciej piksele sledzace, ktore potwierdzalyby nadawcy otwarcie
 * wiadomosci. Mail bez nich nadal jest czytelny, ale milczaca dziura w
 * ukladzie wyglada jak awaria, wiec przy takim mailu pokazujemy jedno
 * zdanie wyjasnienia (i link do Gmaila, gdzie obrazki sie zaladuja).
 */
export function hasRemoteImages(html: string): boolean {
  return REMOTE_IMAGE.test(html);
}

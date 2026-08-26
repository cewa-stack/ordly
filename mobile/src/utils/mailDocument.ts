/**
 * Przygotowanie treści maila do wyświetlenia w izolowanej ramce.
 *
 * Bliźniak `desktop/src/renderer/src/lib/mailDocument.ts` - obie
 * platformy mają pokazywać ten sam mail tak samo, więc wstrzykiwana
 * głowa dokumentu jest identyczna. Zmiana tutaj powinna iść w parze ze
 * zmianą tam.
 */

/**
 * Wstrzykiwane do dokumentu maila:
 * - własna CSP dokumentu: `default-src 'none'` odcina WSZYSTKIE zapytania
 *   do sieci z treści maila (obrazki, fonty, ramki, skrypty). Zostają
 *   tylko style inline - bez nich mail jest nieczytelny - i obrazki
 *   osadzone w treści jako `data:`. Dzięki temu piksel śledzący nie
 *   potwierdzi nadawcy, że wiadomość została otwarta. W PWA to JEDYNA
 *   zapora (strona nie ma własnej CSP), więc nie jest to ozdobnik.
 * - `<base target="_blank">` otwiera każdy link w nowej karcie zamiast
 *   przenawigowywać ramkę z mailem.
 * - `img{max-width:100%}` powstrzymuje szerokie obrazki przed
 *   rozpychaniem ramki w poziomie na wąskim ekranie telefonu.
 *
 * Kolejność ma znaczenie: `<meta>` z CSP musi stać przed czymkolwiek, co
 * mogłaby ograniczyć, więc wstrzykujemy to zaraz za otwarciem `<head>`.
 */
const INJECTED_HEAD =
  '<meta http-equiv="Content-Security-Policy" ' +
  "content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'; " +
  'font-src data:">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<base target="_blank">' +
  "<style>html{background:#fff}body{margin:0;padding:14px;" +
  "font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif;font-size:14px;" +
  "line-height:1.5;color:#232B27;word-wrap:break-word}" +
  "img{max-width:100%;height:auto}table{max-width:100%}</style>";

const HEAD_OPEN = /<head\b[^>]*>/i;
const HTML_OPEN = /<html\b[^>]*>/i;

/** Czy treść maila odwołuje się do obrazków spoza wiadomości. */
const REMOTE_IMAGE = /<img\b[^>]*\ssrc\s*=\s*["']?https?:/i;

export function buildMailDocument(html: string): string {
  if (HEAD_OPEN.test(html)) {
    return html.replace(HEAD_OPEN, (head) => head + INJECTED_HEAD);
  }
  if (HTML_OPEN.test(html)) {
    return html.replace(HTML_OPEN, (open) => `${open}<head>${INJECTED_HEAD}</head>`);
  }
  // Fragment bez własnego szkieletu dokumentu - dokładamy minimalny,
  // żeby przeglądarka nie musiała zgadywać kodowania.
  return `<!doctype html><html lang="pl"><head><meta charset="utf-8">${INJECTED_HEAD}</head><body>${html}</body></html>`;
}

/**
 * Czy uprzedzić użytkownika, że obrazków nie zobaczy - patrz CSP wyżej.
 * Bez tego zdania dziura po zablokowanym obrazku wygląda jak awaria.
 */
export function hasRemoteImages(html: string): boolean {
  return REMOTE_IMAGE.test(html);
}

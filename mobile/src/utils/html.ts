/**
 * Mini-parser bezpiecznego podzbioru HTML, który Allegro wstawia w treść
 * wiadomości dyskusji/reklamacji.
 *
 * Dlaczego własny parser, a nie `react-native-render-html`: apka jest
 * jednocześnie natywnym Expo i PWA w Safari (patrz `src/push/webPush.ts`),
 * a wiadomości Allegro używają zaledwie kilku znaczników inline
 * (`<br>`, `<strong>`, `<em>`, `<p>`, `<a>`). Dokładanie biblioteki
 * renderującej pełny HTML dla tych pięciu przypadków to nowa zależność
 * w bundlu PWA i nowy powód do konfliktu wersji z Expo 51 - a pokrycie
 * jest identyczne. Znaczniki spoza listy tracą tag, ale ZOSTAWIAJĄ swój
 * tekst, więc nawet nieznany szablon Allegro nie gubi treści.
 *
 * Odpowiednik po stronie desktopu to `desktop/src/renderer/src/lib/
 * sanitizeHtml.ts` - obie platformy trzymają tę samą regułę: tekst bez
 * znaczników renderujemy dosłownie (żeby nie zjeść znaków nowej linii
 * z wiadomości wpisanej przez człowieka), a HTML dopiero parsujemy.
 */

/** Fragment tekstu o jednolitym stylu - jednostka renderowania w `RichText`. */
export interface HtmlSegment {
  text: string;
  bold: boolean;
  italic: boolean;
  /** Adres do otwarcia, gdy fragment jest linkiem; `null` dla zwykłego tekstu. */
  href: string | null;
}

/**
 * Czy treść w ogóle zawiera znaczniki HTML.
 *
 * Wiadomości w wątku przychodzą mieszane: komunikaty systemowe Allegro
 * są HTML-em, a to, co wpisał człowiek, to zwykły tekst ze znakami nowej
 * linii. Bez tego rozdziału parser zjadałby te znaki i cała odpowiedź
 * sprzedawcy zlewała się w jeden akapit.
 */
export function looksLikeHtml(text: string): boolean {
  return /<\/?[a-z][^>]*>/i.test(text);
}

/** Protokoły, które wolno otworzyć z linku w treści od obcego nadawcy. */
const SAFE_LINK_PROTOCOLS = ["http://", "https://", "mailto:"];

/**
 * Encje, które realnie pojawiają się w polskich szablonach Allegro.
 * Encje numeryczne (`&#243;`) idą ścieżką ogólną w `decodeHtmlEntities`;
 * encja nierozpoznana zostaje w tekście dosłownie, zamiast zniknąć.
 */
const NAMED_ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  // Twarda spacja celowo NIE jest zwykłą spacją - inaczej kolaps białych
  // znaków w `pushText` zjadłby ją razem z sąsiednimi.
  nbsp: "\u00a0",
  ndash: "–",
  mdash: "—",
  hellip: "…",
  bdquo: "„",
  rdquo: "”",
  lsquo: "‘",
  rsquo: "’",
  laquo: "«",
  raquo: "»",
  middot: "·",
  oacute: "ó",
  eacute: "é",
};

export function decodeHtmlEntities(text: string): string {
  return text.replace(/&(#[0-9]+|#x[0-9a-f]+|[a-z][a-z0-9]*);/gi, (match, body: string) => {
    if (body.startsWith("#")) {
      const isHex = body[1] === "x" || body[1] === "X";
      const code = isHex ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      if (!Number.isFinite(code) || code <= 0 || code > 0x10ffff) return match;
      return String.fromCodePoint(code);
    }
    const named = NAMED_ENTITIES[body.toLowerCase()];
    return named ?? match;
  });
}

interface TagInfo {
  name: string;
  isClosing: boolean;
  href: string | null;
}

function parseTag(raw: string): TagInfo | null {
  const match = /^<\s*(\/?)\s*([a-z][a-z0-9]*)/i.exec(raw);
  if (!match) return null;
  const hrefMatch = /href\s*=\s*("([^"]*)"|'([^']*)')/i.exec(raw);
  const href = hrefMatch ? (hrefMatch[2] ?? hrefMatch[3] ?? null) : null;
  return {
    name: match[2].toLowerCase(),
    isClosing: match[1] === "/",
    href,
  };
}

function safeHref(raw: string | null): string | null {
  if (!raw) return null;
  const trimmed = decodeHtmlEntities(raw).trim();
  // Adres względny w treści od Allegro znaczy allegro.pl - inaczej link
  // byłby martwy, bo telefon nie ma kontekstu strony, z której przyszedł.
  const absolute = trimmed.startsWith("/") ? `https://allegro.pl${trimmed}` : trimmed;
  const lower = absolute.toLowerCase();
  return SAFE_LINK_PROTOCOLS.some((protocol) => lower.startsWith(protocol)) ? absolute : null;
}

/** Rozkłada HTML na listę fragmentów o jednolitym stylu. */
export function parseInlineHtml(html: string): HtmlSegment[] {
  const segments: HtmlSegment[] = [];
  const linkStack: string[] = [];
  let bold = 0;
  let italic = 0;
  /** Głębokość wejścia w `<script>`/`<style>` - ich treść nie jest tekstem. */
  let mutedDepth = 0;

  function append(text: string): void {
    if (!text) return;
    const href = linkStack.length > 0 ? linkStack[linkStack.length - 1] : "";
    const isBold = bold > 0;
    const isItalic = italic > 0;
    const last = segments[segments.length - 1];
    if (last && last.bold === isBold && last.italic === isItalic && (last.href ?? "") === href) {
      last.text += text;
    } else {
      segments.push({ text, bold: isBold, italic: isItalic, href: href || null });
    }
  }

  /** Ile znaków nowej linii stoi na końcu dotychczasowego wyniku. */
  function trailingNewlines(): number {
    let count = 0;
    for (let index = segments.length - 1; index >= 0; index -= 1) {
      const text = segments[index].text;
      const atEnd = /\n*$/.exec(text)?.[0].length ?? 0;
      count += atEnd;
      if (atEnd < text.length) break;
    }
    return count;
  }

  /** Spacja tuż przed złamaniem linii jest w renderze widoczna jako dziura. */
  function trimTrailingSpaces(): void {
    while (segments.length > 0) {
      const last = segments[segments.length - 1];
      const trimmed = last.text.replace(/[ \t]+$/, "");
      if (trimmed === last.text) return;
      last.text = trimmed;
      if (last.text.length > 0) return;
      segments.pop();
    }
  }

  function pushText(raw: string): void {
    if (mutedDepth > 0) return;
    // Reguła białych znaków z HTML: ciąg spacji/tabów/nowych linii to
    // JEDNA spacja. Wchodzimy tu wyłącznie dla treści, która faktycznie
    // ma znaczniki (patrz `looksLikeHtml`), więc wiadomość wpisana przez
    // człowieka - z prawdziwymi znakami nowej linii - nigdy nie trafia
    // pod ten kolaps.
    let text = decodeHtmlEntities(raw).replace(/[ \t\r\n\f]+/g, " ");
    if (!text) return;
    if ((segments.length === 0 || trailingNewlines() > 0) && text.startsWith(" ")) {
      text = text.slice(1);
      if (!text) return;
    }
    append(text);
  }

  /** `<br>` - złamanie DOSŁOWNE, więc `<br><br>` daje pustą linię. */
  function pushLineBreak(): void {
    if (segments.length === 0) return;
    trimTrailingSpaces();
    if (segments.length === 0) return;
    append("\n");
  }

  /** Znacznik blokowy - domyka linię/akapit, ale pustych linii nie mnoży. */
  function ensureBreaks(count: number): void {
    if (segments.length === 0) return;
    trimTrailingSpaces();
    if (segments.length === 0) return;
    const missing = count - trailingNewlines();
    if (missing > 0) append("\n".repeat(missing));
  }

  const tagPattern = /<[^>]*>/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = tagPattern.exec(html)) !== null) {
    pushText(html.slice(cursor, match.index));
    cursor = match.index + match[0].length;

    const tag = parseTag(match[0]);
    if (!tag) continue;

    switch (tag.name) {
      case "br":
        if (mutedDepth === 0) pushLineBreak();
        break;
      case "p":
        if (mutedDepth === 0) ensureBreaks(2);
        break;
      case "div":
      case "ul":
      case "ol":
        if (mutedDepth === 0) ensureBreaks(1);
        break;
      case "li":
        if (!tag.isClosing && mutedDepth === 0) {
          ensureBreaks(1);
          append("• ");
        }
        break;
      case "strong":
      case "b":
        bold = Math.max(0, bold + (tag.isClosing ? -1 : 1));
        break;
      case "em":
      case "i":
        italic = Math.max(0, italic + (tag.isClosing ? -1 : 1));
        break;
      case "script":
      case "style":
        // Nie renderujemy zawartości - inaczej kod CSS/JS z nietypowego
        // szablonu wylądowałby w dymku jako widoczny tekst.
        mutedDepth = Math.max(0, mutedDepth + (tag.isClosing ? -1 : 1));
        break;
      case "a":
        if (tag.isClosing) {
          linkStack.pop();
        } else {
          // Link bez bezpiecznego adresu nadal wnosi tekst do zdania -
          // wchodzi na stos jako pusty ciąg, żeby `</a>` zdjęło właściwy
          // poziom, a fragment wyrenderował się jako zwykły tekst.
          linkStack.push(safeHref(tag.href) ?? "");
        }
        break;
      default:
        break; // nieznany znacznik: tag znika, tekst zostaje
    }
  }

  pushText(html.slice(cursor));

  const last = segments[segments.length - 1];
  if (last) {
    last.text = last.text.replace(/\s+$/, "");
    if (!last.text) segments.pop();
  }
  return segments;
}

/**
 * HTML -> czysty tekst, do miejsc pokazujących jedno-dwuliniowy podgląd
 * (wiersz na liście wątków), gdzie pełne formatowanie nic nie wnosi.
 */
export function htmlToPlainText(html: string): string {
  return parseInlineHtml(html)
    .map((segment) => segment.text)
    .join("")
    .trim();
}

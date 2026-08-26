/**
 * Minimalna sanityzacja HTML przed wyswietleniem go w rendererze.
 *
 * Dwa zastosowania, dwa zestawy dozwolonych znacznikow:
 *
 * 1. `sanitizeOfferHtml` - podglad opisu oferty. Opis pochodzi z modelu
 *    AI, a ten z kolei czyta notatke wpisana przez uzytkownika - czyli
 *    tresc, ktora moglaby probowac wstrzyknac znaczniki. CSP renderera
 *    (`script-src 'self'`) blokuje skrypty inline, ale nie powstrzymuje
 *    np. `<iframe>` ani nie chroni przed rozjechaniem layoutu przez
 *    losowe znaczniki. Podglad ma pokazywac dokladnie to, co Allegro
 *    przyjmie w opisie, wiec przepuszczamy wylacznie te znaczniki, ktore
 *    generuje prompt (patrz `ordlak_service.py`).
 *
 * 2. `sanitizeMessageHtml` - tresc wiadomosci w dyskusji/reklamacji.
 *    Allegro oddaje ja jako HTML (`<br>`, `<strong>`, `<a href>`,
 *    zwlaszcza w komunikatach systemowych typu "Dyskusja trwa juz 14
 *    dni"), wiec renderowanie jej jako zwyklego tekstu pokazywalo
 *    uzytkownikowi surowe znaczniki. Tu dodatkowo przepuszczamy `<a>`,
 *    ale wylacznie z bezpiecznym protokolem i zawsze z `target="_blank"`,
 *    zeby klikniecie oddalo link systemowej przegladarce
 *    (`setWindowOpenHandler` w procesie glownym) zamiast wyprowadzic
 *    renderer z aplikacji.
 *
 * Dlaczego wlasny scrubber, a nie `dompurify`: to te same 3 funkcje na
 * DOM-ie, ktory i tak mamy w Chromium, bez kolejnej zaleznosci w bundlu
 * i bez ryzyka, ze biblioteka zacznie sie prosic o `unsafe-eval` w CSP.
 *
 * Uwaga: to sanityzacja WYSWIETLANIA. Do schowka kopiowany jest surowy
 * tekst z pola edycji - tam uzytkownik widzi dokladnie to, co wklei.
 */
const OFFER_TAGS = new Set(["P", "UL", "OL", "LI", "STRONG", "B", "EM", "I", "BR"]);
const MESSAGE_TAGS = new Set([...OFFER_TAGS, "A"]);

/**
 * Protokoly, ktore wolno zostawic w `href`. Odsiewa `javascript:` i
 * `data:` - jedyne realne wektory ataku przez link w tresci od obcego.
 */
const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

interface ScrubOptions {
  /** Znaczniki, ktore przetrwaja. Reszta traci tag, ale zachowuje tekst. */
  allowed: Set<string>;
  /** Czy zachowac `href` na `<a>` (po weryfikacji protokolu). */
  keepLinks: boolean;
}

export function sanitizeOfferHtml(html: string): string {
  return sanitize(html, { allowed: OFFER_TAGS, keepLinks: false });
}

export function sanitizeMessageHtml(html: string): string {
  return sanitize(html, { allowed: MESSAGE_TAGS, keepLinks: true });
}

/**
 * Czy tresc w ogole zawiera znaczniki HTML.
 *
 * Wiadomosci w dyskusji przychodza mieszane: komunikaty systemowe
 * Allegro sa HTML-em (`<br>`, `<strong>`), a to, co wpisal czlowiek, to
 * zwykly tekst ze znakami nowej linii. Renderowanie tego drugiego przez
 * parser HTML zjadaloby biale znaki i psulo formatowanie, wiec rozdzial
 * jest jawny. Ten sam warunek obowiazuje w aplikacji mobilnej
 * (`mobile/src/components/RichText.tsx`), zeby obie platformy
 * pokazywaly ta sama wiadomosc tak samo.
 */
export function looksLikeHtml(text: string): boolean {
  return /<\/?[a-z][^>]*>/i.test(text);
}

/**
 * Zamienia HTML na czysty tekst z zachowanymi zlamaniami linii.
 *
 * Do miejsc, ktore z zalozenia pokazuja jedna-dwie linijki podgladu
 * (lista watkow, skrot ostatniej wiadomosci) - tam pelne renderowanie
 * HTML nic nie wnosi, a surowe `<br>` w podgladzie wyglada jak blad.
 */
export function htmlToPlainText(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = html;

  for (const dropped of Array.from(template.content.querySelectorAll("script, style"))) {
    dropped.remove();
  }
  for (const lineBreak of Array.from(template.content.querySelectorAll("br"))) {
    lineBreak.replaceWith("\n");
  }
  // Akapit konczy sie pusta linia, blok/element listy zwyklym zlamaniem -
  // tak samo jak `parseInlineHtml` w aplikacji mobilnej, zeby ten sam
  // watek wygladal na obu platformach identycznie.
  for (const block of Array.from(template.content.querySelectorAll("p"))) {
    block.append("\n\n");
  }
  for (const block of Array.from(template.content.querySelectorAll("div, li"))) {
    block.append("\n");
  }

  return (template.content.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
}

function sanitize(html: string, options: ScrubOptions): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  scrub(template.content, options);
  return template.innerHTML;
}

function scrub(node: ParentNode, options: ScrubOptions): void {
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) continue;

    if (child.nodeType !== Node.ELEMENT_NODE) {
      child.remove();
      continue;
    }

    const element = child as Element;
    if (element.tagName === "SCRIPT" || element.tagName === "STYLE") {
      // Wykonac sie i tak nie moga (`<template>` jest inertny, a CSP
      // blokuje skrypty inline), ale zwykle odpiecie znacznika zostawia
      // ich tresc jako TEKST - i uzytkownik widzi w dymku `alert(1)`
      // albo blok CSS. Te dwa znika sie razem z zawartoscia.
      element.remove();
      continue;
    }
    if (!options.allowed.has(element.tagName)) {
      // Znacznik odrzucony, ale jego tekst zostaje - uzytkownik ma
      // zobaczyc calosc opisu, a nie dziure po `<div>`.
      element.replaceWith(...Array.from(element.childNodes));
      continue;
    }

    const href =
      options.keepLinks && element.tagName === "A"
        ? safeHref(element.getAttribute("href"))
        : null;

    for (const attribute of Array.from(element.attributes)) {
      element.removeAttribute(attribute.name);
    }

    if (element.tagName === "A") {
      if (href === null) {
        // Link o niebezpiecznym/pustym adresie traci znacznik, ale tekst
        // zostaje - inaczej z wiadomosci znikalby fragment zdania.
        element.replaceWith(...Array.from(element.childNodes));
        continue;
      }
      element.setAttribute("href", href);
      element.setAttribute("target", "_blank");
      element.setAttribute("rel", "noreferrer noopener");
    }

    scrub(element, options);
  }
}

function safeHref(raw: string | null): string | null {
  if (!raw) return null;
  try {
    // Baza dla adresow wzglednych - tresc wiadomosci pochodzi z Allegro,
    // wiec `/pomoc/...` znaczy tam wlasnie `allegro.pl/pomoc/...`.
    const url = new URL(raw, "https://allegro.pl");
    return SAFE_LINK_PROTOCOLS.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

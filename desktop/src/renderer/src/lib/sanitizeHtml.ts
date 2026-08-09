/**
 * Minimalna sanityzacja HTML opisu oferty przed wyswietleniem podgladu.
 *
 * Opis pochodzi z modelu AI, a ten z kolei czyta notatke wpisana przez
 * uzytkownika - czyli tresc, ktora moglaby probowac wstrzyknac znaczniki.
 * CSP renderera (`script-src 'self'`) blokuje skrypty inline, ale nie
 * powstrzymuje np. `<iframe>` ani nie chroni przed rozjechaniem layoutu
 * przez losowe znaczniki. Podglad ma pokazywac dokladnie to, co Allegro
 * przyjmie w opisie, wiec przepuszczamy wylacznie te znaczniki, ktore
 * generuje prompt (patrz `ordlak_service.py`).
 *
 * Uwaga: to sanityzacja WYSWIETLANIA. Do schowka kopiowany jest surowy
 * tekst z pola edycji - tam uzytkownik widzi dokladnie to, co wklei.
 */
const ALLOWED_TAGS = new Set(["P", "UL", "OL", "LI", "STRONG", "B", "EM", "I", "BR"]);

export function sanitizeOfferHtml(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  scrub(template.content);
  return template.innerHTML;
}

function scrub(node: ParentNode): void {
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) continue;

    if (child.nodeType !== Node.ELEMENT_NODE) {
      child.remove();
      continue;
    }

    const element = child as Element;
    if (!ALLOWED_TAGS.has(element.tagName)) {
      // Znacznik odrzucony, ale jego tekst zostaje - uzytkownik ma
      // zobaczyc calosc opisu, a nie dziure po `<div>`.
      element.replaceWith(...Array.from(element.childNodes));
      continue;
    }

    for (const attribute of Array.from(element.attributes)) {
      element.removeAttribute(attribute.name);
    }
    scrub(element);
  }
}

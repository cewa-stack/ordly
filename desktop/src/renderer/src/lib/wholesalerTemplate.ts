/**
 * Szablony maili do hurtowni - edytowane w Ustawieniach, przypisywane
 * hurtowni w jej edycji. Zyja lokalnie (userData), jak same hurtownie.
 *
 * Kazdy szablon ma dwa warianty. Pusta lista pozycji to NIE blad - mail
 * bez konkretnego zamowienia (pytanie o dostepnosc, cennik, termin) jest
 * rownie potrzebny co zamowienie z lista, wiec wtedy idzie wariant
 * "zapytanie" zamiast "chcialbym zamowic" z pusta lista.
 */
import { useQuery } from "@tanstack/react-query";
import type { WholesalerTemplate } from "../types/api";

export interface WholesalerOrderItem {
  name: string;
  quantity: number;
}

export interface WholesalerRecipient {
  name: string;
  contactPerson?: string;
}

/** Znaczniki pokazywane w edytorze - wstawiane przyciskami, nie z pamieci. */
export const WHOLESALER_TEMPLATE_TOKENS: { token: string; label: string }[] = [
  { token: "{osoba_kontaktowa}", label: "osoba kontaktowa" },
  { token: "{hurtownia}", label: "nazwa hurtowni" },
  { token: "{lista_pozycji}", label: "lista pozycji" },
  { token: "{produkty}", label: "produkty w skrócie" },
  { token: "{data}", label: "dzisiejsza data" },
];

const KNOWN_TOKENS = new Set(WHOLESALER_TEMPLATE_TOKENS.map(({ token }) => token));

const DATE_FORMAT = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function useWholesalerTemplates() {
  return useQuery({
    queryKey: ["wholesaler-templates"],
    queryFn: () => window.ordly.wholesalers.templates(),
  });
}

/** Szablon przypisany hurtowni, a gdy go nie ma (albo usunieto) - domyslny. */
export function resolveWholesalerTemplate(
  templates: WholesalerTemplate[] | undefined,
  templateId: string | undefined
): WholesalerTemplate | null {
  if (!templates || templates.length === 0) return null;
  return (
    templates.find((t) => t.id === templateId) ??
    templates.find((t) => t.isDefault) ??
    templates[0]
  );
}

function fill(text: string, recipient: WholesalerRecipient, items: WholesalerOrderItem[], today: Date) {
  const contact = recipient.contactPerson?.trim() ?? "";
  const itemsList = items
    .map((item) => `- ${item.name} - ilość: ${item.quantity} szt.`)
    .join("\n");
  const products =
    items.length === 0 ? "" : items.length === 1 ? items[0].name : "kilka produktów";

  return (
    text
      // Bez osoby kontaktowej znika tez spacja przed znacznikiem, zeby
      // "Dzień dobry {osoba_kontaktowa}," dalo "Dzień dobry," a nie "Dzień dobry ,".
      .replace(/[ \t]*\{osoba_kontaktowa\}/g, (match) =>
        contact ? match.replace("{osoba_kontaktowa}", contact) : ""
      )
      .replaceAll("{hurtownia}", recipient.name)
      .replaceAll("{lista_pozycji}", itemsList)
      .replaceAll("{produkty}", products)
      .replaceAll("{data}", DATE_FORMAT.format(today))
  );
}

export function renderWholesalerEmail(
  template: WholesalerTemplate,
  recipient: WholesalerRecipient,
  items: WholesalerOrderItem[],
  today: Date = new Date()
): { subject: string; body: string } {
  const isInquiry = items.length === 0;
  return {
    subject: fill(isInquiry ? template.inquirySubject : template.subject, recipient, items, today).trim(),
    body: fill(isInquiry ? template.inquiryBody : template.body, recipient, items, today),
  };
}

/**
 * Ostrzezenia przy zapisie szablonu. Literowka w znaczniku przeszlaby do
 * hurtowni doslownie, a zamowienie bez {lista_pozycji} wyszloby bez listy.
 */
export function findTemplateWarnings(
  template: Pick<WholesalerTemplate, "subject" | "body" | "inquirySubject" | "inquiryBody">
): string[] {
  const warnings: string[] = [];
  const all = [template.subject, template.body, template.inquirySubject, template.inquiryBody].join(
    "\n"
  );
  const unknown = [...new Set(all.match(/\{[^{}\s]*\}/g) ?? [])].filter(
    (token) => !KNOWN_TOKENS.has(token)
  );
  if (unknown.length > 0) {
    warnings.push(
      `Nieznany znacznik ${unknown.join(", ")} trafi do maila dosłownie - wstaw go przyciskiem.`
    );
  }
  if (!template.body.includes("{lista_pozycji}")) {
    warnings.push(
      "Treść zamówienia nie zawiera {lista_pozycji} - zaznaczone pozycje nie trafią do maila."
    );
  }
  return warnings;
}

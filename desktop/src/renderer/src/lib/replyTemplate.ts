/**
 * Podstawianie znacznikow w szablonach odpowiedzi - 1:1 z
 * `mobile/src/utils/replyTemplate.ts`, bo szablony sa wspolne.
 *
 * Serwer oddaje tresc z NIETKNIETYMI znacznikami: tylko aplikacja ma pod
 * reka watek i zamowienie. Gdy danej brakuje (np. zamowienie nie ma
 * jeszcze numeru przesylki), w tekst trafia widoczna luka `‹…›` zamiast
 * pustego miejsca - a `hasTemplateGap` blokuje wysylke, dopoki czlowiek
 * jej nie uzupelni. Kupujacy nigdy nie dostanie "Numer przesylki: ."
 */
import { useQuery } from "@tanstack/react-query";

/** Szablony z Pi - wspolny klucz dla pola odpowiedzi i edytora w Ustawieniach. */
export function useReplyTemplates() {
  return useQuery({
    queryKey: ["reply-templates"],
    queryFn: async () => {
      const result = await window.ordly.templates.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export interface TemplateContext {
  login: string;
  orderId: string;
  trackingNumber: string | null;
}

/** Znaczniki, ktore rozumieja obie aplikacje - pokazywane w edytorze. */
export const TEMPLATE_TOKENS: { token: string; label: string }[] = [
  { token: "{login}", label: "login kupującego" },
  { token: "{numer_zamowienia}", label: "numer zamówienia" },
  { token: "{numer_przesylki}", label: "numer przesyłki" },
];

const GAP = /‹[^›]*›/;

export function fillTemplate(body: string, ctx: TemplateContext): string {
  return body
    .replaceAll("{login}", ctx.login)
    .replaceAll("{numer_zamowienia}", ctx.orderId)
    .replaceAll("{numer_przesylki}", ctx.trackingNumber?.trim() || "‹uzupełnij numer przesyłki›");
}

/** Czy w tekscie zostala luka po brakujacej danej. */
export function hasTemplateGap(text: string): boolean {
  return GAP.test(text);
}

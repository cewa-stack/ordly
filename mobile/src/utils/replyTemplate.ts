/**
 * Podstawianie znaczników w szablonach odpowiedzi - 1:1 z
 * `desktop/.../lib/replyTemplate.ts`, bo szablony są wspólne.
 *
 * Gdy danej brakuje (zamówienie nie ma jeszcze numeru przesyłki), w tekst
 * trafia widoczna luka `‹…›`, a `hasTemplateGap` blokuje wysyłkę, dopóki
 * człowiek jej nie uzupełni. Kupujący nigdy nie dostanie
 * „Numer przesyłki: .”
 */

export interface TemplateContext {
  login: string;
  orderId: string;
  trackingNumber: string | null;
}

const GAP = /‹[^›]*›/;

export function fillTemplate(body: string, ctx: TemplateContext): string {
  return body
    .split("{login}")
    .join(ctx.login)
    .split("{numer_zamowienia}")
    .join(ctx.orderId)
    .split("{numer_przesylki}")
    .join(ctx.trackingNumber?.trim() || "‹uzupełnij numer przesyłki›");
}

/** Czy w tekście została luka po brakującej danej. */
export function hasTemplateGap(text: string): boolean {
  return GAP.test(text);
}

import type { Wholesaler } from "../types/api";

export interface WholesalerOrderItem {
  sku: string;
  name: string;
  quantity: number;
}

export function buildWholesalerSubject(items: WholesalerOrderItem[]): string {
  if (items.length === 0) return "Zapytanie";
  return items.length === 1 ? `Zamówienie - ${items[0].name}` : "Zamówienie - kilka produktów";
}

/**
 * Treść maila do hurtowni. Pusta lista pozycji to NIE blad - mail bez
 * konkretnego zamowienia (pytanie o dostepnosc, cennik, termin) jest
 * rownie potrzebny co zamowienie z lista, wiec szablon oddaje wtedy
 * krotkie powitanie do dopisania wlasnej tresci, zamiast listy z pustka.
 */
export function buildWholesalerBody(wholesaler: Wholesaler, items: WholesalerOrderItem[]): string {
  const greeting = wholesaler.contactPerson
    ? `Dzień dobry ${wholesaler.contactPerson},`
    : "Dzień dobry,";

  if (items.length === 0) {
    return `${greeting}

`;
  }

  const itemsList = items
    .map((item) => `- ${item.name} (SKU: ${item.sku}) - ilość: ${item.quantity} szt.`)
    .join("\n");

  return `${greeting}

Chciałbym złożyć zamówienie na następujące produkty:

${itemsList}

Proszę o potwierdzenie dostępności i przewidywanego terminu dostawy.

Pozdrawiam`;
}

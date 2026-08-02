import type { Wholesaler } from "../types/api";

export interface WholesalerOrderItem {
  sku: string;
  name: string;
  quantity: number;
}

export function buildWholesalerSubject(items: WholesalerOrderItem[]): string {
  return items.length === 1 ? `Zamówienie - ${items[0].name}` : "Zamówienie - kilka produktów";
}

export function buildWholesalerBody(wholesaler: Wholesaler, items: WholesalerOrderItem[]): string {
  const itemsList = items
    .map((item) => `- ${item.name} (SKU: ${item.sku}) - ilość: ${item.quantity} szt.`)
    .join("\n");
  const greeting = wholesaler.contactPerson ? `Dzień dobry ${wholesaler.contactPerson},` : "Dzień dobry,";

  return `${greeting}

Chciałbym złożyć zamówienie na następujące produkty:

${itemsList}

Proszę o potwierdzenie dostępności i przewidywanego terminu dostawy.

Pozdrawiam`;
}

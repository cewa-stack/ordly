/**
 * Etykiety fulfillment_status 1:1 z mobile/src/utils/format.ts
 * (fulfillmentLabel) - te same surowe wartosci Allegro, nie zgadywane
 * ponownie tutaj.
 */
import type { PillTone } from "../components/ui";

/**
 * Wszystkie statusy realizacji, jakie zwraca Allegro. `READY_FOR_SHIPMENT`
 * bywa pomijany w mapach etykiet - wtedy uzytkownik oglada surowe
 * `READY_FOR_SHIPMENT` w interfejsie, co lamie regule 7.1 ("nazywaj
 * rzeczy tak, jak widzi je uzytkownik").
 */
const FULFILLMENT_LABELS: Record<string, string> = {
  NEW: "Nowe",
  PROCESSING: "Do spakowania",
  READY_FOR_SHIPMENT: "Gotowe do wysyłki",
  SENT: "Wysłane",
  PICKED_UP: "Odebrane",
  SUSPENDED: "Wstrzymane",
  CANCELLED: "Anulowane",
};

/**
 * Kolory pigulek wg sekcji 2.4. "Do spakowania" jest koralowe, bo
 * wymaga dzialania; "Wysłane"/"Anulowane" sa wygaszone, bo sa
 * zamknieta historia.
 */
const FULFILLMENT_TONES: Record<string, PillTone> = {
  NEW: "new",
  PROCESSING: "pack",
  READY_FOR_SHIPMENT: "pack",
  SENT: "done",
  PICKED_UP: "done",
  SUSPENDED: "warn",
  CANCELLED: "warn",
};

export function fulfillmentLabel(status: string | null): string {
  if (!status) return "Nowe";
  return FULFILLMENT_LABELS[status] ?? status;
}

export function fulfillmentTone(status: string | null): PillTone {
  if (!status) return "new";
  return FULFILLMENT_TONES[status] ?? "warn";
}

/** Brak statusu lub "NEW" - zamówienie jeszcze nieobsłużone, wymaga uwagi. */
export function isNewFulfillment(status: string | null): boolean {
  return !status || status === "NEW";
}

/** Zamowienie czeka na spakowanie/wyslanie - liczy sie do "do zrobienia". */
export function isPendingFulfillment(status: string | null): boolean {
  return !status || status === "NEW" || status === "PROCESSING";
}

export type OrderFilter = "all" | "pack" | "new" | "sent";

export function matchesOrderFilter(status: string | null, filter: OrderFilter): boolean {
  switch (filter) {
    case "pack":
      return status === "PROCESSING" || status === "READY_FOR_SHIPMENT";
    case "new":
      return isNewFulfillment(status);
    case "sent":
      return status === "SENT" || status === "PICKED_UP";
    default:
      return true;
  }
}

export const ORDER_FILTER_LABEL: Record<OrderFilter, string> = {
  all: "Wszystkie",
  pack: "Do spakowania",
  new: "Nowe",
  sent: "Wysłane",
};

/**
 * Etykiety fulfillment_status 1:1 z mobile/src/utils/format.ts
 * (fulfillmentLabel) - te same surowe wartosci Allegro, nie zgadywane
 * ponownie tutaj.
 */
const FULFILLMENT_LABELS: Record<string, string> = {
  NEW: "Nowe",
  PROCESSING: "Pakowanie",
  SENT: "Wysłane",
  PICKED_UP: "Wysłane",
  CANCELLED: "Anulowane",
};

export function fulfillmentLabel(status: string | null): string {
  if (!status) return "Nowe";
  return FULFILLMENT_LABELS[status] ?? status;
}

/** Brak statusu lub "NEW" - zamówienie jeszcze nieobsłużone, wymaga uwagi. */
export function isNewFulfillment(status: string | null): boolean {
  return !status || status === "NEW";
}

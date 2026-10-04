/**
 * Zwroty - ktore wymagaja dzialania i jak je nazywac.
 *
 * Zrodlem prawdy jest backend (app/domain/returns.py): `GET /returns`
 * zwraca gotowe `requires_action` i `status_label` - te same, z ktorych
 * licza bot, plakietka push i poranny raport. Ponizsze mapy to tylko zapas
 * dla starszego Pi bez tych pol; statusy 1:1 ze swaggerem Allegro
 * (schemat CustomerReturn).
 */
import type { PillTone } from "../components/ui";
import type { CaseHandling, ReturnItem } from "../types/api";

/** Zamkniete: pieniadze zwrocone, prowizja zwrocona/do zwrotu, odrzucony, anulowany. */
const CLOSED_RETURN_STATUSES = new Set([
  "FINISHED",
  "FINISHED_APT",
  "REJECTED",
  "COMMISSION_REFUND_CLAIMED",
  "COMMISSION_REFUNDED",
  "CANCELLED",
]);

const RETURN_STATUS_LABELS: Record<string, string> = {
  CREATED: "Zgłoszony",
  DISPATCHED: "Nadany przez kupującego",
  IN_TRANSIT: "W drodze",
  DELIVERED: "Dostarczony - zwróć pieniądze",
  FINISHED: "Pieniądze zwrócone",
  FINISHED_APT: "Zwrócone przez Allegro Protect",
  REJECTED: "Odrzucony",
  COMMISSION_REFUND_CLAIMED: "Prowizja do zwrotu",
  COMMISSION_REFUNDED: "Prowizja zwrócona",
  WAREHOUSE_DELIVERED: "W magazynie Allegro",
  WAREHOUSE_VERIFICATION: "Weryfikacja w magazynie",
  CANCELLED: "Anulowany",
};

const IN_PROGRESS_RETURN_STATUSES = new Set([
  "DISPATCHED",
  "IN_TRANSIT",
  "DELIVERED",
  "WAREHOUSE_DELIVERED",
  "WAREHOUSE_VERIFICATION",
]);

/**
 * Podzakladka zwrotu: Zgloszony / W trakcie realizacji / Zakonczony.
 * Zrodlem prawdy jest `handling_status` z API (app/domain/returns.py);
 * nizej zapas dla starszego Pi - ta sama regula.
 */
export function returnHandlingOf(
  item: Pick<ReturnItem, "status" | "requires_action" | "handling_status">
): CaseHandling {
  if (item.handling_status) return item.handling_status;
  if (!isOpenReturn(item)) return "DONE";
  return IN_PROGRESS_RETURN_STATUSES.has(item.status) ? "IN_PROGRESS" : "REPORTED";
}

/** Zwrot czeka na ruch sprzedawcy - liczy sie do licznika "Zwroty". */
export function isOpenReturn(item: Pick<ReturnItem, "status" | "requires_action">): boolean {
  if (typeof item.requires_action === "boolean") return item.requires_action;
  return !CLOSED_RETURN_STATUSES.has(item.status);
}

export function returnStatusLabel(item: Pick<ReturnItem, "status" | "status_label">): string {
  return item.status_label ?? RETURN_STATUS_LABELS[item.status] ?? item.status;
}

/**
 * Ton pigulki wg sekcji 7: zamkniety nie ma po co swiecic, dostarczony
 * (trzeba zwrocic pieniadze) i zgloszony sa `hot`, w drodze - `go`.
 */
export function returnStatusTone(item: Pick<ReturnItem, "status" | "requires_action">): PillTone {
  if (!isOpenReturn(item)) return "mute";
  if (item.status === "DELIVERED" || item.status === "CREATED") return "hot";
  return "go";
}

/**
 * Status aplikacyjny zamówienia: Nowe / W realizacji / Zrealizowane /
 * Anulowane - 1:1 z desktopem (desktop/.../lib/appStatus.ts).
 *
 * Telefon tylko go POKAZUJE - zmiana statusu jest na desktopie. Źródłem
 * prawdy jest backend (`app_status`, `app_status_label`,
 * `app_status_manual` z GET /orders, reguła w app/domain/order_status.py).
 * Niżej zapas dla starszego Pi bez tych pól.
 */
import type { AppStatus, Order } from "@/api/types";

export const APP_STATUS_LABEL: Record<AppStatus, string> = {
  NEW: "Nowe",
  IN_PROGRESS: "W realizacji",
  DONE: "Zrealizowane",
  CANCELLED: "Anulowane",
};

type StatusFields = Pick<
  Order,
  "status" | "fulfillment_status" | "tracking_number" | "app_status"
>;

function fromAllegro(order: StatusFields): AppStatus | null {
  const stage = order.fulfillment_status;
  if (order.status === "CANCELLED" || stage === "CANCELLED") return "CANCELLED";
  if (
    order.tracking_number ||
    stage === "SENT" ||
    stage === "PICKED_UP" ||
    stage === "READY_FOR_PICKUP" ||
    stage === "RETURNED"
  ) {
    return "DONE";
  }
  if (stage === "NEW") return "NEW";
  if (stage === "PROCESSING" || stage === "READY_FOR_SHIPMENT" || stage === "SUSPENDED") {
    return "IN_PROGRESS";
  }
  return null;
}

export function appStatusOf(order: StatusFields): AppStatus | null {
  return order.app_status !== undefined ? order.app_status : fromAllegro(order);
}

export function appStatusLabel(order: StatusFields): string {
  const status = appStatusOf(order);
  return status ? APP_STATUS_LABEL[status] : "Brak danych";
}

/** Status zmieniono ręcznie w aplikacji (na desktopie) i nadal obowiązuje. */
export function isManualStatus(order: Pick<Order, "app_status_manual">): boolean {
  return order.app_status_manual === true;
}

/**
 * Status aplikacyjny zamowienia: Nowe / W realizacji / Zrealizowane /
 * Anulowane (pozycja z Notion "Brak recznej zmiany statusu zamowienia
 * wylacznie w aplikacji").
 *
 * Zrodlem prawdy jest backend (app/domain/order_status.py): `GET /orders`
 * zwraca gotowe `app_status`, `app_status_label` i `app_status_manual` -
 * te same, z ktorych licza bot, plakietka push i przypomnienia. Ponizsza
 * regula to tylko zapas dla starszego Pi bez tych pol (wtedy bez recznych
 * zmian - status liczony z etapu Allegro, jak w backendzie).
 */
import type { PillTone } from "../components/ui";
import type { AppStatus, Order } from "../types/api";

export const APP_STATUSES: AppStatus[] = ["NEW", "IN_PROGRESS", "DONE", "CANCELLED"];

export const APP_STATUS_LABEL: Record<AppStatus, string> = {
  NEW: "Nowe",
  IN_PROGRESS: "W realizacji",
  DONE: "Zrealizowane",
  CANCELLED: "Anulowane",
};

/** `hot` wymaga dzialania, `go` jest w toku, `mute` jest zamkniete (sekcja 7). */
const APP_STATUS_TONE: Record<AppStatus, PillTone> = {
  NEW: "hot",
  IN_PROGRESS: "go",
  DONE: "mute",
  CANCELLED: "mute",
};

type StatusFields = Pick<
  Order,
  "status" | "fulfillment_status" | "tracking_number" | "app_status"
>;

/** Lustro `allegro_app_status` z backendu - tylko na wypadek starszego Pi. */
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

export function appStatusTone(order: StatusFields): PillTone {
  const status = appStatusOf(order);
  return status ? APP_STATUS_TONE[status] : "mute";
}

/** Czy obowiazuje status ustawiony recznie w aplikacji. */
export function isManualStatus(order: Pick<Order, "app_status_manual">): boolean {
  return order.app_status_manual === true;
}

/**
 * Podzakladki Zamowien (pozycja z Notion "Podzial zamowien na podzakladki
 * wedlug statusu realizacji", decyzja D3-a): Wszystkie / Nowe /
 * W realizacji / Zrealizowane. Zastapily filtry "Do spakowania",
 * "Gotowe do wysylki" i "Wyslane", ktore pokrywaly sie z nowymi.
 * Anulowane sa widoczne w "Wszystkie" (z szara pigulka).
 */
export type OrderTab = "all" | "NEW" | "IN_PROGRESS" | "DONE";

export const ORDER_TABS: OrderTab[] = ["all", "NEW", "IN_PROGRESS", "DONE"];

export const ORDER_TAB_LABEL: Record<OrderTab, string> = {
  all: "Wszystkie",
  NEW: "Nowe",
  IN_PROGRESS: "W realizacji",
  DONE: "Zrealizowane",
};

export function matchesOrderTab(order: StatusFields, tab: OrderTab): boolean {
  return tab === "all" || appStatusOf(order) === tab;
}

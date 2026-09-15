/**
 * Etykiety fulfillment_status 1:1 z mobile/src/utils/format.ts
 * (fulfillmentLabel) - te same surowe wartosci Allegro, nie zgadywane
 * ponownie tutaj.
 *
 * Etapy obslugi zamowienia w ORDLY:
 *
 *   NEW (Nowe) -> PROCESSING (W realizacji) -> READY_FOR_SHIPMENT
 *   (Gotowe do wysyłki = spakowane) -> SENT (Wysłane)
 *
 * "Oznacz jako spakowane" ustawia READY_FOR_SHIPMENT. Wczesniej ustawialo
 * PROCESSING, ktore aplikacja pokazywala jako "Do spakowania" i dalej
 * liczyla jako czekajace - po kliknieciu "spakowane" zamowienie nadal
 * wisialo w "czeka na spakowanie".
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
  PROCESSING: "W realizacji",
  READY_FOR_SHIPMENT: "Gotowe do wysyłki",
  READY_FOR_PICKUP: "Do odbioru",
  SENT: "Wysłane",
  PICKED_UP: "Odebrane",
  SUSPENDED: "Wstrzymane",
  CANCELLED: "Anulowane",
};

/**
 * Kolory pigulek wg sekcji 2.4. Koralowe jest to, co czeka na spakowanie
 * (wymaga dzialania); spakowane czeka juz tylko na kuriera; wyslane
 * i anulowane sa wygaszone, bo sa zamknieta historia.
 */
const FULFILLMENT_TONES: Record<string, PillTone> = {
  NEW: "pack",
  PROCESSING: "pack",
  READY_FOR_SHIPMENT: "new",
  READY_FOR_PICKUP: "done",
  SENT: "done",
  PICKED_UP: "done",
  SUSPENDED: "warn",
  CANCELLED: "warn",
};

/** Minimum pol zamowienia potrzebne do decyzji o etapie obslugi. */
interface OrderStatusFields {
  status: string;
  fulfillment_status: string | null;
  tracking_number: string | null;
}

const RAW_SHIPPED_STATUSES = new Set(["SENT", "PICKED_UP"]);

/**
 * Zamowienie jest wyslane z punktu widzenia interfejsu, gdy Allegro
 * ustawilo juz odpowiedni fulfillment_status ALBO gdy ORDLY samo wykrylo
 * numer przesylki (check_waybills_job) - zanim uzytkownik recznie zmieni
 * status na Allegro. Lustrzane odbicie backendowego
 * OrderRepository.get_unshipped_since.
 */
export function isShippedForDisplay(order: OrderStatusFields): boolean {
  if (isCancelledOrder(order)) return false;
  const status = order.fulfillment_status;
  return (status !== null && RAW_SHIPPED_STATUSES.has(status)) || Boolean(order.tracking_number);
}

export function fulfillmentLabel(status: string | null): string {
  if (!status) return "Nowe";
  return FULFILLMENT_LABELS[status] ?? status;
}

export function fulfillmentTone(status: string | null): PillTone {
  if (!status) return "pack";
  return FULFILLMENT_TONES[status] ?? "warn";
}

/**
 * Etykieta/ton pigulki do wyswietlenia - jak fulfillmentLabel/Tone, ale
 * pokazuje "Wysłane" tez wtedy, gdy tracking_number zostal wykryty lokalnie
 * (check_waybills_job), zanim uzytkownik recznie zmienil status na Allegro.
 */
export function displayFulfillmentLabel(order: OrderStatusFields): string {
  if (isShippedForDisplay(order) && !RAW_SHIPPED_STATUSES.has(order.fulfillment_status ?? "")) {
    return fulfillmentLabel("SENT");
  }
  return fulfillmentLabel(order.fulfillment_status);
}

export function displayFulfillmentTone(order: OrderStatusFields): PillTone {
  if (isShippedForDisplay(order) && !RAW_SHIPPED_STATUSES.has(order.fulfillment_status ?? "")) {
    return fulfillmentTone("SENT");
  }
  return fulfillmentTone(order.fulfillment_status);
}

/** Anulowane zamowienie - Allegro nie pozwala juz zmieniac jego realizacji. */
export function isCancelledOrder(order: OrderStatusFields): boolean {
  return order.status === "CANCELLED" || order.fulfillment_status === "CANCELLED";
}

/**
 * Zamowienie czeka na spakowanie - liczy sie do "do zrobienia".
 *
 * Anulowane odpada nawet wtedy, gdy Allegro zostawilo mu etap NEW -
 * wczesniej takie zamowienie wisialo w liczniku na zawsze. Wykryty
 * numer przesylki tez zdejmuje zamowienie z tej listy, nawet gdy Allegro
 * jeszcze nie zmienilo statusu - patrz isShippedForDisplay.
 */
export function isPendingOrder(order: OrderStatusFields): boolean {
  if (isShippedForDisplay(order)) return false;
  const status = order.fulfillment_status;
  return !isCancelledOrder(order) && (!status || status === "NEW" || status === "PROCESSING");
}

export type OrderFilter = "all" | "pack" | "ready" | "sent";

export function matchesOrderFilter(order: OrderStatusFields, filter: OrderFilter): boolean {
  const status = order.fulfillment_status;
  switch (filter) {
    case "pack":
      return isPendingOrder(order);
    case "ready":
      return !isCancelledOrder(order) && status === "READY_FOR_SHIPMENT" && !order.tracking_number;
    case "sent":
      return isShippedForDisplay(order) || status === "READY_FOR_PICKUP";
    default:
      return true;
  }
}

export const ORDER_FILTER_LABEL: Record<OrderFilter, string> = {
  all: "Wszystkie",
  pack: "Do spakowania",
  ready: "Gotowe do wysyłki",
  sent: "Wysłane",
};

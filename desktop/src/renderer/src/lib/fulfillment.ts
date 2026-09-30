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
  RETURNED: "Zwrócone",
};

/**
 * Tony pigulek w jezyku z sekcji 7 instrukcji "Nokturn": `hot` wymaga
 * dzialania, `go` jest w toku, `mute` jest zamkniete.
 *
 * "Wyslane", "Odebrane" i "Anulowane" sa `mute`, nie `go` - to zamknieta
 * historia. Swiecenie rzeczy juz skonczonych to glowny powod, przez
 * ktory interfejsy robia sie hałaśliwe. "Wstrzymane" zostaje `hot`, bo
 * jako jedyne z zamknietych naprawde czeka na decyzje sprzedawcy.
 */
const FULFILLMENT_TONES: Record<string, PillTone> = {
  NEW: "hot",
  PROCESSING: "hot",
  READY_FOR_SHIPMENT: "go",
  READY_FOR_PICKUP: "mute",
  SENT: "mute",
  PICKED_UP: "mute",
  SUSPENDED: "hot",
  CANCELLED: "mute",
  RETURNED: "mute",
};

/** Minimum pol zamowienia potrzebne do decyzji o etapie obslugi. */
interface OrderStatusFields {
  status: string;
  fulfillment_status: string | null;
  tracking_number: string | null;
  /** Gotowy wynik reguly backendu (`requires_packing` z GET /orders). */
  requires_packing?: boolean;
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

/**
 * Etap nieznany (NULL) to rekord, ktorego Allegro jeszcze nie potwierdzilo -
 * nie "Nowe". Pokazywanie go jako "Nowe" przy jednoczesnym niewliczaniu do
 * "Do spakowania" lamaloby zasade "zamowienie nie moze byc jednoczesnie
 * obsluzone i widoczne jako nowe".
 */
export function fulfillmentLabel(status: string | null): string {
  if (!status) return "Brak danych";
  return FULFILLMENT_LABELS[status] ?? status;
}

export function fulfillmentTone(status: string | null): PillTone {
  if (!status) return "mute";
  return FULFILLMENT_TONES[status] ?? "mute";
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
 * Zrodlem prawdy jest backend: pole `requires_packing` z GET /orders to
 * wynik tej samej reguly, z ktorej licza bot, plakietka push i poranny
 * raport (app/domain/fulfillment.py). Lokalna regula to tylko zapas na
 * starsze Pi bez tego pola - i jest jej wierna kopia: anulowane odpada,
 * wykryty numer przesylki odpada, etap nieznany (NULL) NIE czeka.
 */
export function isPendingOrder(order: OrderStatusFields): boolean {
  if (typeof order.requires_packing === "boolean") return order.requires_packing;
  if (isShippedForDisplay(order) || isCancelledOrder(order)) return false;
  const status = order.fulfillment_status;
  return status === "NEW" || status === "PROCESSING";
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

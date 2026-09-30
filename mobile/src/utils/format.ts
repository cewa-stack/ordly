/** Formatowanie liczb, kwot i dat spójne we wszystkich ekranach. */

/**
 * Kwota wg sekcji 7.2 specyfikacji: `249,90 zł`.
 *
 * Waluta jest pokazywana SYMBOLEM, nie kodem ISO - "28,92 PLN" to
 * język bankowy, a apkę czyta się w magazynie. Kody inne niż PLN
 * zostają jako kod, bo nie mamy dla nich uzgodnionego symbolu.
 */
export function formatMoney(
  value: number | string,
  currency = "PLN",
  { round = false } = {}
): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  const formatted = numeric.toLocaleString("pl-PL", {
    minimumFractionDigits: round ? 0 : 2,
    maximumFractionDigits: round ? 0 : 2,
  });
  const suffix = currency.toUpperCase() === "PLN" ? "zł" : currency;
  return `${formatted} ${suffix}`;
}

/**
 * Znacznik czasu z API jako `Date`.
 *
 * Starszy backend na Pi oddaje daty BEZ strefy ("2026-09-13T17:13:00"),
 * choć to czas UTC. `new Date()` czyta taki napis jako czas LOKALNY, więc
 * każda godzina w aplikacji była cofnięta o różnicę do UTC (latem 2 h).
 * Napis bez strefy traktujemy jako UTC; z `Z` albo offsetem - bez zmian.
 * Ułamek sekundy skracamy do milisekund - Safari nie gwarantuje dłuższych.
 */
export function parseApiDate(iso: string): Date {
  const trimmed = iso.replace(/(\.\d{3})\d+/, "$1");
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  return new Date(trimmed.includes("T") && !hasZone ? `${trimmed}Z` : trimmed);
}

/** Po tylu godzinach czekające zamówienie robi się koralowe. */
export const OVERDUE_AFTER_HOURS = 24;

/**
 * Ile zamówienie czeka na spakowanie: „czeka 40 min”, „czeka 3 h”,
 * „czeka 3 dni”. Godziny aż do dwóch dób - „czeka 1 dzień” brzmi
 * łagodniej, niż jest, a 30 h mówi wprost, że termin już minął.
 */
export function waitingLabel(iso: string, now = Date.now()): { text: string; overdue: boolean } {
  const minutes = Math.max(0, Math.floor((now - parseApiDate(iso).getTime()) / 60_000));
  const hours = Math.floor(minutes / 60);
  const text =
    minutes < 60
      ? `czeka ${minutes} min`
      : hours < 48
        ? `czeka ${hours} h`
        : `czeka ${Math.floor(hours / 24)} dni`;
  return { text, overdue: hours >= OVERDUE_AFTER_HOURS };
}

/**
 * Ostatnia synchronizacja z Pi - `last_sync_human` z `/dashboard` to
 * polski czas „RRRR-MM-DD GG:MM” (albo „jeszcze nie wykonano” tuż po
 * restarcie usługi). Pi synchronizuje co minutę, więc kwadrans ciszy
 * znaczy, że synchronizacja stanęła - wtedy `stale`.
 */
export function lastSyncLabel(
  human: string | undefined,
  now = Date.now()
): { text: string; stale: boolean } | null {
  if (!human) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(human.trim());
  if (!match) return { text: "Allegro jeszcze nie sprawdzone od startu Pi", stale: false };
  const [, y, mo, d, h, mi] = match.map(Number);
  const minutes = Math.floor((now - new Date(y, mo - 1, d, h, mi).getTime()) / 60_000);
  if (minutes < 1) return { text: "Allegro sprawdzone przed chwilą", stale: false };
  if (minutes < 60) return { text: `Allegro sprawdzone ${minutes} min temu`, stale: minutes >= 15 };
  return { text: `Allegro sprawdzone o ${match[4]}:${match[5]}`, stale: true };
}

export function formatDate(isoDate: string): string {
  const date = parseApiDate(isoDate);
  return date.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Polska odmiana liczebników: plural(2, "zamówienie", "zamówienia",
 * "zamówień") → "zamówienia". Reguła: 1 → one; końcówka 2-4 poza 12-14 →
 * few; reszta → many.
 */
export function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) {
    return one;
  }
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return few;
  }
  return many;
}

/**
 * Etykiety statusów realizacji - te same, co w apce desktopowej.
 *
 * `READY_FOR_SHIPMENT` bywa pomijany w takich mapach i wtedy użytkownik
 * ogląda w interfejsie surowe `READY_FOR_SHIPMENT`, co łamie regułę 7.1
 * ("nazywaj rzeczy tak, jak widzi je użytkownik").
 */
const FULFILLMENT_LABELS: Record<string, string> = {
  NEW: "Nowe",
  // PROCESSING to "w realizacji" - spakowane zamówienie desktop oznacza
  // jako READY_FOR_SHIPMENT. Dawna etykieta "Do spakowania" myliła oba etapy.
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
 * Etap nieznany (NULL) to rekord, którego Allegro jeszcze nie potwierdziło -
 * nie „Nowe”. Inaczej telefon pokazywałby jako nowe zamówienie, które nie
 * liczy się do „Do spakowania” (1:1 z desktopem).
 */
export function fulfillmentLabel(status: string | null): string {
  if (!status) {
    return "Brak danych";
  }
  return FULFILLMENT_LABELS[status] ?? status;
}

/** Minimum pól zamówienia potrzebne do decyzji o etapie obsługi. */
interface OrderStatusFields {
  status: string;
  fulfillment_status: string | null;
  tracking_number: string | null;
  /** Gotowy wynik reguły backendu (`requires_packing` z GET /orders). */
  requires_packing?: boolean;
}

/**
 * Zamówienie jest wysłane z punktu widzenia interfejsu, gdy Allegro
 * ustawiło już odpowiedni fulfillment_status ALBO gdy ORDLY samo wykryło
 * numer przesyłki (check_waybills_job), zanim użytkownik ręcznie zmieni
 * status na Allegro - 1:1 z desktop/.../lib/fulfillment.ts.
 */
export function isShippedForDisplay(order: OrderStatusFields): boolean {
  if (order.status === "CANCELLED" || order.fulfillment_status === "CANCELLED") {
    return false;
  }
  const status = order.fulfillment_status;
  return status === "SENT" || status === "PICKED_UP" || Boolean(order.tracking_number);
}

/** Etykieta jak fulfillmentLabel, ale pokazuje "Wysłane" po wykryciu numeru przesyłki. */
export function displayFulfillmentLabel(order: OrderStatusFields): string {
  if (isShippedForDisplay(order) && order.fulfillment_status !== "PICKED_UP") {
    return fulfillmentLabel("SENT");
  }
  return fulfillmentLabel(order.fulfillment_status);
}

/**
 * Zamówienie czeka na SPAKOWANIE - liczy się do kafla „Do spakowania”,
 * odznaki na zakładce i plakietki aplikacji. Reguła 1:1 z desktopowym
 * `isPendingOrder` (desktop/.../lib/fulfillment.ts) i z backendem
 * (`AttentionService`), który z niej liczy plakietkę przy każdym push -
 * trzy miejsca muszą dawać tę samą liczbę.
 *
 * Dwie poprawki wobec poprzedniej wersji:
 * - `READY_FOR_SHIPMENT` (spakowane, czeka na kuriera) już się NIE liczy.
 *   Telefon pokazywał spakowaną paczkę jako „do spakowania”, podczas gdy
 *   desktop - po kliknięciu „Oznacz jako spakowane” - już nie;
 * - anulowane odpada, nawet gdy Allegro zostawiło mu etap `NEW`.
 *   Wcześniej takie zamówienie wisiało w liczniku na zawsze.
 */
export function isPendingFulfillment(order: OrderStatusFields): boolean {
  // Źródło prawdy: backend (`requires_packing` z GET /orders) - ta sama
  // reguła co bot, plakietka i poranny raport. Niżej zapas dla starszego
  // Pi bez tego pola: etap nieznany (NULL) NIE czeka na spakowanie.
  if (typeof order.requires_packing === "boolean") return order.requires_packing;
  if (order.status === "CANCELLED" || order.fulfillment_status === "CANCELLED") {
    return false;
  }
  if (isShippedForDisplay(order)) return false;
  const status = order.fulfillment_status;
  return status === "NEW" || status === "PROCESSING";
}

/**
 * Etykiety i tonacje statusów dyskusji/reklamacji - 1:1 ze schematem
 * PostPurchaseIssueStatus w oficjalnym swagger.yaml Allegro (zweryfikowane,
 * te same wartości co w apce desktopowej - jedno źródło prawdy o kształcie
 * statusów, nawet jeśli klienty są dwa).
 */
const ISSUE_STATUS_LABELS: Record<string, string> = {
  DISPUTE_ONGOING: "W toku",
  DISPUTE_CLOSED: "Zamknięta",
  DISPUTE_UNRESOLVED: "Nierozwiązana",
  CLAIM_SUBMITTED: "Zgłoszona",
  CLAIM_ACCEPTED: "Zaakceptowana",
  CLAIM_REJECTED: "Odrzucona",
};

export function issueStatusLabel(status: string): string {
  return ISSUE_STATUS_LABELS[status] ?? status;
}

export type IssueStatusTone = "ok" | "warn" | "crit";

const ISSUE_STATUS_TONES: Record<string, IssueStatusTone> = {
  DISPUTE_ONGOING: "warn",
  DISPUTE_CLOSED: "ok",
  DISPUTE_UNRESOLVED: "crit",
  CLAIM_SUBMITTED: "warn",
  CLAIM_ACCEPTED: "ok",
  CLAIM_REJECTED: "crit",
};

export function issueStatusTone(status: string): IssueStatusTone {
  return ISSUE_STATUS_TONES[status] ?? "warn";
}


/**
 * Etykiety statusów zwrotów Allegro - te same, co w aplikacji
 * desktopowej.
 *
 * Bez tego użytkownik oglądał na karcie surowe
 * `COMMISSION_REFUND_CLAIMED`, co łamie regułę 7.1 ("nazywaj rzeczy tak,
 * jak widzi je użytkownik"). Nieznany status zostaje surowy - lepiej
 * pokazać kod niż zgadywać znaczenie.
 */
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

export function returnStatusLabel(status: string, backendLabel?: string): string {
  return backendLabel ?? RETURN_STATUS_LABELS[status] ?? status;
}

/**
 * Zwroty zamknięte (pieniądze zwrócone, prowizja zwrócona/do zwrotu,
 * odrzucony, anulowany) - zapas dla starszego Pi bez `requires_action`.
 * Źródło prawdy: backend, app/domain/returns.py (1:1 z desktopem).
 */
const CLOSED_RETURN_STATUSES = new Set([
  "FINISHED",
  "FINISHED_APT",
  "REJECTED",
  "COMMISSION_REFUND_CLAIMED",
  "COMMISSION_REFUNDED",
  "CANCELLED",
]);

/** Zwrot czeka na ruch sprzedawcy - liczy się do kafla i plakietki „Zwroty”. */
export function isOpenReturn(item: { status: string; requires_action?: boolean }): boolean {
  if (typeof item.requires_action === "boolean") return item.requires_action;
  return !CLOSED_RETURN_STATUSES.has(item.status);
}

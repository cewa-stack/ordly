/** Formatowanie liczb, kwot i dat spójne we wszystkich ekranach. */

/**
 * Kwota wg sekcji 7.2 specyfikacji: `249,90 zł`.
 *
 * Waluta jest pokazywana SYMBOLEM, nie kodem ISO - "28,92 PLN" to
 * język bankowy, a apkę czyta się w magazynie. Kody inne niż PLN
 * zostają jako kod, bo nie mamy dla nich uzgodnionego symbolu.
 */
export function formatMoney(value: number | string, currency = "PLN"): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  const formatted = numeric.toLocaleString("pl-PL", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const suffix = currency.toUpperCase() === "PLN" ? "zł" : currency;
  return `${formatted} ${suffix}`;
}

export function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
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
  PROCESSING: "Do spakowania",
  READY_FOR_SHIPMENT: "Gotowe do wysyłki",
  SENT: "Wysłane",
  PICKED_UP: "Odebrane",
  SUSPENDED: "Wstrzymane",
  CANCELLED: "Anulowane",
};

export function fulfillmentLabel(status: string | null): string {
  if (!status) {
    return "Nowe";
  }
  return FULFILLMENT_LABELS[status] ?? status;
}

/**
 * Zamówienie czeka na obsłużenie - liczy się do odznaki na zakładce
 * i do plakietki aplikacji.
 *
 * Plakietka liczy WYŁĄCZNIE sprawy wymagające decyzji na desktopie
 * (sekcja 04 koncepcji push), więc wysłane i anulowane odpadają.
 */
export function isPendingFulfillment(status: string | null): boolean {
  return (
    !status ||
    status === "NEW" ||
    status === "PROCESSING" ||
    status === "READY_FOR_SHIPMENT"
  );
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
  COMMISSION_REFUND_CLAIMED: "Prowizja do zwrotu",
  COMMISSION_REFUNDED: "Prowizja zwrócona",
  CANCELLED: "Anulowany",
  REJECTED: "Odrzucony",
};

export function returnStatusLabel(status: string): string {
  return RETURN_STATUS_LABELS[status] ?? status;
}

/** Formatowanie liczb, kwot i dat spójne we wszystkich ekranach. */

export function formatMoney(value: number | string, currency = "PLN"): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  const formatted = numeric.toLocaleString("pl-PL", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${formatted} ${currency}`;
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

const FULFILLMENT_LABELS: Record<string, string> = {
  NEW: "Nowe",
  PROCESSING: "Pakowanie",
  SENT: "Wysłane",
  PICKED_UP: "Wysłane",
  CANCELLED: "Anulowane",
};

export function fulfillmentLabel(status: string | null): string {
  if (!status) {
    return "Nowe";
  }
  return FULFILLMENT_LABELS[status] ?? status;
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

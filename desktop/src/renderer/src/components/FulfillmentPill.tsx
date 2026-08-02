import { fulfillmentLabel } from "../lib/fulfillment";

/** Kolory 1:1 z mobile/src/theme/colors.ts (orderStatusColor): Nowe=primary, Pakowanie=warning, Wysłane=success, Anulowane=danger. */
const TONE_CLASS: Record<string, string> = {
  Nowe: "bg-primary-tint text-primary",
  Pakowanie: "bg-warning-tint text-warning",
  Wysłane: "bg-success-tint text-success",
  Anulowane: "bg-danger-tint text-danger",
};

export function FulfillmentPill({ status }: { status: string | null }) {
  const label = fulfillmentLabel(status);
  const toneClass = TONE_CLASS[label] ?? "bg-surface-raised text-text-secondary";
  return <span className={`rounded-full px-2.5 py-1 text-badge-label ${toneClass}`}>{label}</span>;
}

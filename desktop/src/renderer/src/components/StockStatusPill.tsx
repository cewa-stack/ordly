import type { StockStatus } from "../types/api";

const containerClass: Record<StockStatus, string> = {
  ok: "bg-success-tint text-success",
  warning: "bg-warning-tint text-warning",
  critical: "bg-danger-tint text-danger",
};

const dotClass: Record<StockStatus, string> = {
  ok: "bg-success",
  warning: "bg-warning",
  critical: "bg-danger",
};

const label: Record<StockStatus, string> = {
  ok: "OK",
  warning: "Niski stan",
  critical: "Brak",
};

export function StockStatusPill({ status }: { status: StockStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-badge-label ${containerClass[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass[status]}`} />
      {label[status]}
    </span>
  );
}

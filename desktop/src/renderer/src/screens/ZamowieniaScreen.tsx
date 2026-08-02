import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import { FulfillmentPill } from "../components/FulfillmentPill";
import { MarketplaceBadge } from "../components/MarketplaceBadge";
import { isNewFulfillment } from "../lib/fulfillment";
import { useToast } from "../lib/toast";
import type { SyncResult } from "../types/api";

const dateFormatter = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function useOrdersList() {
  return useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const result = await window.ordly.orders.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function formatAmount(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("pl-PL", { style: "currency", currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

function syncToastMessage(result: SyncResult): string {
  if (result.new_orders_count > 0) {
    return `${result.new_orders_count} ${
      result.new_orders_count === 1 ? "nowe zamówienie" : "nowych zamówień"
    } zsynchronizowane z Allegro`;
  }
  if (result.new_returns_count > 0) {
    return `${result.new_returns_count} ${
      result.new_returns_count === 1 ? "nowy zwrot" : "nowych zwrotów"
    } wykrytych podczas synchronizacji`;
  }
  if (result.cancelled_orders_count > 0) {
    return `Wykryto ${result.cancelled_orders_count} anulowanych zamówień`;
  }
  return "Zsynchronizowano — brak nowości";
}

export function ZamowieniaScreen() {
  const { data, isLoading, isError, error } = useOrdersList();
  const queryClient = useQueryClient();
  const toast = useToast();

  const syncMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.orders.sync();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (result) => {
      toast.success(syncToastMessage(result));
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Synchronizacja nie powiodła się");
    },
  });

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-title1">Zamówienia</h1>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 text-[12.5px] font-semibold text-text-secondary hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshIcon size={14} className={syncMutation.isPending ? "animate-spin" : ""} />
          {syncMutation.isPending ? "Synchronizuję…" : "Synchronizuj teraz"}
        </button>
      </div>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie zamówień…</p>}
      {isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać zamówień: {error instanceof Error ? error.message : "nieznany błąd"}
        </p>
      )}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          pose="orders"
          title="Czekamy na pierwsze zamówienie"
          description="Nowe zamówienia z Allegro pojawią się tutaj automatycznie."
        />
      )}

      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {[
                  "Marketplace",
                  "Nr zamówienia",
                  "Klient",
                  "Produkty",
                  "Kwota",
                  "Data",
                  "Status",
                  "Realizacja",
                ].map(
                  (h) => (
                    <th
                      key={h}
                      className="border-b border-border px-4 py-2.5 text-left font-mono text-[10.5px] uppercase tracking-wide text-text-dim"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {data.map((order, rowIndex) => {
                const isLastRow = rowIndex === data.length - 1;
                const cellBorder = isLastRow ? "" : "border-b border-border";
                const isNew = isNewFulfillment(order.fulfillment_status);
                return (
                  <tr key={order.external_id} className="hover:bg-surface-raised">
                    <td
                      className={`px-4 py-3 ${cellBorder}`}
                      style={isNew ? { boxShadow: "inset 3px 0 0 var(--ordly-primary)" } : undefined}
                    >
                      <MarketplaceBadge marketplace={order.marketplace} />
                    </td>
                    <td className={`px-4 py-3 font-mono text-[12px] text-text-secondary ${cellBorder}`}>
                      #{order.external_id}
                    </td>
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>{order.buyer_login}</td>
                    <td className={`px-4 py-3 text-[12.5px] text-text-secondary ${cellBorder}`}>
                      {order.products.length} {order.products.length === 1 ? "produkt" : "produkty"}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] font-semibold tabular-nums ${cellBorder}`}>
                      {formatAmount(order.total_amount, order.currency)}
                    </td>
                    <td className={`px-4 py-3 text-[12px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {dateFormatter.format(new Date(order.order_date))}
                    </td>
                    <td className={`px-4 py-3 ${cellBorder}`}>
                      <span className="rounded-full bg-surface-raised px-2.5 py-1 font-mono text-[10.5px] text-text-secondary">
                        {order.status}
                      </span>
                    </td>
                    <td className={`px-4 py-3 ${cellBorder}`}>
                      <FulfillmentPill status={order.fulfillment_status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";

const dateFormatter = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function useReturnsList() {
  return useQuery({
    queryKey: ["returns"],
    queryFn: async () => {
      const result = await window.ordly.returns.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

export function ReturnsScreen() {
  const { data, isLoading, isError, error, isFetching } = useReturnsList();
  const queryClient = useQueryClient();

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-title1">Zwroty i anulowane</h1>
        <button
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["returns"] })}
          disabled={isFetching}
          className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 text-[12.5px] font-semibold text-text-secondary hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshIcon size={14} className={isFetching ? "animate-spin" : ""} />
          Odśwież
        </button>
      </div>

      <p className="mb-4 text-footnote text-text-secondary">
        Zwroty synchronizują się razem z zamówieniami — użyj „Synchronizuj teraz" na
        ekranie Zamówień, żeby sprawdzić nowe.
      </p>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie zwrotów…</p>}
      {isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać zwrotów: {error instanceof Error ? error.message : "nieznany błąd"}
        </p>
      )}
      {!isLoading && !isError && data && data.length === 0 && (
        <EmptyState
          pose="happy"
          title="Zero zwrotów i anulowań"
          description="Wszystkie zamówienia idą gładko - nic tu dziś nie ma."
        />
      )}

      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Nr zwrotu", "Zamówienie", "Klient", "Produkty", "Data", "Status"].map((h) => (
                  <th
                    key={h}
                    className="border-b border-border px-4 py-2.5 text-left font-mono text-[10.5px] uppercase tracking-wide text-text-dim"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((item, rowIndex) => {
                const isLastRow = rowIndex === data.length - 1;
                const cellBorder = isLastRow ? "" : "border-b border-border";
                return (
                  <tr key={item.external_id} className="hover:bg-surface-raised">
                    <td className={`px-4 py-3 font-mono text-[12px] text-text-secondary ${cellBorder}`}>
                      {item.external_id}
                    </td>
                    <td className={`px-4 py-3 font-mono text-[12px] text-text-secondary ${cellBorder}`}>
                      {item.order_external_id}
                    </td>
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>{item.buyer_login}</td>
                    <td className={`px-4 py-3 text-[12.5px] text-text-secondary ${cellBorder}`}>
                      {item.products_summary}
                    </td>
                    <td className={`px-4 py-3 text-[12px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {dateFormatter.format(new Date(item.return_date))}
                    </td>
                    <td className={`px-4 py-3 ${cellBorder}`}>
                      <span className="rounded-full bg-surface-raised px-2.5 py-1 font-mono text-[10.5px] text-text-secondary">
                        {item.status}
                      </span>
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

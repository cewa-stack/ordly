import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "../components/EmptyState";

const money = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: async () => {
      const result = await window.ordly.stats.get();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function useStockReport() {
  return useQuery({
    queryKey: ["stock-report"],
    queryFn: async () => {
      const result = await window.ordly.stats.stockReport();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function useShoppingList() {
  return useQuery({
    queryKey: ["stock-shopping-list"],
    queryFn: async () => {
      const result = await window.ordly.stats.shoppingList();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

function forecastToneClass(daysLeft: number): string {
  if (daysLeft <= 7) return "text-danger";
  if (daysLeft <= 14) return "text-warning";
  return "text-text-secondary";
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex-1 rounded-xl border border-border bg-surface p-4">
      <p className="text-caption text-text-secondary">{label}</p>
      <p className="mt-1.5 text-stat-value">{value}</p>
    </div>
  );
}

export function StatystykiScreen() {
  const stats = useStats();
  const report = useStockReport();
  const shoppingList = useShoppingList();

  return (
    <div>
      <h1 className="mb-5 text-title1">Statystyki</h1>

      {stats.isLoading && <p className="text-footnote text-text-secondary">Wczytywanie…</p>}
      {stats.isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać statystyk:{" "}
          {stats.error instanceof Error ? stats.error.message : "nieznany błąd"}
        </p>
      )}
      {stats.data && (
        <div className="mb-8 flex flex-wrap gap-3">
          <StatTile label="Zamówienia dziś" value={String(stats.data.orders_today)} />
          <StatTile label="Przychód dziś" value={money.format(stats.data.revenue_today)} />
          <StatTile label="Zamówienia w tym miesiącu" value={String(stats.data.orders_this_month)} />
          <StatTile
            label="Przychód w tym miesiącu"
            value={money.format(stats.data.revenue_this_month)}
          />
          <StatTile label="Wszystkie zamówienia" value={String(stats.data.total_orders)} />
        </div>
      )}

      <h2 className="mb-2 text-headline text-text-secondary">Prognoza zapasów (30 dni)</h2>
      {report.isLoading && <p className="text-footnote text-text-secondary">Wczytywanie…</p>}
      {report.isError && (
        <p className="mb-6 text-footnote text-danger">
          Nie udało się pobrać prognozy:{" "}
          {report.error instanceof Error ? report.error.message : "nieznany błąd"}
        </p>
      )}
      {report.data && report.data.forecasts.length === 0 && (
        <div className="mb-8">
          <EmptyState
            pose="stats"
            title="Brak danych do prognozy"
            description="Potrzebna jest sprzedaż z ostatnich 30 dni."
          />
        </div>
      )}
      {report.data && report.data.forecasts.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["SKU", "Nazwa", "Stan", "Śr. sprzedaż/dzień", "Zapas wystarczy na"].map((h) => (
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
              {report.data.forecasts.slice(0, 10).map((forecast, index) => {
                const cellBorder =
                  index === report.data!.forecasts.length - 1 || index === 9
                    ? ""
                    : "border-b border-border";
                return (
                  <tr key={forecast.sku} className="hover:bg-surface-raised">
                    <td className={`px-4 py-3 font-mono text-[12px] text-text-secondary ${cellBorder}`}>
                      {forecast.sku}
                    </td>
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>{forecast.name}</td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums ${cellBorder}`}>
                      {forecast.stock}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {forecast.avg_daily_sales.toFixed(1)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right text-[13px] font-semibold tabular-nums ${forecastToneClass(forecast.days_left)} ${cellBorder}`}
                    >
                      {forecast.days_left} {forecast.days_left === 1 ? "dzień" : "dni"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {shoppingList.data && shoppingList.data.length > 0 && (
        <>
          <h2 className="mb-2 text-headline text-text-secondary">Lista zakupów</h2>
          <div className="mb-8 overflow-hidden rounded-xl border border-border bg-surface">
            {shoppingList.data.slice(0, 12).map((item, index) => (
              <div
                key={item.sku}
                className={`flex items-center justify-between px-4 py-2.5 ${
                  index === shoppingList.data!.length - 1 ? "" : "border-b border-border"
                }`}
              >
                <span className="text-[13px]">{item.name}</span>
                <span className="font-mono text-[12px] text-warning">
                  {item.stock} / min {item.min_stock}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {report.data && report.data.items_without_sales.length > 0 && (
        <>
          <h2 className="mb-2 text-headline text-text-secondary">Bez sprzedaży (30 dni)</h2>
          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            {report.data.items_without_sales.slice(0, 10).map((item, index) => (
              <div
                key={item.sku}
                className={`px-4 py-2.5 text-[13px] text-text-secondary ${
                  index === report.data!.items_without_sales.length - 1 ? "" : "border-b border-border"
                }`}
              >
                {item.name}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

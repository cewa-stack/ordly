/**
 * Statystyki - siatka `1.55fr 1fr` (sekcja 4.4): slupki przychodu z 7 dni
 * (dzisiejszy slupek w `--coral`, animacja wysokosci 1 s przy wejsciu)
 * + pierscien podzialu kanalow z legenda. Pod spodem lista najczesciej
 * sprzedawanych.
 *
 * Podzial kanalow i lista najlepiej sprzedajacych sie sa liczone z
 * ostatnich zamowien, ktore backend faktycznie zwraca - podpis mowi to
 * wprost, zeby nikt nie czytal tego jako statystyki "ze wszech czasow".
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { EmptyState, ErrorState } from "../components/ui";
import { formatCurrency } from "../lib/format";
import type { Order } from "../types/api";

const DAY_LABELS = ["pon", "wt", "śr", "czw", "pt", "sob", "ndz"];

const CHANNEL_COLOR: Record<string, string> = {
  allegro: "var(--coral)",
  amazon: "var(--amber)",
  olx: "var(--violet)",
  ebay: "var(--teal-bright)",
};

/** Etykiety 7 dni wstecz, konczac na dzisiaj - zgodnie z kolejnoscia serii z backendu. */
function lastSevenDayLabels(): string[] {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    // getDay(): 0 = niedziela, a nasza tablica zaczyna sie od poniedzialku.
    return DAY_LABELS[(date.getDay() + 6) % 7];
  });
}

function RevenueBars({ series }: { series: number[] }) {
  const [grown, setGrown] = React.useState(false);
  const labels = lastSevenDayLabels();
  const max = Math.max(...series, 1);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setGrown(true), 40);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="flex h-[150px] items-end gap-[9px] pt-2">
      {series.map((value, index) => {
        const isToday = index === series.length - 1;
        return (
          <div
            key={index}
            className="flex h-full flex-1 flex-col items-center justify-end gap-2"
            title={formatCurrency(value)}
          >
            <span
              className="w-full max-w-[30px] rounded-[5px_5px_2px_2px] transition-[height] duration-1000 ease-ordly"
              style={{
                height: grown ? `${Math.max(2, (value / max) * 100)}%` : "0%",
                background: isToday
                  ? "linear-gradient(180deg, var(--coral), #C4533A)"
                  : "linear-gradient(180deg, var(--teal-bright), var(--teal-deep))",
              }}
            />
            <span className="o-mono text-[9.5px] text-slate-dim">{labels[index]}</span>
          </div>
        );
      })}
    </div>
  );
}

function ChannelDonut({ orders }: { orders: Order[] }) {
  const counts = orders.reduce<Record<string, number>>((acc, order) => {
    acc[order.marketplace] = (acc[order.marketplace] ?? 0) + 1;
    return acc;
  }, {});
  const total = orders.length;
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  if (total === 0) {
    return (
      <p className="py-6 text-center text-[12px] text-slate-dim">
        Brak zamówień do podziału na kanały.
      </p>
    );
  }

  let cursor = 0;
  const segments = entries.map(([channel, count]) => {
    const start = (cursor / total) * 100;
    cursor += count;
    const end = (cursor / total) * 100;
    const color = CHANNEL_COLOR[channel] ?? "var(--slate)";
    return `${color} ${start}% ${end}%`;
  });

  return (
    <>
      <div
        className="relative mx-auto my-1 h-[118px] w-[118px] rounded-full"
        style={{ background: `conic-gradient(${segments.join(", ")})` }}
      >
        <span className="absolute inset-[22px] rounded-full bg-panel-2" />
        <div className="absolute inset-0 z-[1] flex flex-col items-center justify-center">
          <span className="o-mono text-[19px] font-semibold">{total}</span>
          <span className="text-[9.5px] text-slate-dim">zamówień</span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {entries.map(([channel, count]) => (
          <div key={channel} className="flex items-center gap-[9px] text-[12px] text-slate">
            <i
              className="h-2 w-2 shrink-0 rounded-[2.5px]"
              style={{ background: CHANNEL_COLOR[channel] ?? "var(--slate)" }}
            />
            <span className="capitalize">{channel}</span>
            <span className="o-mono ml-auto text-[11px] text-white">
              {Math.round((count / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

export function StatystykiScreen() {
  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: async () => {
      const result = await window.ordly.stats.get();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const result = await window.ordly.stats.dashboard();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const ordersQuery = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const result = await window.ordly.orders.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const reportQuery = useQuery({
    queryKey: ["stock-report"],
    queryFn: async () => {
      const result = await window.ordly.stats.stockReport();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  if (statsQuery.isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać statystyk"
        detail={
          statsQuery.error instanceof Error
            ? statsQuery.error.message
            : "Pi nie odpowiedziało na zapytanie o statystyki."
        }
        onRetry={() => void statsQuery.refetch()}
      />
    );
  }

  const orders = ordersQuery.data ?? [];

  // Najczesciej sprzedawane - liczone ze sztuk w pobranych zamowieniach.
  const bestSellers = Object.values(
    orders
      .flatMap((order) => order.products)
      .reduce<Record<string, { name: string; quantity: number; revenue: number }>>(
        (acc, product) => {
          const key = product.name;
          const existing = acc[key] ?? { name: key, quantity: 0, revenue: 0 };
          existing.quantity += product.quantity;
          existing.revenue += product.total_price;
          acc[key] = existing;
          return acc;
        },
        {}
      )
  )
    .sort((a, b) => b.quantity - a.quantity)
    .slice(0, 6);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      <div className="grid grid-cols-4 gap-3 max-[940px]:grid-cols-2">
        <SummaryTile label="Zamówienia dziś" value={String(statsQuery.data?.orders_today ?? 0)} />
        <SummaryTile
          label="Przychód dziś"
          value={formatCurrency(statsQuery.data?.revenue_today ?? 0)}
          accent
        />
        <SummaryTile
          label="Przychód w tym miesiącu"
          value={formatCurrency(statsQuery.data?.revenue_this_month ?? 0)}
        />
        <SummaryTile label="Zamówienia łącznie" value={String(statsQuery.data?.total_orders ?? 0)} />
      </div>

      <div className="grid grid-cols-[1.55fr_minmax(0,1fr)] gap-3.5 max-[940px]:grid-cols-1">
        <div className="flex flex-col gap-[15px] rounded-md border border-line bg-panel-2 p-[18px]">
          <h4 className="text-[13px] font-semibold">Przychód z ostatnich 7 dni</h4>
          <RevenueBars series={dashboardQuery.data?.revenue_last_7_days ?? Array(7).fill(0)} />
        </div>

        <div className="flex flex-col gap-[15px] rounded-md border border-line bg-panel-2 p-[18px]">
          <h4 className="text-[13px] font-semibold">Podział kanałów</h4>
          <ChannelDonut orders={orders} />
          <p className="text-[10.5px] leading-[1.5] text-slate-dim">
            Liczone z {orders.length} ostatnich zamówień pobranych z Pi.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2.5 rounded-md border border-line bg-panel-2 p-[18px]">
        <h4 className="text-[13px] font-semibold">Najczęściej sprzedawane</h4>
        {bestSellers.length === 0 ? (
          <EmptyState
            pose="idle"
            title="Brak danych sprzedażowych"
            description="Gdy pojawią się zamówienia, Ordi policzy, co schodzi najlepiej."
          />
        ) : (
          bestSellers.map((product) => (
            <div
              key={product.name}
              className="flex items-center gap-3 border-b border-line py-2 text-[12.5px] last:border-b-0"
            >
              <span className="min-w-0 flex-1 truncate text-white">{product.name}</span>
              <span className="o-mono shrink-0 text-slate">{product.quantity} szt.</span>
              <span className="o-mono w-[90px] shrink-0 text-right text-teal-bright">
                {formatCurrency(product.revenue)}
              </span>
            </div>
          ))
        )}
      </div>

      {reportQuery.data && (
        <div className="flex flex-col gap-2.5 rounded-md border border-line bg-panel-2 p-[18px]">
          <h4 className="text-[13px] font-semibold">Prognoza wyczerpania zapasu</h4>
          {reportQuery.data.forecasts.length === 0 ? (
            <p className="text-[12px] text-slate-dim">
              Za mało historii sprzedaży, żeby cokolwiek prognozować.
            </p>
          ) : (
            reportQuery.data.forecasts.slice(0, 6).map((forecast) => (
              <div
                key={forecast.sku}
                className="flex items-center gap-3 border-b border-line py-2 text-[12.5px] last:border-b-0"
              >
                <span className="min-w-0 flex-1 truncate text-white">{forecast.name}</span>
                <span className="o-mono shrink-0 text-slate">{forecast.stock} szt.</span>
                <span
                  className={`o-mono w-[90px] shrink-0 text-right ${
                    forecast.days_left <= 7 ? "text-coral" : "text-slate"
                  }`}
                >
                  {forecast.days_left} dni
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function SummaryTile({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-line bg-panel-2 p-4">
      <span className="text-[11px] text-slate-dim">{label}</span>
      <span className={`o-counter ${accent ? "text-teal-bright" : "text-white"}`}>{value}</span>
    </div>
  );
}

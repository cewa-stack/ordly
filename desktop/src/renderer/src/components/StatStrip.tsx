/**
 * Pasek statystyk - widoczny WYLACZNIE na ekranie Start (sekcja 4.1).
 *
 * Liczniki animuja sie przy pierwszym wejsciu na ekran: 950 ms,
 * krzywa ease-out szescienna `1 - (1-t)^3` (sekcja 2.6).
 *
 * Iskierka (sparkline) jest TYLKO przy przychodzie, bo tylko dla niego
 * backend zwraca prawdziwy szereg 7-dniowy (`revenue_last_7_days`).
 * Dorysowanie jej przy pozostalych licznikach byloby wykresem
 * zmyslonych danych - patrz [[feedback-no-phantom-features]].
 */
import * as React from "react";
import type { DashboardSummary } from "../types/api";
import { formatCurrency } from "../lib/format";

const COUNTER_DURATION_MS = 950;

/** Animowany licznik. Uruchamia sie raz, przy pojawieniu sie wartosci. */
function useCountUp(target: number): number {
  const [value, setValue] = React.useState(0);
  const started = React.useRef(false);

  React.useEffect(() => {
    if (started.current || target === 0) {
      setValue(target);
      return;
    }
    started.current = true;
    let frame = 0;
    const startedAt = performance.now();

    function tick(now: number) {
      const t = Math.min(1, (now - startedAt) / COUNTER_DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    }

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return value;
}

function Sparkline({ series }: { series: number[] }) {
  if (series.length < 2) return <div className="h-5" />;
  const max = Math.max(...series, 1);
  const points = series
    .map((value, index) => {
      const x = (index / (series.length - 1)) * 100;
      const y = 18 - (value / max) * 16;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 20" preserveAspectRatio="none" className="h-5 w-full opacity-85">
      <polyline
        points={points}
        fill="none"
        stroke="var(--teal-bright)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Stat({
  label,
  value,
  tone = "plain",
  delta,
  children,
}: {
  label: string;
  value: string;
  tone?: "plain" | "up" | "warn";
  delta?: string;
  children?: React.ReactNode;
}) {
  const toneClass =
    tone === "up" ? "text-teal-bright" : tone === "warn" ? "text-coral" : "text-white";
  return (
    <div className="flex flex-col gap-[7px] bg-panel px-[22px] pb-[13px] pt-[15px]">
      <div className="text-[11px] text-slate-dim">{label}</div>
      <div className="flex items-end gap-[9px]">
        <span className={`o-counter ${toneClass}`}>{value}</span>
        {delta && <span className="o-mono pb-0.5 text-[10px] text-slate-dim">{delta}</span>}
      </div>
      {children ?? <div className="h-5" />}
    </div>
  );
}

interface StatStripProps {
  dashboard: DashboardSummary | undefined;
  openIssues: number;
  loading: boolean;
}

export function StatStrip({ dashboard, openIssues, loading }: StatStripProps) {
  const ordersToday = useCountUp(dashboard?.orders_today ?? 0);
  const revenueToday = useCountUp(dashboard?.revenue_today ?? 0);
  const lowStock = useCountUp(dashboard?.low_stock_count ?? 0);
  const issues = useCountUp(openIssues);

  if (loading) {
    return (
      <div className="grid shrink-0 grid-cols-4 gap-px border-b border-line bg-line">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="flex flex-col gap-[7px] bg-panel px-[22px] pb-[13px] pt-[15px]">
            <span className="o-skeleton-bar h-[11px] w-[60%]" />
            <span className="o-skeleton-bar h-[22px] w-[40%]" />
            <span className="o-skeleton-bar h-5 w-full" />
          </div>
        ))}
      </div>
    );
  }

  const trend = dashboard?.trend_percent ?? 0;
  const trendLabel = trend === 0 ? undefined : `${trend > 0 ? "+" : ""}${Math.round(trend)}%`;

  return (
    <div className="grid shrink-0 grid-cols-4 gap-px border-b border-line bg-line max-[940px]:grid-cols-2">
      <Stat label="Zamówienia dziś" value={String(Math.round(ordersToday))} />
      <Stat
        label="Przychód dziś"
        value={formatCurrency(revenueToday, { round: true })}
        tone="up"
        delta={trendLabel}
      >
        <Sparkline series={dashboard?.revenue_last_7_days ?? []} />
      </Stat>
      <Stat
        label="Niski stan"
        value={String(Math.round(lowStock))}
        tone={lowStock > 0 ? "warn" : "plain"}
        delta="produkty"
      />
      <Stat
        label="Czeka na odpowiedź"
        value={String(Math.round(issues))}
        tone={issues > 0 ? "warn" : "plain"}
        delta="dyskusje"
      />
    </div>
  );
}

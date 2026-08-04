/**
 * Ekran Start (sekcja 4.4): hero z najpilniejsza rzecza do zrobienia ->
 * trzy karty skrotow z duzymi liczbami -> os "Dziś w systemie".
 *
 * Naglowek hero nie jest powitaniem - mowi, co JEST do zrobienia teraz.
 * Gdy nie ma nic pilnego, mowi to wprost, zamiast udawac zajetosc.
 */
import { useQuery } from "@tanstack/react-query";
import { BoxIcon, ChatIcon, GridIcon, RefreshIcon } from "../icons";
import { Button, SectionLabel } from "../components/ui";
import { Mascot } from "../components/Mascot";
import { useSync } from "../lib/sync";
import { formatCurrency, formatTime } from "../lib/format";
import { isPendingFulfillment } from "../lib/fulfillment";
import type { ViewId } from "../components/Sidebar";

/**
 * Kolor kropki wg typu zdarzenia. Nieznany typ dostaje kolor neutralny -
 * lepszy niz zgadywanie znaczenia zdarzenia, ktorego jeszcze nie ma.
 */
const EVENT_DOT: Record<string, string> = {
  OrderCreated: "bg-teal-bright",
  OrderCancelled: "bg-coral",
  OrderPackingStarted: "bg-amber",
  OrderReturnCreated: "bg-violet",
  LowStockDetected: "bg-coral",
  NotificationSent: "bg-slate-dim",
  SyncStarted: "bg-slate-dim",
  SyncFinished: "bg-teal-deep",
};

const EVENT_LABEL: Record<string, string> = {
  OrderCreated: "Nowe zamówienie",
  OrderCancelled: "Anulowane zamówienie",
  OrderPackingStarted: "Rozpoczęto pakowanie",
  OrderReturnCreated: "Nowy zwrot",
  LowStockDetected: "Niski stan magazynowy",
  NotificationSent: "Wysłano powiadomienie",
  SyncStarted: "Start synchronizacji",
  SyncFinished: "Koniec synchronizacji",
};

function ShortcutCard({
  icon,
  tint,
  value,
  caption,
  onClick,
}: {
  icon: React.ReactNode;
  tint: "teal" | "coral" | "violet";
  value: string;
  caption: string;
  onClick: () => void;
}) {
  const tintClass =
    tint === "teal"
      ? "bg-teal-dim text-teal-bright"
      : tint === "coral"
        ? "bg-coral-dim text-coral"
        : "bg-[rgba(167,155,255,.13)] text-violet";
  return (
    <button
      onClick={onClick}
      className="flex flex-col gap-[9px] rounded-md border border-line bg-panel-2 p-4 text-left transition-[border-color,transform] duration-[180ms] ease-ordly hover:-translate-y-0.5 hover:border-line-strong"
    >
      <span className={`flex h-[30px] w-[30px] items-center justify-center rounded-[9px] ${tintClass}`}>
        {icon}
      </span>
      <span className="o-mono text-[24px] font-semibold tracking-[-.02em]">{value}</span>
      <span className="text-[12px] leading-[1.45] text-slate-dim">{caption}</span>
    </button>
  );
}

export function StartScreen({ onNavigate }: { onNavigate: (view: ViewId) => void }) {
  const { sync, phase } = useSync();

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

  const issuesQuery = useQuery({
    queryKey: ["issues"],
    queryFn: async () => {
      const result = await window.ordly.issues.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const eventsQuery = useQuery({
    queryKey: ["events"],
    queryFn: async () => {
      const result = await window.ordly.stats.events();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    // Dziennik zdarzen sam sie podnosi po nieudanej probie. Przy zimnym
    // starcie appki Tailscale bywa jeszcze nieuzbrojony i pierwsze
    // zapytanie leci w prozne - bez tego czerwony komunikat zostawal na
    // ekranie do nastepnego przejscia miedzy zakladkami.
    refetchInterval: 60_000,
  });

  const dashboard = dashboardQuery.data;
  const pendingOrders = (ordersQuery.data ?? []).filter((order) =>
    isPendingFulfillment(order.fulfillment_status)
  );
  const openIssues = (issuesQuery.data ?? []).filter((issue) => issue.chat_active);
  const lowStock = dashboard?.low_stock_count ?? 0;

  // Najpilniejsza rzecz - kolejnosc odzwierciedla realny koszt zwloki:
  // niezapakowane zamowienie kosztuje najwiecej, potem czekajacy klient,
  // na koncu magazyn (ktory da sie uzupelnic jutro).
  const headline =
    pendingOrders.length > 0
      ? `${pendingOrders.length} ${
          pendingOrders.length === 1 ? "zamówienie czeka" : "zamówień czeka"
        } na spakowanie`
      : openIssues.length > 0
        ? `${openIssues.length} ${
            openIssues.length === 1 ? "klient czeka" : "klientów czeka"
          } na odpowiedź`
        : lowStock > 0
          ? `${lowStock} ${lowStock === 1 ? "produkt" : "produkty"} poniżej progu`
          : "Wszystko obsłużone";

  const subline =
    pendingOrders.length > 0
      ? "Otwórz zamówienia, spakuj i oznacz je jako gotowe do wysyłki."
      : openIssues.length > 0
        ? "Odpowiedz na otwarte dyskusje, zanim kupujący zdąży się zniecierpliwić."
        : lowStock > 0
          ? "Ordi przygotował listę zakupów - wyślij zamówienie do hurtowni."
          : "Zero zaległości. Ordi pilnuje kanałów i da znać, gdy coś się pojawi.";

  const primaryAction: { label: string; go: ViewId } =
    pendingOrders.length > 0
      ? { label: "Otwórz zamówienia", go: "zamowienia" }
      : openIssues.length > 0
        ? { label: "Otwórz dyskusje", go: "dyskusje" }
        : lowStock > 0
          ? { label: "Otwórz magazyn", go: "magazyn" }
          : { label: "Zobacz statystyki", go: "statystyki" };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-[22px] overflow-y-auto p-6">
      <section
        className="flex items-center gap-5 rounded-lg border border-line px-[22px] py-5"
        style={{
          background: "linear-gradient(120deg, var(--panel-2), rgba(31,125,128,.1))",
        }}
      >
        <Mascot pose="orders" size={78} />
        <div className="min-w-0 flex-1">
          <h3 className="o-hero-title mb-1.5">{headline}</h3>
          <p className="max-w-[440px] text-[13.5px] leading-[1.55] text-slate">{subline}</p>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <Button onClick={() => onNavigate(primaryAction.go)}>{primaryAction.label}</Button>
          <Button
            variant="ghost"
            onClick={sync}
            disabled={phase !== "idle"}
            icon={<RefreshIcon size={14} className={phase === "working" ? "animate-spin-ring" : ""} />}
          >
            {phase === "working" ? "Synchronizuję…" : "Synchronizuj"}
          </Button>
        </div>
      </section>

      <section className="grid grid-cols-3 gap-3 max-[940px]:grid-cols-1">
        <ShortcutCard
          icon={<BoxIcon size={16} />}
          tint="teal"
          value={String(pendingOrders.length)}
          caption="Zamówienia do obsłużenia"
          onClick={() => onNavigate("zamowienia")}
        />
        <ShortcutCard
          icon={<GridIcon size={16} />}
          tint="coral"
          value={String(lowStock)}
          caption="Produkty poniżej progu"
          onClick={() => onNavigate("magazyn")}
        />
        <ShortcutCard
          icon={<ChatIcon size={16} />}
          tint="violet"
          value={String(openIssues.length)}
          caption="Otwarte dyskusje z kupującymi"
          onClick={() => onNavigate("dyskusje")}
        />
      </section>

      <section className="flex flex-col gap-0.5">
        <SectionLabel>Dziś w systemie</SectionLabel>
        {eventsQuery.isLoading && (
          <div className="flex flex-col gap-2 pt-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <span key={index} className="o-skeleton-bar h-[14px] w-[70%]" />
            ))}
          </div>
        )}
        {eventsQuery.isError && (
          <p className="pt-2 text-[12.5px] leading-[1.5] text-coral">
            Nie udało się pobrać dziennika zdarzeń z Pi.{" "}
            {eventsQuery.error instanceof Error ? eventsQuery.error.message : ""}
          </p>
        )}
        {eventsQuery.data?.length === 0 && (
          <p className="pt-2 text-[12.5px] text-slate-dim">
            Ordi jeszcze nic dziś nie zanotował.
          </p>
        )}
        {(eventsQuery.data ?? []).slice(0, 12).map((event, index) => (
          <div
            key={`${event.created_at}-${index}`}
            className="flex items-center gap-[11px] rounded-[9px] px-3 py-2.5 text-[12.5px] transition-colors duration-150 hover:bg-panel-2"
          >
            <span className="o-mono w-11 shrink-0 text-[10.5px] text-slate-dim">
              {formatTime(event.created_at)}
            </span>
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                EVENT_DOT[event.event_type] ?? "bg-slate-dim"
              }`}
            />
            <span className="min-w-0 flex-1 truncate text-slate">
              <b className="font-medium text-white">
                {EVENT_LABEL[event.event_type] ?? event.event_type}
              </b>
            </span>
          </div>
        ))}
      </section>

      {dashboard && (
        <p className="o-mono pb-1 text-[10.5px] text-slate-dim">
          Przychód dziś {formatCurrency(dashboard.revenue_today)} · ostatnia synchronizacja{" "}
          {dashboard.last_sync_human}
        </p>
      )}
    </div>
  );
}

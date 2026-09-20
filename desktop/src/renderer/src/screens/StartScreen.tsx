/**
 * Ekran Start (sekcja 8 instrukcji "Nokturn").
 *
 * Wysokosci w pionie sa WYNIKIEM, nie zalozeniem - wynikaja z wysokosci
 * zawartosci. Przy oknie 1280 x 800 obszar roboczy ma 629 px:
 *
 *   karta powitalna   204 px  flex:none
 *   pasek asystenta    45 px  flex:none
 *   rzad kafli         92 px  flex:none
 *   dolne kolumny     flex:1  (224 px)
 *
 * Jesli dolne kolumny maja mniej niz 224 px - przytnij karte powitalna,
 * nie liste.
 *
 * ODSTEPSTWO OD INSTRUKCJI (swiadome): czwarty kafel miał pokazywac
 * "Niskie stany". Magazyn nie ma juz progow ani SKU - ilosc wisi wprost
 * na ofercie i wpisuje sie ja recznie - wiec progu nie ma z czym
 * porownac. Kafel pokazuje wiec rzecz, ktora naprawde da sie policzyc
 * i ktora naprawde boli: oferty obiecujace wiecej sztuk, niz lezy na
 * polce. Zmyslony prog bylby przyciskiem-widmem.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpIcon, RefreshIcon } from "../icons";
import {
  Button,
  KpiTile,
  MarketplaceBadge,
  PanelHeader,
  PanelLink,
  Pill,
} from "../components/ui";
import { Ordlak } from "../components/Ordlak";
import { useSync } from "../lib/sync";
import { useOrdlakState } from "../lib/ordlakState";
import {
  formatCurrency,
  formatPlural,
  formatTime,
  parseApiDate,
} from "../lib/format";
import { displayFulfillmentLabel, displayFulfillmentTone, isPendingOrder } from "../lib/fulfillment";
import type { ViewId } from "../components/Sidebar";
import type { Order } from "../types/api";

/**
 * Kolor kropki wg typu zdarzenia. Nieznany typ dostaje kolor neutralny -
 * lepszy niz zgadywanie znaczenia zdarzenia, ktorego jeszcze nie ma.
 */
const EVENT_DOT: Record<string, string> = {
  OrderCreated: "bg-teal",
  OrderCancelled: "bg-coral",
  OrderPackingStarted: "bg-amber",
  OrderReturnCreated: "bg-violet",
  AllegroLokalnieEventDetected: "bg-teal-deep",
  OlxEventDetected: "bg-violet",
  DisputeNoticeDetected: "bg-coral",
};

const EVENT_LABEL: Record<string, string> = {
  OrderCreated: "Nowe zamówienie",
  OrderCancelled: "Anulowane zamówienie",
  OrderPackingStarted: "Rozpoczęto pakowanie",
  OrderReturnCreated: "Nowy zwrot",
  AllegroLokalnieEventDetected: "Mail z Allegro Lokalnie",
  OlxEventDetected: "Mail z OLX",
  DisputeNoticeDetected: "Nowa dyskusja",
};

/**
 * Wpisy powstajace przy KAZDEJ synchronizacji (co minute). Na osi
 * "Dzisiaj" zaslanialy zamowienia i zwroty - backend je juz pomija
 * (`include_sync=false`), a to jest siatka na starszy backend.
 */
const SYNC_EVENT_TYPES = new Set(["SyncStarted", "SyncFinished"]);

/** Dwa REALNE przyklady zapytan - nie "Zapytaj o cokolwiek". */
const ASSISTANT_EXAMPLES = [
  "Podsumuj dzisiejszą sprzedaż",
  "Czego brakuje na półce?",
];

function isToday(iso: string): boolean {
  return parseApiDate(iso).toDateString() === new Date().toDateString();
}

function greetingFor(hour: number): string {
  if (hour < 5) return "Dobra noc";
  if (hour < 11) return "Dzień dobry";
  if (hour < 18) return "Cześć";
  return "Dobry wieczór";
}

/** Mikrostatystyka na karcie powitalnej - etykieta, liczba, jednostka. */
function MicroStat({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="min-w-0">
      <div className="o-eyebrow truncate">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="o-display o-num text-[23px] leading-none tracking-[-.03em]">
          {value}
        </span>
        <span className="text-[11.5px] text-text-3">{unit}</span>
      </div>
    </div>
  );
}

/**
 * Wiersz listy "Wymaga uwagi" (sekcja 7). Szerokosci stale, w tej
 * kolejnosci: kanal 68 · nazwisko i pozycje flex-1 · godzina 50 prawo ·
 * kwota 94 prawo · status 96. Dzieki temu prawa krawedz listy jest
 * PROSTA, a nazwiska zaczynaja sie w jednej linii pionowej.
 */
function AttentionRow({ order, onOpen }: { order: Order; onOpen: () => void }) {
  const items = order.products.map((product) => product.name).join(", ");
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-center gap-3 border-b border-line px-4 py-2 text-left transition-colors duration-150 ease-ordly last:border-b-0 hover:bg-panel-2"
    >
      <MarketplaceBadge marketplace={order.marketplace} />
      <span className="min-w-0 flex-1">
        <span className="o-row-name block truncate text-text">{order.buyer_login}</span>
        <span className="block truncate text-[11px] text-text-3">
          {items || "brak pozycji"}
        </span>
      </span>
      <span className="o-mono w-[50px] shrink-0 text-right text-[11px] text-text-3">
        {formatTime(order.order_date)}
      </span>
      <span className="o-mono w-[94px] shrink-0 whitespace-nowrap text-right text-[11.5px] text-text-2">
        {formatCurrency(order.total_amount)}
      </span>
      <Pill tone={displayFulfillmentTone(order)} fixed>
        {displayFulfillmentLabel(order)}
      </Pill>
    </button>
  );
}

interface StartScreenProps {
  onNavigate: (view: ViewId) => void;
  /** Wysyla pytanie do ekranu asystenta i tam je otwiera. */
  onAsk: (question: string) => void;
  username: string;
}

export function StartScreen({ onNavigate, onAsk, username }: StartScreenProps) {
  const { sync, phase, lastSyncAt, subtitle } = useSync();
  const { state: ordlakState } = useOrdlakState();
  const [question, setQuestion] = React.useState("");
  const [exampleIndex, setExampleIndex] = React.useState(0);

  // Placeholder podmienia sie co 6 s - dwa realne przyklady zamiast
  // jednego ogolnika. Bez tego drugi przyklad nigdy nie jest widoczny.
  React.useEffect(() => {
    const timer = window.setInterval(
      () => setExampleIndex((index) => (index + 1) % ASSISTANT_EXAMPLES.length),
      6000
    );
    return () => window.clearInterval(timer);
  }, []);

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

  const offersQuery = useQuery({
    queryKey: ["offers"],
    queryFn: async () => {
      const result = await window.ordly.stock.offers();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const eventsQuery = useQuery({
    queryKey: ["events"],
    queryFn: async () => {
      const result = await window.ordly.stats.events();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    refetchInterval: 60_000,
  });

  const dashboard = dashboardQuery.data;
  const pendingOrders = (ordersQuery.data ?? []).filter(isPendingOrder);
  const openIssues = (issuesQuery.data ?? []).filter((issue) => issue.chat_active);
  const offers = offersQuery.data ?? [];

  // Rozjazd: oferta obiecuje wiecej sztuk, niz lezy na polce. Oferty
  // nigdy nie liczone (`null`) nie sa rozjazdem - sa nieznana.
  const mismatched = offers.filter(
    (offer) => offer.quantity_on_hand !== null && offer.quantity_on_hand < offer.available_stock
  );
  const uncounted = offers.filter((offer) => offer.quantity_on_hand === null);

  const todayOrders = (ordersQuery.data ?? []).filter((order) => isToday(order.order_date));
  const revenueToday = dashboard?.revenue_today ?? 0;

  // "Dzisiaj" znaczy DZIS - dziennik zwraca ostatnie wpisy bez wzgledu
  // na date, wiec rano lista pokazywala jeszcze wczorajszy wieczor.
  const todayEvents = (eventsQuery.data ?? []).filter(
    (event) => !SYNC_EVENT_TYPES.has(event.event_type) && isToday(event.created_at)
  );

  // Cztery wiersze - liczba w liczniku panelu MUSI zgadzac sie z liczba
  // widocznych wierszy, wiec licznik liczy to, co widac.
  const attention = pendingOrders.slice(0, 4);
  const timeline = todayEvents.slice(0, 4);

  const firstName = username.split(/[\s._-]+/)[0] || username;
  const greeting = greetingFor(new Date().getHours());

  // Zdanie o stanie dnia - ZDANIE, nie lista.
  const stateSentence =
    pendingOrders.length > 0 ? (
      <>
        Czeka <b className="font-semibold text-text">
          {formatPlural(pendingOrders.length, [
            "zamówienie",
            "zamówienia",
            "zamówień",
          ])}
        </b>{" "}
        do spakowania
        {openIssues.length > 0 && (
          <>
            {" "}
            i{" "}
            <b className="font-semibold text-text">
              {formatPlural(openIssues.length, [
                "otwarta dyskusja",
                "otwarte dyskusje",
                "otwartych dyskusji",
              ])}
            </b>
          </>
        )}
        .
      </>
    ) : openIssues.length > 0 ? (
      <>
        Paczki są spakowane, ale{" "}
        <b className="font-semibold text-text">
          {formatPlural(openIssues.length, [
            "kupujący czeka",
            "kupujących czeka",
            "kupujących czeka",
          ])}
        </b>{" "}
        na odpowiedź.
      </>
    ) : (
      <>
        Zero zaległości — <b className="font-semibold text-text">wszystko obsłużone</b>. Ordlak
        pilnuje kanałów i da znać, gdy coś się pojawi.
      </>
    );

  const primary: { label: string; go: ViewId } =
    pendingOrders.length > 0
      ? { label: "Otwórz zamówienia", go: "zamowienia" }
      : openIssues.length > 0
        ? { label: "Otwórz dyskusje", go: "dyskusje" }
        : { label: "Zobacz statystyki", go: "statystyki" };

  function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    onAsk(trimmed);
    setQuestion("");
  }

  return (
    <div
      data-frame
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-[22px] pb-[18px] pt-4"
    >
      {/* ---------------------------------------------- karta powitalna */}
      <section className="relative flex h-[204px] shrink-0 items-center gap-5 overflow-hidden rounded-xl border border-line bg-panel px-6 py-4">
        {/* Jedno zrodlo swiatla na karcie - bez zmywu na cala powierzchnie. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -top-[90px] right-[-40px] h-[340px] w-[460px]"
          style={{
            background:
              "radial-gradient(closest-side, var(--teal-glow), transparent 72%)",
          }}
        />
        <div className="relative z-[1] flex min-w-0 flex-1 flex-col">
          <div className="o-mono text-[10.5px] uppercase tracking-[.15em] text-text-3">
            {lastSyncAt || dashboard ? `Dyżur otwarty · ${subtitle}` : "Dyżur otwarty"}
          </div>
          <h2 className="o-greet my-[5px] mt-1.5 truncate">
            {greeting}, <span className="text-teal">{firstName}</span>
          </h2>
          <p className="max-w-[460px] text-[13.5px] leading-[1.5] text-text-2">
            {stateSentence}
          </p>

          <div className="mt-[13px] flex gap-[30px]">
            <MicroStat
              label="Dziś"
              value={String(dashboard?.orders_today ?? todayOrders.length)}
              unit="zamówień"
            />
            <MicroStat
              label="Do wysyłki"
              value={String(dashboard?.orders_to_ship ?? pendingOrders.length)}
              unit="paczek"
            />
            <MicroStat
              label="Przychód"
              value={formatCurrency(revenueToday, { round: true }).replace(" zł", "")}
              unit="zł"
            />
          </div>

          <div className="mt-3 flex gap-2">
            <Button onClick={() => onNavigate(primary.go)}>{primary.label}</Button>
            <Button
              variant="ghost"
              onClick={sync}
              disabled={phase !== "idle"}
              icon={
                <RefreshIcon
                  size={14}
                  className={phase === "working" ? "animate-spin-ring" : ""}
                />
              }
            >
              {phase === "working" ? "Synchronizuję…" : "Synchronizuj"}
            </Button>
          </div>
        </div>

        <div className="relative z-[1] flex h-[140px] w-[158px] shrink-0 items-center justify-center">
          <Ordlak state={ordlakState} size={134} />
        </div>
      </section>

      {/* ------------------------------------------- pasek asystenta 45 px */}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
        }}
        className="flex h-[45px] shrink-0 items-center gap-3 rounded-pill border border-line bg-panel py-2 pl-4 pr-2"
      >
        {/* Po lewej Ordlak 22 px, nie ikona gwiazdki. */}
        <Ordlak state={ordlakState} size={22} className="shrink-0" />
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={ASSISTANT_EXAMPLES[exampleIndex]}
          aria-label="Zapytaj Ordlaka"
          className="min-w-0 flex-1 bg-transparent text-[12.5px] text-text outline-none placeholder:text-text-3"
        />
        <button
          type="submit"
          disabled={question.trim().length === 0}
          aria-label="Zapytaj Ordlaka"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal text-on-teal transition-opacity duration-150 disabled:opacity-40"
          style={{ boxShadow: "0 0 0 5px var(--teal-glow)" }}
        >
          <ArrowUpIcon size={15} strokeWidth={2} />
        </button>
      </form>

      {/* ------------------------------------------------ rzad kafli 92 px */}
      <section className="grid h-[92px] shrink-0 grid-cols-4 gap-3">
        <KpiTile
          label="Do spakowania"
          tint="coral"
          value={String(pendingOrders.length)}
          delta={pendingOrders.length > 0 ? "czeka" : "czysto"}
          deltaTone={pendingOrders.length > 0 ? "wait" : "neutral"}
          onClick={() => onNavigate("zamowienia")}
        />
        <KpiTile
          label="Nowe dziś"
          tint="teal"
          value={String(dashboard?.orders_today ?? todayOrders.length)}
          delta={
            dashboard?.trend_percent
              ? `${dashboard.trend_percent > 0 ? "+" : ""}${Math.round(dashboard.trend_percent)}%`
              : undefined
          }
          deltaTone={(dashboard?.trend_percent ?? 0) >= 0 ? "up" : "neutral"}
          onClick={() => onNavigate("zamowienia")}
        />
        <KpiTile
          label="Wartość dziś"
          tint="teal"
          value={formatCurrency(revenueToday, { round: true })}
          series={dashboard?.revenue_last_7_days}
          onClick={() => onNavigate("statystyki")}
        />
        <KpiTile
          label="Rozjazd stanów"
          tint="amber"
          value={String(mismatched.length)}
          delta={uncounted.length > 0 ? `${uncounted.length} nieliczonych` : undefined}
          onClick={() => onNavigate("magazyn")}
        />
      </section>

      {/* ---------------------------------------------- dolne kolumny 1fr */}
      <section className="grid min-h-0 flex-1 grid-cols-[1.32fr_1fr] gap-3">
        {/* --- Wymaga uwagi --- */}
        <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-panel">
          <PanelHeader
            title="Wymaga uwagi"
            count={attention.length}
            action={
              <PanelLink onClick={() => onNavigate("zamowienia")}>Wszystkie</PanelLink>
            }
          />
          <div className="o-fade-b min-h-0 flex-1 overflow-y-auto">
            {ordersQuery.isLoading && (
              <div className="flex flex-col gap-2 p-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <span key={index} className="o-skeleton-bar h-[26px] w-full" />
                ))}
              </div>
            )}
            {!ordersQuery.isLoading && attention.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
                <Ordlak state="sleep" size={48} />
                <p className="text-[12px] text-text-3">
                  Nic nie czeka na spakowanie.
                </p>
              </div>
            )}
            {attention.map((order) => (
              <AttentionRow
                key={order.external_id}
                order={order}
                onOpen={() => onNavigate("zamowienia")}
              />
            ))}
          </div>
        </div>

        {/* --- Dzisiaj --- */}
        <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-panel">
          <PanelHeader
            title="Dzisiaj"
            action={<PanelLink onClick={() => onNavigate("statystyki")}>Dziennik</PanelLink>}
          />
          <div className="o-fade-b min-h-0 flex-1 overflow-y-auto px-4 py-[5px]">
            {eventsQuery.isError && (
              <p className="py-2 text-[12px] leading-[1.5] text-coral">
                Nie udało się pobrać dziennika zdarzeń z Pi.
              </p>
            )}
            {!eventsQuery.isError && timeline.length === 0 && (
              <p className="py-2 text-[12px] text-text-3">
                Ordlak jeszcze nic dziś nie zanotował.
              </p>
            )}
            {timeline.map((event, index) => (
              <div key={`${event.created_at}-${index}`} className="flex gap-3 py-1.5">
                <span
                  aria-hidden="true"
                  className={`mt-[5px] h-[7px] w-[7px] shrink-0 rounded-full ${
                    index === 0
                      ? "bg-teal"
                      : `${EVENT_DOT[event.event_type] ?? "bg-transparent"} ring-1 ring-text-3`
                  }`}
                  style={
                    index === 0 ? { boxShadow: "0 0 0 4px var(--teal-glow)" } : undefined
                  }
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] text-text">
                    {EVENT_LABEL[event.event_type] ?? event.event_type}
                  </span>
                  <span className="o-mono block text-[9.5px] text-text-3">
                    {formatTime(event.created_at)} · {event.level.toLowerCase()}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

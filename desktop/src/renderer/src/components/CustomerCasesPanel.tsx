/**
 * Rejestr anulowan i zwrotow pieniedzy (pozycje z Notion "Brak
 * automatycznego zbierania danych klientow...", "Brak miejsca i
 * jednolitego formatu..." i "Brak danych potrzebnych do pozniejszego
 * kontaktu...").
 *
 * Jeden rekord na zamowienie. Filtry: data, powod, zrodlo (status obslugi
 * wybiera rodzic - podzakladki). Szybki filtr "Brak towaru" odnajduje
 * wszystkich klientow, ktorych zamowienia anulowano z braku produktu.
 *
 * Puste pole = "nieuzupelnione" - nigdy zgadywana wartosc. Rekord nie ma
 * telefonu, e-maila ani imienia i nazwiska (decyzja D7): klienta
 * identyfikuje login Allegro, kontakt przez Allegro po numerze zamowienia.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Chip, EmptyState, ErrorState, MarketplaceBadge, Pill, SkeletonRows } from "./ui";
import { useToast } from "../lib/toast";
import { formatDateTime } from "../lib/format";
import type {
  CaseHandling,
  CaseKind,
  CaseQuery,
  CaseReason,
  CaseSource,
  CustomerCase,
} from "../types/api";

export const CASE_REASON_LABEL: Record<CaseReason, string> = {
  OUT_OF_STOCK: "Brak towaru",
  PAYMENT_PROBLEM: "Problem z płatnością",
  BUYER_RESIGNED: "Rezygnacja klienta",
  OTHER: "Inna",
};

export const CASE_HANDLING_LABEL: Record<CaseHandling, string> = {
  REPORTED: "Zgłoszony",
  IN_PROGRESS: "W trakcie realizacji",
  DONE: "Zakończony",
};

const SOURCE_LABEL: Record<CaseSource, string> = {
  ALLEGRO_ORDER: "Allegro - anulowanie zamówienia",
  ALLEGRO_RETURN: "Allegro - zwrot klienta",
  APP_STATUS: "Status w aplikacji",
  MIGRATION: "Dane sprzed wdrożenia",
};

const MISSING = "nieuzupełnione";

const SELECT_CLASS =
  "rounded-md border border-line bg-panel-2 px-2 py-[5px] text-[11.5px] text-text-2 outline-none transition-colors hover:border-line-2 focus:border-teal";

type ReasonFilter = "" | CaseReason | "MISSING";

export function casesQueryKey(query: CaseQuery): unknown[] {
  return ["customer-cases", query];
}

/** Data z pola `<input type="date">` jako poczatek polskiej doby w ISO (UTC). */
function dayStartIso(value: string, plusDays = 0): string | undefined {
  if (!value) return undefined;
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + plusDays);
  return date.toISOString();
}

function DateFact({ label, value }: { label: string; value: string | null }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="text-[10px] uppercase tracking-[.08em] text-text-3">{label}</span>
      <span className={`o-mono truncate text-[11px] ${value ? "text-text-2" : "text-text-3"}`}>
        {value ? formatDateTime(value) : MISSING}
      </span>
    </span>
  );
}

function CaseRow({ item }: { item: CustomerCase }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: async (update: { reason?: CaseReason | null; handling_status?: CaseHandling }) => {
      const result = await window.ordly.cases.update(item.id, update);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customer-cases"] });
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać zmiany",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-line bg-panel-2 px-[17px] py-[13px]">
      <div className="flex min-w-0 items-center gap-3">
        <MarketplaceBadge marketplace={item.marketplace} />
        <div className="min-w-0 flex-1">
          <h4 className={`truncate text-[13.5px] font-semibold ${item.buyer_login ? "" : "text-text-3"}`}>
            {item.buyer_login ?? `login ${MISSING}`}
          </h4>
          <p
            className="o-mono truncate text-[11px] text-text-3"
            title={`Numer zamówienia: ${item.order_external_id}${
              item.allegro_order_id ? ` · ID w Allegro: ${item.allegro_order_id}` : ""
            }`}
          >
            Zamówienie {item.order_external_id.slice(0, 8).toUpperCase()} · ID Allegro{" "}
            {item.allegro_order_id ? item.allegro_order_id.slice(0, 8).toUpperCase() : MISSING} ·{" "}
            {SOURCE_LABEL[item.source] ?? item.source_label}
          </p>
        </div>
        <Pill tone={item.kind === "REFUND" ? "go" : "mute"}>{item.kind_label}</Pill>
      </div>

      <div className="grid grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.2fr)_minmax(0,1.2fr)] items-end gap-3">
        <DateFact label="Złożone" value={item.order_date} />
        <DateFact label="Anulowane" value={item.cancelled_at} />
        <DateFact label="Zwrot pieniędzy" value={item.refunded_at} />
        <label className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] uppercase tracking-[.08em] text-text-3">Powód</span>
          <select
            className={SELECT_CLASS}
            value={item.reason ?? ""}
            disabled={mutation.isPending}
            onChange={(event) =>
              mutation.mutate({
                reason: event.target.value === "" ? null : (event.target.value as CaseReason),
              })
            }
            title={item.reason_detail ? `Kod powodu z Allegro: ${item.reason_detail}` : undefined}
          >
            <option value="">{MISSING}</option>
            {(Object.keys(CASE_REASON_LABEL) as CaseReason[]).map((reason) => (
              <option key={reason} value={reason}>
                {CASE_REASON_LABEL[reason]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] uppercase tracking-[.08em] text-text-3">Status obsługi</span>
          <select
            className={SELECT_CLASS}
            value={item.handling_status}
            disabled={mutation.isPending}
            onChange={(event) =>
              mutation.mutate({ handling_status: event.target.value as CaseHandling })
            }
          >
            {(Object.keys(CASE_HANDLING_LABEL) as CaseHandling[]).map((status) => (
              <option key={status} value={status}>
                {CASE_HANDLING_LABEL[status]}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

interface CustomerCasesPanelProps {
  /** Rodzaje spraw do pokazania (puste = wszystkie). */
  kinds?: CaseKind[];
  /** Status obslugi z podzakladki rodzica (puste = wszystkie). */
  handlingStatus?: CaseHandling;
  emptyTitle?: string;
}

export function CustomerCasesPanel({
  kinds,
  handlingStatus,
  emptyTitle = "Brak spraw",
}: CustomerCasesPanelProps) {
  const [reason, setReason] = React.useState<ReasonFilter>("");
  const [source, setSource] = React.useState<"" | CaseSource>("");
  const [dateFrom, setDateFrom] = React.useState("");
  const [dateTo, setDateTo] = React.useState("");

  const query: CaseQuery = {
    kind: kinds,
    handling_status: handlingStatus,
    reason: reason || undefined,
    source: source || undefined,
    date_from: dayStartIso(dateFrom),
    // "do" wlacznie z wybranym dniem.
    date_to: dayStartIso(dateTo, 1),
  };

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: casesQueryKey(query),
    queryFn: async () => {
      const result = await window.ordly.cases.list(query);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const filtersActive = Boolean(reason || source || dateFrom || dateTo);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={reason === ""} onClick={() => setReason("")}>
          Każdy powód
        </Chip>
        <Chip active={reason === "OUT_OF_STOCK"} onClick={() => setReason("OUT_OF_STOCK")}>
          Brak towaru
        </Chip>
        <Chip active={reason === "MISSING"} onClick={() => setReason("MISSING")}>
          Powód nieuzupełniony
        </Chip>
        <select
          aria-label="Powód"
          className={SELECT_CLASS}
          value={reason}
          onChange={(event) => setReason(event.target.value as ReasonFilter)}
        >
          <option value="">Powód: wszystkie</option>
          {(Object.keys(CASE_REASON_LABEL) as CaseReason[]).map((value) => (
            <option key={value} value={value}>
              {CASE_REASON_LABEL[value]}
            </option>
          ))}
          <option value="MISSING">{MISSING}</option>
        </select>
        <select
          aria-label="Źródło zdarzenia"
          className={SELECT_CLASS}
          value={source}
          onChange={(event) => setSource(event.target.value as "" | CaseSource)}
        >
          <option value="">Źródło: wszystkie</option>
          {(Object.keys(SOURCE_LABEL) as CaseSource[]).map((value) => (
            <option key={value} value={value}>
              {SOURCE_LABEL[value]}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-[11px] text-text-3">
          od
          <input
            type="date"
            className={SELECT_CLASS}
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-text-3">
          do
          <input
            type="date"
            className={SELECT_CLASS}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </label>
        {filtersActive && (
          <button
            onClick={() => {
              setReason("");
              setSource("");
              setDateFrom("");
              setDateTo("");
            }}
            className="text-[11.5px] text-text-3 transition-colors hover:text-text"
          >
            Wyczyść filtry
          </button>
        )}
      </div>

      {isError && (
        <ErrorState
          title="Nie udało się pobrać spraw"
          detail={`Pi nie odpowiedziało. ${error instanceof Error ? error.message : ""}`}
          onRetry={() => void refetch()}
        />
      )}
      {isLoading && <SkeletonRows rows={3} />}
      {!isLoading && !isError && (data ?? []).length === 0 && (
        <EmptyState
          prop="box"
          title={emptyTitle}
          description={
            filtersActive
              ? "Nic nie pasuje do filtrów - zmień je albo wyczyść."
              : "Ordlak zapisze tu każde anulowanie i zwrot pieniędzy."
          }
        />
      )}
      {(data ?? []).map((item) => (
        <CaseRow key={item.id} item={item} />
      ))}
    </div>
  );
}

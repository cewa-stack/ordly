/**
 * Zamowienia - uklad "lista + szczegoly" (`1fr 328px`, sekcja 4.3).
 *
 * Chipy filtrow i sortowanie sa REALNE (sekcja 9.1 pkt 3) - zmieniaja
 * liste, a nie tylko swoj wyglad. Zaznaczanie wielu zamowien wlacza
 * pasek akcji zbiorczych na dole listy (pkt 5).
 *
 * "Oznacz jako spakowane" i "Oznacz jako wysłane" zapisuja status
 * NAJPIERW na Allegro, potem lokalnie - jesli Allegro odmowi (np. brak
 * uprawnienia `allegro:api:orders:write`), aplikacja pokazuje blad i
 * nie klamie, ze zamowienie jest obsluzone.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckIcon, ExportIcon, SortIcon, TruckIcon } from "../icons";
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  MarketplaceBadge,
  MiniButton,
  Pill,
  SkeletonRows,
} from "../components/ui";
import { ConfirmDialog } from "../components/Modal";
import { useToast } from "../lib/toast";
import { formatCurrency, formatDateTime, formatTime, toAmount } from "../lib/format";
import {
  ORDER_FILTER_LABEL,
  fulfillmentLabel,
  fulfillmentTone,
  matchesOrderFilter,
  type OrderFilter,
} from "../lib/fulfillment";
import type { Order } from "../types/api";

type SortMode = "newest" | "amount";

interface ZamowieniaScreenProps {
  focusOrderId: string | null;
  onFocusHandled: () => void;
}

function useOrders() {
  return useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const result = await window.ordly.orders.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

/**
 * Os czasu realizacji: kropki wypelnione = wykonane, puste = oczekujace.
 * Etapy sa wyprowadzone ze statusu Allegro, a nie zmyslone - kazdy ma
 * pokrycie w danych zamowienia.
 */
function fulfillmentTimeline(order: Order): { label: string; done: boolean; time?: string }[] {
  const status = order.fulfillment_status;
  const paid = status !== null || order.status === "READY_FOR_PROCESSING";
  const packing = status === "PROCESSING" || status === "SENT" || status === "PICKED_UP";
  const sent = status === "SENT" || status === "PICKED_UP";
  return [
    { label: "Zamówienie złożone", done: true, time: formatDateTime(order.order_date) },
    { label: "Opłacone", done: paid },
    { label: "Spakowane", done: packing },
    { label: "Wysłane", done: sent },
  ];
}

function OrderDetail({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = React.useState<null | "PROCESSING" | "SENT">(null);

  const trackingQuery = useQuery({
    queryKey: ["tracking", order.external_id],
    queryFn: async () => {
      const result = await window.ordly.orders.tracking(order.external_id);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

  const fulfillmentMutation = useMutation({
    mutationFn: async (status: "PROCESSING" | "SENT") => {
      const result = await window.ordly.orders.setFulfillment(order.external_id, status);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (updated) => {
      setConfirm(null);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(
        updated.fulfillment_status === "SENT"
          ? "Oznaczono jako wysłane"
          : "Oznaczono jako spakowane",
        `${order.buyer_login} · ${formatCurrency(order.total_amount)}`
      );
    },
    onError: (error) => {
      setConfirm(null);
      toast.error(
        "Allegro nie przyjęło zmiany statusu",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  const itemsTotal = order.products.reduce(
    (sum, product) => sum + toAmount(product.total_price),
    0
  );

  return (
    <div className="flex min-h-0 flex-col gap-[18px] overflow-y-auto border-l border-line p-5">
      <div className="flex flex-col gap-1">
        <h3 className="o-section-title">{order.buyer_login}</h3>
        <div className="o-mono text-[11px] text-slate-dim">
          {order.external_id.slice(0, 8).toUpperCase()} · {formatDateTime(order.order_date)}
        </div>
      </div>

      <div className="flex flex-col gap-[9px]">
        <div className="o-eyebrow">Pozycje</div>
        {order.products.map((product) => (
          <div
            key={product.external_id}
            className="flex justify-between gap-3 border-b border-line py-[7px] text-[12.5px] text-slate"
          >
            <span className="min-w-0 flex-1 truncate text-white">{product.name}</span>
            <span className="o-mono shrink-0">
              {product.quantity} × {formatCurrency(product.unit_price)}
            </span>
          </div>
        ))}
        <div className="flex justify-between gap-3 pt-[9px] text-[12.5px] font-semibold">
          <span className="text-white">Razem</span>
          <span className="o-mono text-teal-bright">{formatCurrency(itemsTotal)}</span>
        </div>
      </div>

      <div className="flex flex-col gap-[9px]">
        <div className="o-eyebrow">Realizacja</div>
        <div className="flex flex-col">
          {fulfillmentTimeline(order).map((step, index, all) => (
            <div key={step.label} className="relative flex gap-[11px] pb-3.5 text-[12px]">
              {index < all.length - 1 && (
                <span className="absolute bottom-[-3px] left-[3px] top-[11px] w-px bg-line-strong" />
              )}
              <span
                className={`relative z-[1] mt-1 h-[7px] w-[7px] shrink-0 rounded-full ${
                  step.done
                    ? "bg-teal-bright shadow-[0_0_0_3px_var(--panel)]"
                    : "bg-panel-3 shadow-[0_0_0_3px_var(--panel),inset_0_0_0_1px_var(--line-strong)]"
                }`}
              />
              <span className={step.done ? "text-white" : "text-slate-dim"}>
                {step.label}
                {step.time && (
                  <span className="o-mono mt-0.5 block text-[10px] text-slate-dim">
                    {step.time}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      {trackingQuery.data?.tracking_number && (
        <div className="flex flex-col gap-[9px]">
          <div className="o-eyebrow">Przesyłka</div>
          <div className="flex items-center gap-2 rounded-md border border-line bg-panel-2 px-3 py-2.5">
            <TruckIcon size={15} className="text-teal-bright" />
            <span className="o-mono text-[11.5px] text-white">
              {trackingQuery.data.tracking_number}
            </span>
            <span className="ml-auto text-[11px] text-slate-dim">
              {trackingQuery.data.carrier ?? "przewoźnik nieznany"}
            </span>
          </div>
        </div>
      )}

      <div className="mt-auto flex flex-col gap-2 pt-1.5">
        <Button
          onClick={() => setConfirm("PROCESSING")}
          disabled={fulfillmentMutation.isPending || order.fulfillment_status === "PROCESSING"}
          icon={<CheckIcon size={14} />}
        >
          Oznacz jako spakowane
        </Button>
        <Button
          variant="ghost"
          onClick={() => setConfirm("SENT")}
          disabled={fulfillmentMutation.isPending || order.fulfillment_status === "SENT"}
          icon={<TruckIcon size={14} />}
        >
          Oznacz jako wysłane
        </Button>
      </div>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm === "SENT" ? "Oznaczyć jako wysłane?" : "Oznaczyć jako spakowane?"}
        message={
          confirm === "SENT"
            ? `Allegro pokaże kupującemu ${order.buyer_login}, że paczka została nadana. Tej zmiany nie da się cofnąć z poziomu ORDLY.`
            : `Allegro zmieni status zamówienia ${order.buyer_login} na "w realizacji". Kupujący zobaczy to od razu.`
        }
        confirmLabel={confirm === "SENT" ? "Oznacz jako wysłane" : "Oznacz jako spakowane"}
        pending={fulfillmentMutation.isPending}
        onConfirm={() => confirm && fulfillmentMutation.mutate(confirm)}
        onClose={() => setConfirm(null)}
      />
    </div>
  );
}

export function ZamowieniaScreen({ focusOrderId, onFocusHandled }: ZamowieniaScreenProps) {
  const { data, isLoading, isError, error, refetch } = useOrders();
  const [filter, setFilter] = React.useState<OrderFilter>("all");
  const [sort, setSort] = React.useState<SortMode>("newest");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [checked, setChecked] = React.useState<Set<string>>(new Set());
  const [bulkConfirm, setBulkConfirm] = React.useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  // Wejscie z palety polecen: przelacz filtr na "Wszystkie", zeby
  // szukane zamowienie na pewno bylo na liscie, i zaznacz je.
  React.useEffect(() => {
    if (!focusOrderId) return;
    setFilter("all");
    setSelectedId(focusOrderId);
    onFocusHandled();
  }, [focusOrderId, onFocusHandled]);

  const visible = React.useMemo(() => {
    const filtered = (data ?? []).filter((order) =>
      matchesOrderFilter(order.fulfillment_status, filter)
    );
    return [...filtered].sort((a, b) =>
      sort === "amount"
        ? toAmount(b.total_amount) - toAmount(a.total_amount)
        : new Date(b.order_date).getTime() - new Date(a.order_date).getTime()
    );
  }, [data, filter, sort]);

  const selected = visible.find((order) => order.external_id === selectedId) ?? visible[0];

  const bulkMutation = useMutation({
    mutationFn: async () => {
      const ids = [...checked];
      const failures: string[] = [];
      for (const id of ids) {
        const result = await window.ordly.orders.setFulfillment(id, "PROCESSING");
        if (!result.ok) failures.push(id);
      }
      return { total: ids.length, failures };
    },
    onSuccess: ({ total, failures }) => {
      setBulkConfirm(false);
      setChecked(new Set());
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      if (failures.length === 0) {
        toast.success(
          "Oznaczono jako spakowane",
          `${total} ${total === 1 ? "zamówienie" : "zamówień"}`
        );
      } else {
        toast.error(
          `${failures.length} z ${total} nie przeszło`,
          "Allegro odrzuciło część zmian - odśwież listę i spróbuj ponownie."
        );
      }
    },
  });

  function toggleChecked(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function exportCsv() {
    const header = "numer;kanal;kupujacy;kwota;status;data";
    const rows = visible.map((order) =>
      [
        order.external_id,
        order.marketplace,
        order.buyer_login,
        toAmount(order.total_amount).toFixed(2).replace(".", ","),
        fulfillmentLabel(order.fulfillment_status),
        order.order_date,
      ].join(";")
    );
    // Separator ';' i BOM - inaczej Excel w polskiej lokalizacji wrzuca
    // caly wiersz do jednej kolumny i psuje polskie znaki.
    const blob = new Blob(["﻿" + [header, ...rows].join("\r\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ordly-zamowienia-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success("Wyeksportowano listę", `${visible.length} pozycji do pliku CSV`);
  }

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać zamówień"
        detail={`Pi nie odpowiedziało na zapytanie o listę zamówień. ${
          error instanceof Error ? error.message : ""
        }`}
        onRetry={() => void refetch()}
      />
    );
  }

  // `minmax(0,1fr)` zamiast `1fr` jest OBOWIAZKOWE: `1fr` to w praktyce
  // `minmax(auto, 1fr)`, wiec bez tego szeroka zawartosc wiersza rozpycha
  // pierwsza kolumne i zgniata panel szczegolow do zera. Ponizej 1100 px
  // uklad schodzi do jednej kolumny (kryterium odbioru 10.2).
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_328px] max-[1100px]:grid-cols-1">
      <div className="flex min-h-0 min-w-0 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-[22px] py-[11px]">
          {(["all", "pack", "new", "sent"] as const).map((option) => (
            <Chip key={option} active={filter === option} onClick={() => setFilter(option)}>
              {ORDER_FILTER_LABEL[option]}
            </Chip>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <MiniButton
              icon={<SortIcon size={13} />}
              onClick={() => setSort((prev) => (prev === "newest" ? "amount" : "newest"))}
            >
              {sort === "newest" ? "Najnowsze" : "Kwota malejąco"}
            </MiniButton>
            <MiniButton icon={<ExportIcon size={13} />} onClick={exportCsv}>
              Eksport
            </MiniButton>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading && <SkeletonRows rows={6} />}
          {!isLoading && visible.length === 0 && (
            <EmptyState
              pose={filter === "all" ? "orders" : "think"}
              title={filter === "all" ? "Brak zamówień" : "Nic w tym filtrze"}
              description={
                filter === "all"
                  ? "Gdy tylko wpadnie nowe zamówienie, Ordi je tu położy."
                  : "Zmień filtr albo zsynchronizuj kanały, żeby zobaczyć więcej."
              }
            />
          )}
          {visible.map((order) => {
            const isSelected = selected?.external_id === order.external_id;
            return (
              <div
                key={order.external_id}
                className={`relative flex w-full items-center gap-3 border-b border-line px-[22px] py-[12.5px] transition-colors duration-150 ease-ordly ${
                  isSelected ? "bg-teal-dim" : "hover:bg-panel-2"
                }`}
              >
                {isSelected && (
                  <span className="absolute bottom-0 left-0 top-0 w-[3px] bg-teal-bright" />
                )}
                <input
                  type="checkbox"
                  checked={checked.has(order.external_id)}
                  onChange={() => toggleChecked(order.external_id)}
                  aria-label={`Zaznacz zamówienie ${order.buyer_login}`}
                  className="h-3.5 w-3.5 shrink-0 accent-[#5FD9CC]"
                />
                <button
                  onClick={() => setSelectedId(order.external_id)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <MarketplaceBadge marketplace={order.marketplace} />
                  <span className="o-mono w-20 shrink-0 text-[11.5px] text-slate-dim">
                    {formatTime(order.order_date)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-white">
                    {order.buyer_login}
                  </span>
                  <span className="o-mono w-[78px] shrink-0 text-right text-[12.5px] text-slate">
                    {formatCurrency(order.total_amount)}
                  </span>
                  <Pill tone={fulfillmentTone(order.fulfillment_status)}>
                    {fulfillmentLabel(order.fulfillment_status)}
                  </Pill>
                </button>
              </div>
            );
          })}
        </div>

        {checked.size > 0 && (
          <div className="flex shrink-0 items-center gap-3 border-t border-line bg-panel-2 px-[22px] py-3">
            <span className="o-mono text-[11.5px] text-slate">Zaznaczono {checked.size}</span>
            <button
              onClick={() => setChecked(new Set())}
              className="text-[11.5px] text-slate-dim hover:text-white"
            >
              Wyczyść
            </button>
            <div className="ml-auto flex gap-2">
              <MiniButton icon={<ExportIcon size={13} />} onClick={exportCsv}>
                Eksportuj widok
              </MiniButton>
              <Button
                className="!px-3 !py-1.5 !text-[11.5px]"
                onClick={() => setBulkConfirm(true)}
                disabled={bulkMutation.isPending}
                icon={<CheckIcon size={13} />}
              >
                Oznacz jako spakowane
              </Button>
            </div>
          </div>
        )}
      </div>

      {selected ? (
        <OrderDetail key={selected.external_id} order={selected} />
      ) : (
        <div className="flex items-center justify-center border-l border-line p-5 text-center text-[12.5px] text-slate-dim">
          Wybierz zamówienie z listy, żeby zobaczyć szczegóły.
        </div>
      )}

      <ConfirmDialog
        open={bulkConfirm}
        title={`Oznaczyć ${checked.size} ${checked.size === 1 ? "zamówienie" : "zamówień"}?`}
        message='Allegro zmieni status wszystkich zaznaczonych zamówień na "w realizacji". Kupujący zobaczą to od razu, a zmiany nie da się cofnąć z poziomu ORDLY.'
        confirmLabel="Oznacz jako spakowane"
        pending={bulkMutation.isPending}
        onConfirm={() => bulkMutation.mutate()}
        onClose={() => setBulkConfirm(false)}
      />
    </div>
  );
}

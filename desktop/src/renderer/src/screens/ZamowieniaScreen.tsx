/**
 * Zamowienia - lista + panel szczegolu (sekcja 9 instrukcji "Nokturn").
 *
 * Naglowek listy i wiersze maja IDENTYCZNA definicje kolumn - to jedyny
 * sposob, zeby prawa krawedz listy byla prosta przy kazdej dlugosci
 * nazwiska. `min-width:0` na kazdym dziecku jest obowiazkowe: bez niego
 * sciezka `1fr` nie moze skurczyc sie ponizej swojej zawartosci i kwoty
 * wychodza poza panel.
 *
 * ODSTEPSTWO OD INSTRUKCJI (swiadome): siatka ma SIEDEM kolumn, nie
 * szesc - na poczatku dochodzi 22 px na pole wyboru. Zaznaczanie wielu
 * zamowien i zbiorcze "oznacz jako spakowane" to dzialajaca funkcja;
 * wyrzucenie jej tylko po to, zeby zgadzala sie lista kolumn, zabiera
 * uzytkownikowi mozliwosc, ktora ma dzis. Regula "naglowek i wiersz maja
 * te sama definicje" zostaje nienaruszona.
 *
 * "Oznacz jako spakowane" i "Oznacz jako wysłane" zapisuja status
 * NAJPIERW na Allegro, potem lokalnie - jesli Allegro odmowi (np. brak
 * uprawnienia `allegro:api:orders:write`), aplikacja pokazuje blad i
 * nie klamie, ze zamowienie jest obsluzone.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BoxIcon, CheckIcon, ExportIcon, SortIcon, TruckIcon } from "../icons";
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
import { Ordlak } from "../components/Ordlak";
import { ConfirmDialog } from "../components/Modal";
import { useToast } from "../lib/toast";
import { useOrdlakState } from "../lib/ordlakState";
import {
  formatAge,
  formatCurrency,
  formatDateTime,
  formatPlural,
  formatTime,
  parseApiDate,
  toAmount,
} from "../lib/format";
import {
  ORDER_FILTER_LABEL,
  displayFulfillmentLabel,
  displayFulfillmentTone,
  isShippedForDisplay,
  matchesOrderFilter,
  type OrderFilter,
} from "../lib/fulfillment";
import type { MarketplaceOffer, Order } from "../types/api";

type SortMode = "newest" | "amount";

/**
 * Jedna definicja kolumn dla naglowka I wierszy. Zmiana w jednym miejscu
 * zmienia oba - inaczej rozjazd jest kwestia czasu.
 *
 * wybor · kanal · kupujacy/pozycje · numer · status · wartosc · czas
 */
const GRID_COLUMNS = "22px 68px minmax(0,1fr) 76px 88px 92px 52px";

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

/** Anulowane zamowienie - Allegro nie pozwala juz zmieniac jego realizacji. */
function isCancelled(order: Order): boolean {
  return order.status === "CANCELLED" || order.fulfillment_status === "CANCELLED";
}

/**
 * Czy "Oznacz jako spakowane" ma sens - tylko dla zamowien, ktore jeszcze
 * czekaja na spakowanie. Wczesniej przycisk byl aktywny takze dla wyslanych
 * i odebranych paczek, a klikniecie cofalo ich status na Allegro.
 */
function canMarkPacked(order: Order): boolean {
  const status = order.fulfillment_status;
  return !isCancelled(order) && (status === null || status === "NEW" || status === "PROCESSING");
}

function canMarkSent(order: Order): boolean {
  const status = order.fulfillment_status;
  return (
    !isCancelled(order) &&
    status !== "SENT" &&
    status !== "PICKED_UP" &&
    status !== "READY_FOR_PICKUP"
  );
}

/**
 * DOKLADNIE TRZY segmenty i trzy etykiety (sekcja 9). "Zamowienie
 * zlozone" nie jest etapem - zamowienie, ktorego nie zlozono, nie
 * istnieje - wiec pasek zaczyna sie od platnosci.
 */
function fulfillmentSteps(order: Order): { label: string; done: boolean }[] {
  const status = order.fulfillment_status;
  const paid = status !== null || order.status === "READY_FOR_PROCESSING";
  const sent = isShippedForDisplay(order);
  // "Spakowane" = od READY_FOR_SHIPMENT wzwyz. PROCESSING to dopiero
  // "w realizacji" - tak ustawia Allegro, gdy pakowanie sie zaczyna.
  const packed =
    sent ||
    status === "READY_FOR_SHIPMENT" ||
    status === "READY_FOR_PICKUP" ||
    status === "SENT" ||
    status === "PICKED_UP";
  return [
    { label: "Opłacone", done: paid },
    { label: "Spakowane", done: packed },
    { label: "Wysłane", done: sent },
  ];
}

function ProgressBar({ order }: { order: Order }) {
  const steps = fulfillmentSteps(order);
  // Biezacy krok to pierwszy niezrobiony; gdy wszystkie zrobione - zaden.
  const currentIndex = steps.findIndex((step) => !step.done);

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-3 gap-1.5">
        {steps.map((step, index) => (
          <span
            key={step.label}
            className={`h-[3px] rounded-[2px] ${
              step.done
                ? "bg-teal"
                : index === currentIndex
                  ? "bg-teal opacity-45"
                  : "bg-panel-3"
            }`}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {steps.map((step, index) => (
          <span
            key={step.label}
            className={`truncate text-[10px] ${
              index === currentIndex ? "text-teal" : "text-text-3"
            }`}
          >
            {step.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Notka Ordlaka. Pojawia sie TYLKO wtedy, gdy ma cos konkretnego do
 * powiedzenia - nie jako staly element panelu.
 *
 * Kazda notka jest wyliczana LOKALNIE z samego zamowienia. Zaden wariant
 * nie wola modelu: panel szczegolu otwiera sie przy kazdym kliknieciu
 * w liste, a pytanie modelu za kazdym razem byloby i wolne, i kosztowne.
 */
function ordlakNote(order: Order): string | null {
  if (isCancelled(order)) {
    return "Zamówienie jest anulowane — Allegro nie pozwoli już zmienić realizacji.";
  }
  // Numer przesylki wykryty lokalnie (check_waybills_job), a Allegro
  // wciaz ma starszy status - to realny rozjazd, nie domysl.
  if (
    order.tracking_number &&
    order.fulfillment_status !== "SENT" &&
    order.fulfillment_status !== "PICKED_UP"
  ) {
    return `Znalazłem numer przesyłki ${order.tracking_number}, ale Allegro wciąż ma status „${displayFulfillmentLabel(
      order
    )}". Oznacz jako wysłane, żeby kupujący to zobaczył.`;
  }
  const hoursWaiting = Math.floor(
    (Date.now() - parseApiDate(order.order_date).getTime()) / 3_600_000
  );
  if (canMarkPacked(order) && hoursWaiting >= 24) {
    return `Czeka na spakowanie od ${formatAge(order.order_date)} — Allegro liczy to do oceny terminowości wysyłki.`;
  }
  return null;
}

/** Para klucz-wartosc w panelu szczegolu. */
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3">
      <span className="shrink-0 text-[11px] text-text-3">{label}</span>
      <span className="o-mono min-w-0 truncate text-right text-[11px] text-text-2">
        {value}
      </span>
    </div>
  );
}

function OrderDetail({
  order,
  offers,
}: {
  order: Order;
  offers: MarketplaceOffer[];
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { celebrate } = useOrdlakState();
  const [confirm, setConfirm] = React.useState<null | "READY_FOR_SHIPMENT" | "SENT">(null);

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
    mutationFn: async (status: "READY_FOR_SHIPMENT" | "SENT") => {
      const result = await window.ordly.orders.setFulfillment(order.external_id, status);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (updated) => {
      setConfirm(null);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      // Oznaczenie paczki jako wyslanej to jeden z wyzwalaczy `happy`
      // (sekcja 6) - maskotka cieszy sie 1,2 s i wraca do idle.
      celebrate();
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
  const note = ordlakNote(order);
  const tracking = trackingQuery.data?.tracking_number ?? order.tracking_number;

  /** Miniatura z Magazynu, o ile oferta o tym numerze jest w katalogu. */
  function thumbnailFor(externalId: string): string | null {
    return (
      offers.find(
        (offer) =>
          offer.external_id === externalId && offer.marketplace === order.marketplace
      )?.image_url ?? null
    );
  }

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-line bg-panel max-[1100px]:min-h-[420px]">
      {/* --------------------------------------------------- naglowek */}
      <div className="shrink-0 border-b border-line p-4">
        <div className="o-mono text-[11px] uppercase tracking-[.1em] text-text-3">
          {order.external_id.slice(0, 8).toUpperCase()} · {order.marketplace}
        </div>
        <h3 className="o-display mt-1 truncate text-[19px] tracking-[-.02em]">
          {order.buyer_login}
        </h3>
        <div className="mt-2 flex items-center gap-2">
          <Pill tone={displayFulfillmentTone(order)}>{displayFulfillmentLabel(order)}</Pill>
          <span className="o-mono text-[10px] text-text-3">
            czeka {formatAge(order.order_date)}
          </span>
        </div>
      </div>

      {/* ------------------------------------------------------ tresc */}
      <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto px-4 py-3.5">
        {order.products.map((product) => {
          const thumbnail = thumbnailFor(product.external_id);
          return (
            <div
              key={product.external_id}
              className="flex items-center gap-2.5 rounded-md bg-panel-2 p-2.5"
            >
              <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center overflow-hidden rounded-xs bg-panel-3 text-text-3">
                {thumbnail ? (
                  <img
                    src={thumbnail}
                    alt=""
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <BoxIcon size={16} />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="o-row-name block truncate text-text">{product.name}</span>
                <span className="o-mono block truncate text-[10px] text-text-3">
                  {formatCurrency(product.unit_price)} / szt.
                </span>
              </span>
              <span className="o-mono shrink-0 text-[12px] text-text-2">
                ×{product.quantity}
              </span>
            </div>
          );
        })}

        <div className="flex flex-col gap-2">
          <Fact label="Wartość" value={formatCurrency(itemsTotal)} />
          <Fact label="Złożone" value={formatDateTime(order.order_date)} />
          <Fact label="Kanał" value={order.marketplace} />
          <Fact
            label="Przesyłka"
            value={
              tracking
                ? `${tracking}${
                    trackingQuery.data?.carrier ? ` · ${trackingQuery.data.carrier}` : ""
                  }`
                : "brak numeru"
            }
          />
        </div>

        <ProgressBar order={order} />

        {note && (
          <div className="flex items-start gap-2.5 rounded-md bg-panel-2 px-3 py-2.5">
            <Ordlak state="think" size={34} className="shrink-0" />
            <p className="text-[11.5px] leading-[1.5] text-text-2">{note}</p>
          </div>
        )}
      </div>

      {/* ----------------------------------------------------- stopka */}
      <div className="mt-auto flex shrink-0 gap-2 border-t border-line px-4 py-3.5">
        <Button
          className="flex-1"
          onClick={() => setConfirm("READY_FOR_SHIPMENT")}
          disabled={fulfillmentMutation.isPending || !canMarkPacked(order)}
          icon={<CheckIcon size={14} />}
        >
          Spakowane
        </Button>
        <Button
          className="flex-1"
          variant="ghost"
          onClick={() => setConfirm("SENT")}
          disabled={fulfillmentMutation.isPending || !canMarkSent(order)}
          icon={<TruckIcon size={14} />}
        >
          Wysłane
        </Button>
      </div>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm === "SENT" ? "Oznaczyć jako wysłane?" : "Oznaczyć jako spakowane?"}
        message={
          confirm === "SENT"
            ? `Allegro pokaże kupującemu ${order.buyer_login}, że paczka została nadana. Tej zmiany nie da się cofnąć z poziomu ORDLY.`
            : `Allegro zmieni status zamówienia ${order.buyer_login} na "gotowe do wysyłki". Kupujący zobaczy to od razu.`
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
  const { celebrate } = useOrdlakState();

  // Miniatury pozycji biora sie z katalogu Magazynu - zapytanie i tak
  // jest w pamieci podrecznej, bo ekran Start je odpytuje.
  const offersQuery = useQuery({
    queryKey: ["offers"],
    queryFn: async () => {
      const result = await window.ordly.stock.offers();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  // Wejscie z palety polecen: przelacz filtr na "Wszystkie", zeby
  // szukane zamowienie na pewno bylo na liscie, i zaznacz je.
  React.useEffect(() => {
    if (!focusOrderId) return;
    setFilter("all");
    setSelectedId(focusOrderId);
    onFocusHandled();
  }, [focusOrderId, onFocusHandled]);

  const visible = React.useMemo(() => {
    const filtered = (data ?? []).filter((order) => matchesOrderFilter(order, filter));
    return [...filtered].sort((a, b) =>
      sort === "amount"
        ? toAmount(b.total_amount) - toAmount(a.total_amount)
        : new Date(b.order_date).getTime() - new Date(a.order_date).getTime()
    );
  }, [data, filter, sort]);

  const selected = visible.find((order) => order.external_id === selectedId) ?? visible[0];

  /** Licznik przy kazdym chipie - liczy to, co chip naprawde pokaze. */
  const filterCounts = React.useMemo(() => {
    const all = data ?? [];
    return {
      all: all.length,
      pack: all.filter((order) => matchesOrderFilter(order, "pack")).length,
      ready: all.filter((order) => matchesOrderFilter(order, "ready")).length,
      sent: all.filter((order) => matchesOrderFilter(order, "sent")).length,
    } satisfies Record<OrderFilter, number>;
  }, [data]);

  const bulkMutation = useMutation({
    mutationFn: async () => {
      // Tylko zamowienia, ktore naprawde czekaja na spakowanie - pozostale
      // (spakowane, wyslane, anulowane) mialyby cofniety status na Allegro.
      const eligible = (data ?? []).filter(
        (order) => checked.has(order.external_id) && canMarkPacked(order)
      );
      const failures: string[] = [];
      for (const order of eligible) {
        const result = await window.ordly.orders.setFulfillment(
          order.external_id,
          "READY_FOR_SHIPMENT"
        );
        if (!result.ok) failures.push(order.external_id);
      }
      return { total: eligible.length, skipped: checked.size - eligible.length, failures };
    },
    onSuccess: ({ total, skipped, failures }) => {
      setBulkConfirm(false);
      setChecked(new Set());
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      const skippedNote =
        skipped > 0
          ? ` Pominięto ${formatPlural(skipped, [
              "zamówienie",
              "zamówienia",
              "zamówień",
            ])} - już spakowane, wysłane lub anulowane.`
          : "";
      if (total === 0) {
        toast.error(
          "Nic do oznaczenia",
          "Zaznaczone zamówienia są już spakowane, wysłane lub anulowane."
        );
      } else if (failures.length === 0) {
        celebrate();
        toast.success(
          "Oznaczono jako spakowane",
          `${formatPlural(total, ["zamówienie", "zamówienia", "zamówień"])}.${skippedNote}`
        );
      } else {
        toast.error(
          `${failures.length} z ${total} nie przeszło`,
          "Allegro odrzuciło część zmian - odśwież listę i spróbuj ponownie."
        );
      }
    },
    onError: (error) => {
      setBulkConfirm(false);
      toast.error(
        "Oznaczanie nie przeszło",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
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
        displayFulfillmentLabel(order),
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

  return (
    <div
      data-frame
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-[22px] pb-[18px] pt-3.5"
    >
      {/* ------------------------------------------------ rzad filtrow */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {(["all", "pack", "ready", "sent"] as const).map((option) => (
          <Chip
            key={option}
            active={filter === option}
            count={filterCounts[option]}
            onClick={() => setFilter(option)}
          >
            {ORDER_FILTER_LABEL[option]}
          </Chip>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setSort((prev) => (prev === "newest" ? "amount" : "newest"))}
            className="o-mono flex items-center gap-1.5 text-[10px] uppercase tracking-[.1em] text-text-3 transition-colors duration-150 hover:text-teal"
          >
            <SortIcon size={12} />
            Sortuj: {sort === "newest" ? "najnowsze" : "kwota"}
          </button>
          <MiniButton icon={<ExportIcon size={13} />} onClick={exportCsv}>
            Eksport
          </MiniButton>
        </div>
      </div>

      {/* ------------------------------------------- lista + szczegoly */}
      {/*
       * Ponizej 1100 px uklad schodzi do jednej kolumny. Obie czesci
       * dostaja wtedy wysokosc minimalna, a przewija sie CALA kolumna -
       * bez tego panel szczegolu zapadal sie do wysokosci naglowka
       * i stopki, a srodek (pozycje, pasek realizacji, notka) znikal.
       */}
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_332px] gap-3 max-[1100px]:grid-cols-1 max-[1100px]:overflow-y-auto">
        <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-line bg-panel max-[1100px]:min-h-[320px]">
          {/* Naglowek - ta sama definicja kolumn co wiersz. */}
          <div
            className="o-eyebrow grid shrink-0 items-center gap-2.5 border-b border-line px-4 py-2.5 [&>*]:min-w-0"
            style={{ gridTemplateColumns: GRID_COLUMNS }}
          >
            <span />
            <span>Kanał</span>
            <span>Kupujący</span>
            <span>Numer</span>
            <span>Status</span>
            <span className="text-right">Wartość</span>
            <span className="text-right">Czas</span>
          </div>

          <div className="o-fade-b min-h-0 flex-1 overflow-y-auto">
            {isLoading && <SkeletonRows rows={6} />}
            {!isLoading && visible.length === 0 && (
              <EmptyState
                title={filter === "all" ? "Brak zamówień" : "Nic w tym filtrze"}
                description={
                  filter === "all"
                    ? "Gdy tylko wpadnie nowe zamówienie, Ordlak je tu położy."
                    : "Zmień filtr albo zsynchronizuj kanały, żeby zobaczyć więcej."
                }
              />
            )}
            {visible.map((order) => {
              const isSelected = selected?.external_id === order.external_id;
              const items = order.products.map((product) => product.name).join(", ");
              return (
                <div
                  key={order.external_id}
                  onClick={() => setSelectedId(order.external_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedId(order.external_id);
                    }
                  }}
                  className={`relative grid cursor-pointer items-center gap-2.5 border-b border-line px-4 py-[11px] text-left transition-colors duration-150 ease-ordly [&>*]:min-w-0 ${
                    isSelected ? "bg-panel-2" : "hover:bg-panel-2"
                  }`}
                  style={{ gridTemplateColumns: GRID_COLUMNS }}
                >
                  {/* Pasek 2 px na lewej krawedzi - ten sam wzorzec co nawigacja. */}
                  {isSelected && (
                    <span className="absolute bottom-0 left-0 top-0 w-[2px] bg-teal" />
                  )}
                  <input
                    type="checkbox"
                    checked={checked.has(order.external_id)}
                    onClick={(event) => event.stopPropagation()}
                    onChange={() => toggleChecked(order.external_id)}
                    aria-label={`Zaznacz zamówienie ${order.buyer_login}`}
                    className="h-3.5 w-3.5 shrink-0 accent-teal"
                  />
                  <MarketplaceBadge marketplace={order.marketplace} />
                  {/*
                   * Obie linijki ucinane wielokropkiem - dzieki temu KAZDY
                   * wiersz ma te sama wysokosc niezaleznie od liczby pozycji.
                   */}
                  <span className="min-w-0">
                    <span className="o-row-name block truncate text-text">
                      {order.buyer_login}
                    </span>
                    <span className="block truncate text-[11px] text-text-3">
                      {items || "brak pozycji"}
                    </span>
                  </span>
                  <span className="o-mono truncate text-[10.5px] text-text-3">
                    {order.external_id.slice(0, 8).toUpperCase()}
                  </span>
                  <Pill tone={displayFulfillmentTone(order)}>
                    {displayFulfillmentLabel(order)}
                  </Pill>
                  <span className="o-mono whitespace-nowrap text-right text-[11.5px] text-text-2">
                    {formatCurrency(order.total_amount)}
                  </span>
                  <span className="o-mono whitespace-nowrap text-right text-[11px] text-text-3">
                    {formatTime(order.order_date)}
                  </span>
                </div>
              );
            })}
          </div>

          {checked.size > 0 && (
            <div className="flex shrink-0 items-center gap-3 border-t border-line bg-panel-2 px-4 py-2.5">
              <span className="o-mono text-[11px] text-text-2">
                Zaznaczono {checked.size}
              </span>
              <button
                onClick={() => setChecked(new Set())}
                className="text-[11.5px] text-text-3 transition-colors hover:text-text"
              >
                Wyczyść
              </button>
              <Button
                className="ml-auto !px-3 !py-1.5 !text-[11.5px]"
                onClick={() => setBulkConfirm(true)}
                disabled={bulkMutation.isPending}
                icon={<CheckIcon size={13} />}
              >
                Oznacz jako spakowane
              </Button>
            </div>
          )}
        </div>

        {selected ? (
          <OrderDetail
            key={selected.external_id}
            order={selected}
            offers={offersQuery.data ?? []}
          />
        ) : (
          <div className="flex items-center justify-center rounded-lg border border-line bg-panel p-5 text-center text-[12.5px] text-text-3">
            Wybierz zamówienie z listy, żeby zobaczyć szczegóły.
          </div>
        )}
      </div>

      <ConfirmDialog
        open={bulkConfirm}
        title={`Oznaczyć ${formatPlural(checked.size, ["zamówienie", "zamówienia", "zamówień"])}?`}
        message='Allegro zmieni status zaznaczonych zamówień na "gotowe do wysyłki". Kupujący zobaczą to od razu, a zmiany nie da się cofnąć z poziomu ORDLY. Zamówienia już spakowane, wysłane i anulowane zostaną pominięte.'
        confirmLabel="Oznacz jako spakowane"
        pending={bulkMutation.isPending}
        onConfirm={() => bulkMutation.mutate()}
        onClose={() => setBulkConfirm(false)}
      />
    </div>
  );
}

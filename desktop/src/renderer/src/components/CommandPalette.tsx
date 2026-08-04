/**
 * Paleta polecen (Ctrl+K) wg sekcji 4.5 i 9.1 pkt 4.
 *
 * Paleta nie tylko nawiguje - realnie SZUKA: po numerze zamowienia,
 * nazwie kupujacego, SKU i nazwie produktu, i otwiera konkretny rekord.
 * Zamowienia leca do `/api/v1/orders/search` na Pi, produkty sa
 * filtrowane po stronie aplikacji z juz pobranej listy magazynu.
 *
 * Zadnej akcji bez pokrycia w backendzie - patrz
 * [[feedback-no-phantom-features]].
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BoxIcon, GearIcon, GridIcon, RefreshIcon, SearchIcon } from "../icons";
import { BACKSTAGE_NAV, MAIN_NAV, type ViewId } from "./Sidebar";
import { useSync } from "../lib/sync";
import { formatCurrency } from "../lib/format";

export type PaletteTarget =
  | { kind: "view"; view: ViewId }
  | { kind: "order"; externalId: string }
  | { kind: "product"; sku: string };

interface PaletteEntry {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  target: PaletteTarget | "sync";
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelect: (target: PaletteTarget) => void;
}

const SEARCH_DEBOUNCE_MS = 220;

export function CommandPalette({ open, onClose, onSelect }: CommandPaletteProps) {
  const [query, setQuery] = React.useState("");
  const [cursor, setCursor] = React.useState(0);
  const [debounced, setDebounced] = React.useState("");
  const listRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const { sync } = useSync();

  React.useEffect(() => {
    if (!open) {
      setQuery("");
      setCursor(0);
      return;
    }
    inputRef.current?.focus();
  }, [open]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const ordersQuery = useQuery({
    queryKey: ["palette-orders", debounced],
    enabled: open && debounced.length >= 2,
    queryFn: async () => {
      const result = await window.ordly.orders.search(debounced);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const stockQuery = useQuery({
    queryKey: ["stock"],
    enabled: open,
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const entries = React.useMemo<PaletteEntry[]>(() => {
    const needle = debounced.toLowerCase();

    const screens: PaletteEntry[] = [
      ...MAIN_NAV,
      ...BACKSTAGE_NAV,
      { id: "ustawienia" as ViewId, label: "Ustawienia", icon: <GearIcon /> },
    ]
      .map((item) => ({
        id: `view:${item.id}`,
        group: "Ekrany",
        label: item.label,
        icon: item.icon,
        target: { kind: "view" as const, view: item.id as ViewId },
      }))
      .filter((entry) => needle === "" || entry.label.toLowerCase().includes(needle));

    const orders: PaletteEntry[] = (ordersQuery.data ?? []).slice(0, 6).map((order) => ({
      id: `order:${order.external_id}`,
      group: "Zamówienia",
      label: order.buyer_login,
      hint: formatCurrency(order.total_amount),
      icon: <BoxIcon />,
      target: { kind: "order", externalId: order.external_id },
    }));

    const products: PaletteEntry[] =
      needle.length >= 2
        ? (stockQuery.data ?? [])
            .filter(
              (item) =>
                item.sku.toLowerCase().includes(needle) ||
                item.name.toLowerCase().includes(needle)
            )
            .slice(0, 6)
            .map((item) => ({
              id: `product:${item.sku}`,
              group: "Produkty",
              label: item.name,
              hint: item.sku,
              icon: <GridIcon />,
              target: { kind: "product" as const, sku: item.sku },
            }))
        : [];

    const actions: PaletteEntry[] = (
      [
        {
          id: "action:sync",
          group: "Działania",
          label: "Synchronizuj z marketplace",
          hint: "Ctrl R",
          icon: <RefreshIcon />,
          target: "sync" as const,
        },
      ] satisfies PaletteEntry[]
    ).filter((entry) => needle === "" || entry.label.toLowerCase().includes(needle));

    return [...screens, ...orders, ...products, ...actions];
  }, [debounced, ordersQuery.data, stockQuery.data]);

  React.useEffect(() => {
    setCursor(0);
  }, [entries.length]);

  const commit = React.useCallback(
    (entry: PaletteEntry | undefined) => {
      if (!entry) return;
      onClose();
      if (entry.target === "sync") {
        sync();
        return;
      }
      onSelect(entry.target);
    },
    [onClose, onSelect, sync]
  );

  React.useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setCursor((prev) => (entries.length === 0 ? 0 : (prev + 1) % entries.length));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setCursor((prev) =>
          entries.length === 0 ? 0 : (prev - 1 + entries.length) % entries.length
        );
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        commit(entries[cursor]);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, entries, cursor, commit, onClose]);

  React.useEffect(() => {
    listRef.current
      ?.querySelector('[data-cursor="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  if (!open) return null;

  let lastGroup = "";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[14vh]"
      style={{ background: "rgba(4,7,6,.72)", backdropFilter: "blur(7px)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Paleta poleceń"
    >
      <div
        className="animate-cmd-in w-[min(540px,92vw)] overflow-hidden rounded-lg border border-line-strong bg-panel shadow-palette"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-[11px] border-b border-line px-[17px] py-[15px]">
          <SearchIcon size={16} className="text-slate-dim" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Szukaj zamówienia, produktu lub ekranu…"
            className="flex-1 bg-transparent text-[14.5px] text-white outline-none placeholder:text-slate-dim"
          />
        </div>

        <div ref={listRef} className="max-h-[320px] overflow-y-auto p-[7px]">
          {entries.length === 0 ? (
            <p className="px-4 py-7 text-center text-[12.5px] text-slate-dim">
              Nic nie pasuje do «{query}»
            </p>
          ) : (
            entries.map((entry, index) => {
              const showGroup = entry.group !== lastGroup;
              lastGroup = entry.group;
              return (
                <React.Fragment key={entry.id}>
                  {showGroup && (
                    <div className="o-mono px-2.5 pb-[5px] pt-2.5 text-[9.5px] uppercase tracking-[.12em] text-slate-dim">
                      {entry.group}
                    </div>
                  )}
                  <button
                    data-cursor={index === cursor}
                    onMouseEnter={() => setCursor(index)}
                    onClick={() => commit(entry)}
                    className={`flex w-full items-center gap-[11px] rounded-[9px] px-2.5 py-[9.5px] text-left text-[13.5px] transition-colors duration-100 ${
                      index === cursor ? "bg-teal-dim text-teal-bright" : "text-slate"
                    }`}
                  >
                    <span className="opacity-80">{entry.icon}</span>
                    <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                    {entry.hint && (
                      <span className="o-mono shrink-0 text-[9.5px] text-slate-dim">
                        {entry.hint}
                      </span>
                    )}
                  </button>
                </React.Fragment>
              );
            })
          )}
        </div>

        <div className="flex items-center gap-3.5 border-t border-line px-4 py-2.5 text-[10.5px] text-slate-dim">
          <span className="flex items-center gap-1.5">
            <Kbd>↑</Kbd>
            <Kbd>↓</Kbd> nawigacja
          </span>
          <span className="flex items-center gap-1.5">
            <Kbd>↵</Kbd> otwórz
          </span>
          <span className="flex items-center gap-1.5">
            <Kbd>Esc</Kbd> zamknij
          </span>
          <span className="ml-auto">Ordi indeksuje przy każdej synchronizacji</span>
        </div>
      </div>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span className="o-mono rounded-[5px] border border-line-strong bg-ink-raised px-1.5 py-0.5 text-[10px] text-slate-dim">
      {children}
    </span>
  );
}

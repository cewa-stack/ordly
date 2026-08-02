/**
 * Paleta poleceń (Ctrl/Cmd+K) - szybka nawigacja + realne szybkie akcje.
 * Celowo NIE ma akcji bez pokrycia w backendzie (żadnego "utwórz
 * zamówienie" - ORDLY nigdy nie tworzy zamówień ręcznie, tylko z
 * synchronizacji Allegro) - patrz [[feedback-no-phantom-features]].
 * Obie szybkie akcje (synchronizacja, import CSV) są bezkontekstowe,
 * więc mają sens z dowolnego ekranu.
 */
import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ViewId } from "./Sidebar";
import { useToast } from "../lib/toast";
import {
  BarsIcon,
  BoxIcon,
  ChatIcon,
  MailIcon,
  ReceiptIcon,
  RefreshIcon,
  SearchIcon,
  TagIcon,
  UndoIcon,
  WarehouseIcon,
} from "../icons";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (view: ViewId) => void;
}

interface PaletteItem {
  id: string;
  section: "Szybkie akcje" | "Nawigacja";
  label: string;
  icon: React.ReactNode;
  keywords?: string;
  run: () => void;
}

const NAV_ITEMS: { id: ViewId; label: string; icon: React.ReactNode }[] = [
  { id: "magazyn", label: "Magazyn", icon: <BoxIcon size={15} /> },
  { id: "zamowienia", label: "Zamówienia", icon: <ReceiptIcon size={15} /> },
  { id: "zwroty", label: "Zwroty i anulowane", icon: <UndoIcon size={15} /> },
  { id: "dyskusje", label: "Dyskusje", icon: <ChatIcon size={15} /> },
  { id: "hurtownia", label: "Hurtownia", icon: <WarehouseIcon size={15} /> },
  { id: "skrzynka", label: "Skrzynka", icon: <MailIcon size={15} /> },
  { id: "olx", label: "OLX", icon: <TagIcon size={15} /> },
  { id: "statystyki", label: "Statystyki", icon: <BarsIcon size={15} /> },
];

export function CommandPalette({ open, onClose, onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = React.useState("");
  const [activeIndex, setActiveIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const toast = useToast();
  const queryClient = useQueryClient();

  const syncMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.orders.sync();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      toast.success(
        result.new_orders_count > 0
          ? `${result.new_orders_count} nowych zamówień zsynchronizowanych`
          : "Zsynchronizowano — brak nowości"
      );
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Synchronizacja nie powiodła się");
    },
  });

  const importMutation = useMutation({
    mutationFn: () => window.ordly.olx.importCsv(),
    onSuccess: (result) => {
      if (!result.cancelled) {
        void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
        toast.success(`Zaimportowano ${result.imported} ofert OLX`);
      }
    },
    onError: () => toast.error("Import CSV nie powiódł się"),
  });

  const items = React.useMemo<PaletteItem[]>(() => {
    const actions: PaletteItem[] = [
      {
        id: "action-sync",
        section: "Szybkie akcje",
        label: "Synchronizuj zamówienia teraz",
        icon: <RefreshIcon size={15} />,
        run: () => syncMutation.mutate(),
      },
      {
        id: "action-import-olx",
        section: "Szybkie akcje",
        label: "Importuj CSV z OLX",
        icon: <TagIcon size={15} />,
        run: () => importMutation.mutate(),
      },
    ];
    const nav: PaletteItem[] = NAV_ITEMS.map((n) => ({
      id: `nav-${n.id}`,
      section: "Nawigacja",
      label: n.label,
      icon: n.icon,
      keywords: `przejdź idź ${n.label}`,
      run: () => onNavigate(n.id),
    }));
    return [...actions, ...nav];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onNavigate]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(q) || item.keywords?.toLowerCase().includes(q)
    );
  }, [items, query]);

  React.useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  React.useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      // Modal renderuje sie po klatce - focus w mikrotasku, zeby input juz istnial w DOM.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    function handleGlobalKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", handleGlobalKey);
    return () => window.removeEventListener("keydown", handleGlobalKey);
  }, [open, onClose]);

  if (!open) return null;

  function activate(item: PaletteItem) {
    item.run();
    onClose();
  }

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = filtered[activeIndex];
      if (item) activate(item);
    }
  }

  let renderedIndex = -1;

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 pt-[14vh]"
      onClick={onClose}
    >
      <div
        className="animate-palette-in flex max-h-[65vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_24px_60px_-15px_rgba(0,0,0,0.7)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-border px-4 py-3.5">
          <SearchIcon size={16} className="shrink-0 text-text-dim" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Szukaj sekcji, uruchom akcję…"
            className="w-full border-0 bg-transparent text-body text-text placeholder:text-text-dim focus:outline-none"
          />
          <kbd className="shrink-0 rounded-md border border-border bg-surface-raised px-1.5 py-0.5 font-mono text-[10px] text-text-dim">
            esc
          </kbd>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {filtered.length === 0 && (
            <p className="px-3 py-6 text-center text-footnote text-text-dim">Brak wyników.</p>
          )}
          {(["Szybkie akcje", "Nawigacja"] as const).map((section) => {
            const sectionItems = filtered.filter((i) => i.section === section);
            if (sectionItems.length === 0) return null;
            return (
              <div key={section} className="mb-1.5 last:mb-0">
                <p className="px-3 pb-1 pt-2 font-mono text-[10px] uppercase tracking-wide text-text-dim">
                  {section}
                </p>
                {sectionItems.map((item) => {
                  renderedIndex += 1;
                  const isActive = renderedIndex === activeIndex;
                  return (
                    <button
                      key={item.id}
                      onMouseEnter={() => setActiveIndex(renderedIndex)}
                      onClick={() => activate(item)}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-[13.5px] font-medium transition-colors ${
                        isActive ? "bg-primary-tint text-primary" : "text-text hover:bg-surface-raised"
                      }`}
                    >
                      <span className="shrink-0">{item.icon}</span>
                      {item.label}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

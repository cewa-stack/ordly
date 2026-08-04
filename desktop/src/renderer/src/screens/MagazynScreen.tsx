/**
 * Magazyn - tabela Produkt · SKU · Zapas · Korekta · Status (sekcja 4.4).
 *
 * Wiersze ponizej progu maja wsuniety pasek `--coral` na lewej krawedzi
 * i ikone Ordiego 22 px w pozie `think` przy nazwie. To jedyny wyjatek
 * od "reguly jednego Ordiego" - tutaj Ordi jest ETYKIETA, nie
 * wskaznikiem stanu (sekcja 3.3).
 *
 * Nowosc wobec poprzedniej wersji: formularz produktu (sekcja 9.1 pkt 6)
 * i historia ruchow magazynowych - wczesniej byl tylko stepper korekty.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClockIcon, PlusIcon } from "../icons";
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  MiniButton,
  Pill,
  SkeletonRows,
  StockBar,
  Stepper,
} from "../components/ui";
import { Modal } from "../components/Modal";
import { Mascot } from "../components/Mascot";
import { useToast } from "../lib/toast";
import { formatDateTime, formatStock } from "../lib/format";
import type { StockItem } from "../types/api";

type StockFilter = "all" | "low" | "zero";

const STOCK_FILTER_LABEL: Record<StockFilter, string> = {
  all: "Wszystkie",
  low: "Poniżej progu",
  zero: "Zerowy stan",
};

interface MagazynScreenProps {
  focusSku: string | null;
  onFocusHandled: () => void;
}

function statusPill(item: StockItem) {
  if (item.status === "critical") return <Pill tone="pack">Brak</Pill>;
  if (item.status === "warning") return <Pill tone="warn">Niski stan</Pill>;
  return <Pill tone="done">W normie</Pill>;
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="o-eyebrow">{label}</span>
      {children}
      <span className="text-[11px] text-slate-dim">{hint}</span>
    </label>
  );
}

function NewProductModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [sku, setSku] = React.useState("");
  const [name, setName] = React.useState("");
  const [minStock, setMinStock] = React.useState("0");

  const mutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.create({
        sku: sku.trim(),
        name: name.trim(),
        min_stock: Number(minStock) || 0,
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Dodano produkt", `${item.sku} · stan początkowy 0`);
      setSku("");
      setName("");
      setMinStock("0");
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Nie udało się dodać produktu",
        error instanceof Error ? error.message : "Sprawdź, czy SKU nie jest już zajęte."
      );
    },
  });

  const canSubmit = sku.trim().length > 0 && name.trim().length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nowy produkt"
      subtitle="Stan początkowy 0 - uzupełnisz go korektą"
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Anuluj
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!canSubmit || mutation.isPending}>
            {mutation.isPending ? "Dodaję…" : "Dodaj produkt"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="SKU" hint="Unikalny identyfikator, np. PET30">
          <input
            value={sku}
            onChange={(event) => setSku(event.target.value.toUpperCase())}
            className="o-mono w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
          />
        </Field>
        <Field label="Nazwa" hint="Tak, jak nazywasz produkt na co dzień">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
          />
        </Field>
        <Field label="Próg niskiego stanu" hint="Poniżej tej liczby Ordi zacznie ostrzegać">
          <input
            type="number"
            min={0}
            value={minStock}
            onChange={(event) => setMinStock(event.target.value)}
            className="o-mono w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
          />
        </Field>
      </div>
    </Modal>
  );
}

function HistoryModal({ sku, onClose }: { sku: string | null; onClose: () => void }) {
  const historyQuery = useQuery({
    queryKey: ["stock-history", sku],
    enabled: sku !== null,
    queryFn: async () => {
      const result = await window.ordly.stock.history(sku as string);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  return (
    <Modal
      open={sku !== null}
      onClose={onClose}
      title="Historia zmian"
      subtitle={sku ?? ""}
      width={520}
    >
      {historyQuery.isLoading && <span className="o-skeleton-bar h-24 w-full" />}
      {historyQuery.data?.length === 0 && (
        <p className="text-[12.5px] text-slate-dim">
          Brak zapisanych ruchów dla tego produktu.
        </p>
      )}
      <div className="flex flex-col">
        {(historyQuery.data ?? []).map((movement, index) => (
          <div
            key={`${movement.created_at}-${index}`}
            className="flex items-center gap-3 border-b border-line py-2.5 text-[12.5px] last:border-b-0"
          >
            <span className="o-mono w-[100px] shrink-0 text-[10.5px] text-slate-dim">
              {formatDateTime(movement.created_at)}
            </span>
            <span
              className={`o-mono w-12 shrink-0 text-right ${
                movement.change < 0 ? "text-coral" : "text-teal-bright"
              }`}
            >
              {movement.change > 0 ? `+${movement.change}` : movement.change}
            </span>
            <span className="min-w-0 flex-1 truncate text-slate">{movement.reason}</span>
          </div>
        ))}
      </div>
    </Modal>
  );
}

export function MagazynScreen({ focusSku, onFocusHandled }: MagazynScreenProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = React.useState<StockFilter>("all");
  const [newOpen, setNewOpen] = React.useState(false);
  const [historySku, setHistorySku] = React.useState<string | null>(null);
  const [highlightSku, setHighlightSku] = React.useState<string | null>(null);
  const rowRefs = React.useRef<Record<string, HTMLTableRowElement | null>>({});

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const adjustMutation = useMutation({
    mutationFn: async ({ sku, delta }: { sku: string; delta: number }) => {
      const result = await window.ordly.stock.adjust(sku, {
        op: delta > 0 ? "add" : "remove",
        quantity: Math.abs(delta),
        reason: "Korekta z aplikacji desktopowej",
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      toast.error(
        "Korekta nie przeszła",
        error instanceof Error ? error.message : "Odśwież listę i spróbuj ponownie."
      );
    },
  });

  // Wejscie z palety polecen - przewin do produktu i podswietl go.
  React.useEffect(() => {
    if (!focusSku) return;
    setFilter("all");
    setHighlightSku(focusSku);
    onFocusHandled();
    const scrollTimer = window.setTimeout(() => {
      rowRefs.current[focusSku]?.scrollIntoView({ block: "center" });
    }, 60);
    const clearTimer = window.setTimeout(() => setHighlightSku(null), 2400);
    return () => {
      window.clearTimeout(scrollTimer);
      window.clearTimeout(clearTimer);
    };
  }, [focusSku, onFocusHandled]);

  const visible = (data ?? []).filter((item) => {
    if (filter === "low") return item.is_low_stock;
    if (filter === "zero") return item.stock === 0;
    return true;
  });

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać magazynu"
        detail={`Pi nie odpowiedziało na zapytanie o stan magazynowy. ${
          error instanceof Error ? error.message : ""
        }`}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-[22px] py-[11px]">
        {(["all", "low", "zero"] as const).map((option) => (
          <Chip key={option} active={filter === option} onClick={() => setFilter(option)}>
            {STOCK_FILTER_LABEL[option]}
          </Chip>
        ))}
        <div className="ml-auto">
          <MiniButton icon={<PlusIcon size={13} />} onClick={() => setNewOpen(true)}>
            Nowy produkt
          </MiniButton>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading && <SkeletonRows rows={6} />}
        {!isLoading && visible.length === 0 && (
          <EmptyState
            pose={filter === "all" ? "idle" : "happy"}
            title={filter === "all" ? "Magazyn jest pusty" : "Nic w tym filtrze"}
            description={
              filter === "all"
                ? "Dodaj pierwszy produkt, żeby Ordi mógł pilnować jego stanu."
                : "Żaden produkt nie spełnia tego warunku - to dobra wiadomość."
            }
          />
        )}
        {!isLoading && visible.length > 0 && (
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Produkt", "SKU", "Zapas", "Korekta", "Status", "Historia"].map(
                  (header, index, all) => (
                    <th
                      key={header}
                      className={`o-mono sticky top-0 z-[2] border-b border-line bg-panel py-[11px] text-left text-[9.5px] uppercase tracking-[.11em] text-slate-dim ${
                        index === 0 || index === all.length - 1 ? "px-[22px]" : "px-3"
                      }`}
                    >
                      {header}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => {
                const max = item.max_stock ?? Math.max(item.min_stock * 2, item.stock, 1);
                return (
                  <tr
                    key={item.sku}
                    ref={(element) => {
                      rowRefs.current[item.sku] = element;
                    }}
                    className={`transition-colors duration-150 ease-ordly hover:bg-panel-2 ${
                      highlightSku === item.sku ? "bg-teal-dim" : ""
                    }`}
                  >
                    <td
                      className={`border-b border-line px-[22px] py-3 text-[13px] text-white ${
                        item.is_low_stock ? "shadow-[inset_3px_0_0_var(--coral)]" : ""
                      }`}
                    >
                      <span className="flex items-center gap-2.5">
                        {item.is_low_stock && <Mascot pose="think" size={22} floaty={false} />}
                        {item.name}
                      </span>
                    </td>
                    <td className="o-mono border-b border-line px-3 py-3 text-[12px] text-slate">
                      {item.sku}
                    </td>
                    <td className="border-b border-line px-3 py-3">
                      <span className="flex items-center gap-2.5">
                        <StockBar value={item.stock} max={max} low={item.is_low_stock} />
                        <span className="o-mono text-[12px] text-slate">
                          {formatStock(item.stock, max)}
                        </span>
                      </span>
                    </td>
                    <td className="border-b border-line px-3 py-3">
                      <Stepper
                        value={item.stock}
                        disabled={adjustMutation.isPending}
                        onDecrease={() => adjustMutation.mutate({ sku: item.sku, delta: -1 })}
                        onIncrease={() => adjustMutation.mutate({ sku: item.sku, delta: 1 })}
                      />
                    </td>
                    <td className="border-b border-line px-3 py-3">{statusPill(item)}</td>
                    <td className="border-b border-line px-[22px] py-3 text-right">
                      <MiniButton
                        icon={<ClockIcon size={13} />}
                        onClick={() => setHistorySku(item.sku)}
                      >
                        Historia
                      </MiniButton>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <NewProductModal open={newOpen} onClose={() => setNewOpen(false)} />
      <HistoryModal sku={historySku} onClose={() => setHistorySku(null)} />
    </div>
  );
}

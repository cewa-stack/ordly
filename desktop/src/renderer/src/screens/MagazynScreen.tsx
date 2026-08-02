import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SearchIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import { StockStatusPill } from "../components/StockStatusPill";
import { WholesalerOrderModal } from "../components/WholesalerOrderModal";
import { useToast } from "../lib/toast";
import type { StockAdjustPayload, StockItem } from "../types/api";

const currency = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });

function useStockList() {
  return useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
}

const inputClass =
  "h-10 rounded-md border border-border bg-background px-3 text-body text-text focus:border-primary focus:outline-none";

interface AdjustStockModalProps {
  item: StockItem;
  onClose: () => void;
}

function AdjustStockModal({ item, onClose }: AdjustStockModalProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [op, setOp] = React.useState<StockAdjustPayload["op"]>("add");
  const [quantity, setQuantity] = React.useState(1);
  const [reason, setReason] = React.useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.adjust(item.sku, {
        op,
        quantity,
        reason: reason.trim() || undefined,
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      toast.success(`${item.name}: nowy stan ${result.stock} szt.`);
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-headline">Koryguj stan — {item.name}</h2>
        <p className="mt-1 text-footnote text-text-secondary">Obecny stan: {item.stock} szt.</p>

        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Operacja</span>
            <select
              value={op}
              onChange={(e) => setOp(e.target.value as StockAdjustPayload["op"])}
              className={`${inputClass} ordly-select`}
            >
              <option value="add">Dodaj do stanu</option>
              <option value="remove">Odejmij ze stanu</option>
              <option value="set">Ustaw dokładny stan</option>
              <option value="min">Ustaw próg minimalny</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Ilość</span>
            <input
              type="number"
              min={0}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(0, Number(e.target.value)))}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Powód (opcjonalnie)</span>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="np. inwentaryzacja, zwrot dostawcy"
              className={inputClass}
            />
          </label>
        </div>

        {mutation.isError && (
          <p className="mt-3 text-caption text-danger">
            {mutation.error instanceof Error ? mutation.error.message : "Nie udało się zapisać zmiany."}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-callout-semibold text-text-secondary hover:bg-surface-raised"
          >
            Anuluj
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="rounded-lg bg-gradient-to-br from-primary to-accent px-4 py-2 text-callout-semibold text-on-primary shadow-[0_8px_18px_-8px_rgba(86,224,208,0.5)] disabled:opacity-45"
          >
            {mutation.isPending ? "Zapisywanie…" : "Zapisz"}
          </button>
        </div>
      </div>
    </div>
  );
}

const columns = ["SKU", "Nazwa", "Stan", "Min.", "Wartość", "Status", ""];

export function MagazynScreen() {
  const { data, isLoading, isError, error } = useStockList();
  const [search, setSearch] = React.useState("");
  const [adjustingItem, setAdjustingItem] = React.useState<StockItem | null>(null);
  const [orderingItem, setOrderingItem] = React.useState<StockItem | null>(null);

  const filtered = React.useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return data;
    return data.filter(
      (item) => item.sku.toLowerCase().includes(q) || item.name.toLowerCase().includes(q)
    );
  }, [data, search]);

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-title1">Magazyn</h1>
        <div className="flex h-9 w-[200px] items-center gap-2 rounded-[10px] border border-border bg-surface px-3 text-footnote text-text-dim">
          <SearchIcon size={14} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Szukaj SKU, nazwy…"
            className="w-full border-0 bg-transparent p-0 text-footnote text-text placeholder:text-text-dim focus:outline-none"
          />
        </div>
      </div>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie magazynu…</p>}
      {isError && (
        <p className="text-footnote text-danger">
          Nie udało się pobrać magazynu: {error instanceof Error ? error.message : "nieznany błąd"}
        </p>
      )}
      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          pose="thinking"
          title="Nic nie znaleziono"
          description="Żaden produkt nie pasuje do wyszukiwania - spróbuj innej frazy."
        />
      )}

      {filtered.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {columns.map((h, i) => (
                  <th
                    key={h || `col-${i}`}
                    className={`border-b border-border px-4 py-2.5 text-left font-mono text-[10.5px] uppercase tracking-wide text-text-dim ${
                      i === 2 || i === 3 || i === 4 ? "text-right" : ""
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, rowIndex) => {
                const isLastRow = rowIndex === filtered.length - 1;
                const cellBorder = isLastRow ? "" : "border-b border-border";
                return (
                  <tr key={item.sku} className="hover:bg-surface-raised">
                    <td className={`px-4 py-3 font-mono text-[12px] text-text-secondary ${cellBorder}`}>
                      {item.sku}
                    </td>
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>{item.name}</td>
                    <td className={`px-4 py-3 text-right text-[13px] font-semibold tabular-nums ${cellBorder}`}>
                      {item.stock}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {item.min_stock}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums text-text-secondary ${cellBorder}`}>
                      {currency.format(item.stock_value)}
                    </td>
                    <td className={`px-4 py-3 ${cellBorder}`}>
                      <StockStatusPill status={item.status} />
                    </td>
                    <td className={`px-4 py-3 text-right ${cellBorder}`}>
                      <div className="inline-flex items-center gap-1">
                        <button
                          onClick={() => setOrderingItem(item)}
                          className="rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-text-secondary hover:bg-surface-raised"
                        >
                          Zamów
                        </button>
                        <button
                          onClick={() => setAdjustingItem(item)}
                          className="rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-primary hover:bg-primary-tint"
                        >
                          Koryguj
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {adjustingItem && (
        <AdjustStockModal item={adjustingItem} onClose={() => setAdjustingItem(null)} />
      )}
      {orderingItem && (
        <WholesalerOrderModal item={orderingItem} onClose={() => setOrderingItem(null)} />
      )}
    </div>
  );
}

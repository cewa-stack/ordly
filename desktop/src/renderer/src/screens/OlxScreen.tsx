import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import { useToast } from "../lib/toast";
import type { OlxOffer } from "../types/api";

const currency = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });
const inputClass =
  "h-10 rounded-md border border-border bg-background px-3 text-body text-text focus:border-primary focus:outline-none";

function useOlxOffers() {
  return useQuery({ queryKey: ["olx-offers"], queryFn: () => window.ordly.olx.list() });
}

/** Stan magazynowy (z tego samego /api/v1/stock co ekran Magazyn) do recznego porownania z ofertami OLX. */
function useStockBySku() {
  return useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      const map = new Map<string, number>();
      for (const item of result.data) map.set(item.sku, item.stock);
      return map;
    },
  });
}

interface OfferFormModalProps {
  offer: OlxOffer | null;
  onClose: () => void;
}

function OfferFormModal({ offer, onClose }: OfferFormModalProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = React.useState(offer?.title ?? "");
  const [price, setPrice] = React.useState(offer?.price ?? 0);
  const [stock, setStock] = React.useState(offer?.stock ?? 0);
  const [url, setUrl] = React.useState(offer?.url ?? "");
  const [linkedSku, setLinkedSku] = React.useState(offer?.linkedSku ?? "");

  const saveMutation = useMutation({
    mutationFn: () =>
      window.ordly.olx.save({
        id: offer?.id,
        title: title.trim(),
        price,
        stock,
        url: url.trim(),
        linkedSku: linkedSku.trim() || undefined,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
      onClose();
    },
  });

  const canSave = title.trim().length > 0;

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-headline">{offer ? "Edytuj ofertę OLX" : "Nowa oferta OLX"}</h2>
        <div className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Tytuł ogłoszenia</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1.5">
              <span className="text-caption text-text-secondary">Cena</span>
              <input
                type="number"
                min={0}
                value={price}
                onChange={(e) => setPrice(Math.max(0, Number(e.target.value)))}
                className={inputClass}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1.5">
              <span className="text-caption text-text-secondary">Stan (OLX)</span>
              <input
                type="number"
                min={0}
                value={stock}
                onChange={(e) => setStock(Math.max(0, Number(e.target.value)))}
                className={inputClass}
              />
            </label>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Link do ogłoszenia (opcjonalnie)</span>
            <input value={url} onChange={(e) => setUrl(e.target.value)} className={inputClass} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-caption text-text-secondary">Powiązane SKU w Magazynie (opcjonalnie)</span>
            <input
              value={linkedSku}
              onChange={(e) => setLinkedSku(e.target.value)}
              placeholder="np. ETU-014"
              className={inputClass}
            />
          </label>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-callout-semibold text-text-secondary hover:bg-surface-raised">
            Anuluj
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!canSave || saveMutation.isPending}
            className="rounded-lg bg-gradient-to-br from-primary to-accent px-4 py-2 text-callout-semibold text-on-primary shadow-[0_8px_18px_-8px_rgba(86,224,208,0.5)] disabled:opacity-45"
          >
            {saveMutation.isPending ? "Zapisywanie…" : "Zapisz"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function OlxScreen() {
  const { data: offers, isLoading } = useOlxOffers();
  const { data: stockBySku } = useStockBySku();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = React.useState<OlxOffer | null | "new">(null);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => window.ordly.olx.delete(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["olx-offers"] }),
  });

  const importMutation = useMutation({
    mutationFn: () => window.ordly.olx.importCsv(),
    onSuccess: (result) => {
      if (!result.cancelled) {
        toast.success(`Zaimportowano ${result.imported} ofert OLX`);
        void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
      }
    },
    onError: () => toast.error("Import CSV nie powiódł się"),
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <h1 className="text-title1">OLX</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending}
            className="flex h-9 items-center gap-2 rounded-[10px] border border-border bg-surface px-3.5 text-[12.5px] font-semibold text-text-secondary hover:bg-surface-raised disabled:opacity-50"
          >
            {importMutation.isPending ? "Importowanie…" : "Importuj z CSV"}
          </button>
          <button
            onClick={() => setEditing("new")}
            className="flex h-9 items-center gap-2 rounded-[10px] bg-gradient-to-br from-primary to-accent px-3.5 text-[12.5px] font-bold text-on-primary"
          >
            <PlusIcon size={14} className="text-on-primary" />
            Dodaj ofertę
          </button>
        </div>
      </div>

      <p className="mb-4 text-footnote text-text-secondary">
        Brak automatycznej synchronizacji z OLX (wymaga rejestracji własnej aplikacji na{" "}
        developer.olx.pl) - oferty wpisujesz ręcznie albo importujesz z pliku CSV (kolumny:
        title, price, stock, url, sku).
      </p>

      {isLoading && <p className="text-footnote text-text-secondary">Wczytywanie…</p>}
      {!isLoading && offers && offers.length === 0 && (
        <EmptyState
          pose="thinking"
          title="Brak ofert OLX"
          description="Dodaj ofertę ręcznie albo zaimportuj listę z pliku CSV."
        />
      )}

      {offers && offers.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Tytuł", "Cena", "Stan (OLX)", "Stan w Magazynie", ""].map((h) => (
                  <th
                    key={h || "actions"}
                    className="border-b border-border px-4 py-2.5 text-left font-mono text-[10.5px] uppercase tracking-wide text-text-dim"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {offers.map((offer, rowIndex) => {
                const cellBorder = rowIndex === offers.length - 1 ? "" : "border-b border-border";
                const magazynStock = offer.linkedSku ? stockBySku?.get(offer.linkedSku) : undefined;
                const mismatch = magazynStock !== undefined && magazynStock !== offer.stock;
                return (
                  <tr key={offer.id} className="hover:bg-surface-raised">
                    <td className={`px-4 py-3 text-[13px] ${cellBorder}`}>
                      {offer.url ? (
                        <a href={offer.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                          {offer.title}
                        </a>
                      ) : (
                        offer.title
                      )}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums ${cellBorder}`}>
                      {currency.format(offer.price)}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] font-semibold tabular-nums ${cellBorder}`}>
                      {offer.stock}
                    </td>
                    <td className={`px-4 py-3 text-right text-[13px] tabular-nums ${cellBorder}`}>
                      {magazynStock === undefined ? (
                        <span className="text-text-dim">—</span>
                      ) : (
                        <span className={mismatch ? "font-semibold text-warning" : "text-text-secondary"}>
                          {magazynStock}
                        </span>
                      )}
                    </td>
                    <td className={`px-4 py-3 text-right ${cellBorder}`}>
                      <div className="inline-flex items-center gap-1">
                        <button
                          onClick={() => setEditing(offer)}
                          className="rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-primary hover:bg-primary-tint"
                        >
                          Edytuj
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(offer.id)}
                          className="rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-danger hover:bg-danger-tint"
                        >
                          Usuń
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

      {editing && (
        <OfferFormModal offer={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

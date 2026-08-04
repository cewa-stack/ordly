/**
 * OLX - oferty prowadzone recznie.
 *
 * OLX nie ma tu automatycznej synchronizacji (wymagalaby rejestracji
 * wlasnej aplikacji na developer.olx.pl), wiec ekran mowi to wprost
 * zamiast udawac integracje. Dane trzymane sa lokalnie na komputerze
 * przez main proces, nie na Pi.
 *
 * NAPRAWA PRZY OKAZJI: poprzednia wersja robila `useQuery` z kluczem
 * `["stock"]`, ale zwracala `Map<string, number>` zamiast `StockItem[]`.
 * Ten sam klucz co ekran Magazyn oznacza WSPOLNY wpis w cache - kto
 * pobral pierwszy, ten narzucal ksztalt danych drugiemu. Teraz mapa
 * powstaje przez `select`, ktory nie dotyka tego, co siedzi w cache.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExportIcon, ExternalIcon, PencilIcon, PlusIcon, TrashIcon } from "../icons";
import { Button, EmptyState, MiniButton, SkeletonRows } from "../components/ui";
import { ConfirmDialog, Modal } from "../components/Modal";
import { useToast } from "../lib/toast";
import { formatCurrency } from "../lib/format";
import type { OlxOffer } from "../types/api";

const inputClass =
  "w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright";

function OfferFormModal({ offer, onClose }: { offer: OlxOffer | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = React.useState(offer?.title ?? "");
  const [price, setPrice] = React.useState(String(offer?.price ?? 0));
  const [stock, setStock] = React.useState(String(offer?.stock ?? 0));
  const [url, setUrl] = React.useState(offer?.url ?? "");
  const [linkedSku, setLinkedSku] = React.useState(offer?.linkedSku ?? "");

  const saveMutation = useMutation({
    mutationFn: () =>
      window.ordly.olx.save({
        id: offer?.id,
        title: title.trim(),
        price: Math.max(0, Number(price) || 0),
        stock: Math.max(0, Number(stock) || 0),
        url: url.trim(),
        linkedSku: linkedSku.trim().toUpperCase() || undefined,
      }),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
      toast.success(offer ? "Zapisano ofertę" : "Dodano ofertę", saved.title);
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={offer ? "Edytuj ofertę OLX" : "Nowa oferta OLX"}
      width={480}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saveMutation.isPending}>
            Anuluj
          </Button>
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={title.trim().length === 0 || saveMutation.isPending}
          >
            {saveMutation.isPending ? "Zapisuję…" : "Zapisz"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Tytuł ogłoszenia</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
        </label>
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1.5">
            <span className="o-eyebrow">Cena</span>
            <input
              type="number"
              min={0}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className={`${inputClass} o-mono`}
            />
          </label>
          <label className="flex flex-1 flex-col gap-1.5">
            <span className="o-eyebrow">Stan na OLX</span>
            <input
              type="number"
              min={0}
              value={stock}
              onChange={(e) => setStock(e.target.value)}
              className={`${inputClass} o-mono`}
            />
          </label>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Link do ogłoszenia</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="opcjonalnie"
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="o-eyebrow">Powiązane SKU</span>
          <input
            value={linkedSku}
            onChange={(e) => setLinkedSku(e.target.value)}
            placeholder="np. PET30 - pozwala porównać stany"
            className={`${inputClass} o-mono`}
          />
        </label>
      </div>
    </Modal>
  );
}

export function OlxScreen() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = React.useState<OlxOffer | null | "new">(null);
  const [deleting, setDeleting] = React.useState<OlxOffer | null>(null);

  const offersQuery = useQuery({
    queryKey: ["olx-offers"],
    queryFn: () => window.ordly.olx.list(),
  });

  const stockBySku = useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    // `select` przeksztalca dane WYDANE z cache, nie te w cache - dzieki
    // temu ekran Magazyn dalej dostaje pod tym kluczem swoja tablice.
    select: (items) => new Map(items.map((item) => [item.sku, item.stock])),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => window.ordly.olx.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
      setDeleting(null);
      toast.success("Usunięto ofertę", "Lista OLX zaktualizowana.");
    },
  });

  const importMutation = useMutation({
    mutationFn: () => window.ordly.olx.importCsv(),
    onSuccess: (result) => {
      if (result.cancelled) return;
      void queryClient.invalidateQueries({ queryKey: ["olx-offers"] });
      toast.success(
        "Zaimportowano oferty",
        `${result.imported} ${result.imported === 1 ? "pozycja" : "pozycji"} z pliku CSV`
      );
    },
    onError: () =>
      toast.error(
        "Import CSV nie przeszedł",
        "Sprawdź kolumny: title, price, stock, url, sku."
      ),
  });

  const offers = offersQuery.data ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-[22px] py-[11px]">
        <p className="text-[11.5px] leading-[1.5] text-slate-dim">
          OLX nie ma publicznego API dla sprzedawcy - te oferty prowadzisz ręcznie, a ORDLY
          pilnuje, żeby stan zgadzał się z magazynem.
        </p>
        <div className="ml-auto flex gap-2">
          <MiniButton
            icon={<ExportIcon size={13} className="rotate-180" />}
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending}
          >
            {importMutation.isPending ? "Importuję…" : "Importuj z CSV"}
          </MiniButton>
          <MiniButton icon={<PlusIcon size={13} />} onClick={() => setEditing("new")}>
            Dodaj ofertę
          </MiniButton>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {offersQuery.isLoading && <SkeletonRows rows={4} />}
        {!offersQuery.isLoading && offers.length === 0 && (
          <EmptyState
            pose="think"
            title="Brak ofert OLX"
            description="Dodaj ofertę ręcznie albo zaimportuj listę z pliku CSV."
          />
        )}
        {offers.length > 0 && (
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Tytuł", "Cena", "Stan na OLX", "Stan w magazynie", "Akcje"].map((header) => (
                  <th
                    key={header}
                    className="o-mono sticky top-0 z-[2] border-b border-line bg-panel px-[22px] py-[11px] text-left text-[9.5px] uppercase tracking-[.11em] text-slate-dim"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {offers.map((offer) => {
                const warehouseStock = offer.linkedSku
                  ? stockBySku.data?.get(offer.linkedSku)
                  : undefined;
                const mismatch =
                  warehouseStock !== undefined && warehouseStock !== offer.stock;
                return (
                  <tr key={offer.id} className="transition-colors hover:bg-panel-2">
                    <td className="border-b border-line px-[22px] py-3 text-[13px] text-white">
                      <span className="flex items-center gap-2">
                        {offer.title}
                        {offer.url && (
                          <a
                            href={offer.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label="Otwórz ogłoszenie na OLX"
                            className="text-slate-dim hover:text-teal-bright"
                          >
                            <ExternalIcon size={13} />
                          </a>
                        )}
                      </span>
                    </td>
                    <td className="o-mono border-b border-line px-[22px] py-3 text-[12px] text-slate">
                      {formatCurrency(offer.price)}
                    </td>
                    <td className="o-mono border-b border-line px-[22px] py-3 text-[12px] text-white">
                      {offer.stock}
                    </td>
                    <td className="o-mono border-b border-line px-[22px] py-3 text-[12px]">
                      {warehouseStock === undefined ? (
                        <span className="text-slate-dim">—</span>
                      ) : (
                        <span className={mismatch ? "font-semibold text-amber" : "text-slate"}>
                          {warehouseStock}
                          {mismatch ? " ≠" : ""}
                        </span>
                      )}
                    </td>
                    <td className="border-b border-line px-[22px] py-3">
                      <span className="flex gap-1">
                        <MiniButton
                          className="!px-2"
                          onClick={() => setEditing(offer)}
                          aria-label="Edytuj"
                        >
                          <PencilIcon size={13} />
                        </MiniButton>
                        <MiniButton
                          className="!px-2 hover:!text-coral"
                          onClick={() => setDeleting(offer)}
                          aria-label="Usuń"
                        >
                          <TrashIcon size={13} />
                        </MiniButton>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <OfferFormModal
          offer={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}

      <ConfirmDialog
        open={deleting !== null}
        title={`Usunąć ofertę „${deleting?.title ?? ""}”?`}
        message="Oferta zniknie z listy w ORDLY. Samo ogłoszenie na OLX zostaje - to usuwa się w panelu OLX."
        confirmLabel="Usuń ofertę"
        pending={deleteMutation.isPending}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}

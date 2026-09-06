/**
 * Powiązania ofert - z czego magazynowo składa się oferta marketplace.
 *
 * Bez receptury sprzedaż w ogóle nie rusza stanów: ORDLY nie wie, że
 * "Butelka 60 ml z kroplomierzem" to butelka PLUS kroplomierz PLUS
 * nakrętka. Ten widok pokazuje najpierw oferty, które sprzedają się bez
 * receptury (bo to one cicho psują magazyn), a dopiero pod spodem te
 * już powiązane.
 *
 * Korekta wsteczna nadrabia sprzedaż sprzed powiązania. Rozlicza się
 * per zamówienie, więc podglad i zastosowanie pokazuja te sama liczbe,
 * a powtorzenie nie odejmuje niczego drugi raz.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertIcon, LinkIcon, PencilIcon, PlusIcon, TrashIcon } from "../icons";
import {
  Button,
  EmptyState,
  ErrorState,
  MiniButton,
  Pill,
  SectionLabel,
  SkeletonRows,
} from "../components/ui";
import { Modal, ConfirmDialog } from "../components/Modal";
import { useToast } from "../lib/toast";
import { formatAge, formatDateTime } from "../lib/format";
import type {
  BackfillPlan,
  OfferRecipe,
  OfferRef,
  StockItem,
  UnmappedOffer,
} from "../types/api";

/** Oferta otwarta w edytorze receptury (z widoku powiązań lub katalogu). */
export interface OfferTarget {
  marketplace: string;
  externalProductId: string;
  offerName: string | null;
  components: { sku: string; quantity: number }[];
}

function toRef(target: OfferTarget | OfferRecipe | UnmappedOffer): OfferRef {
  return {
    marketplace: target.marketplace,
    externalProductId:
      "externalProductId" in target ? target.externalProductId : target.external_product_id,
  };
}

// ------------------------------------------------------------ Edytor receptury

export function RecipeModal({
  target,
  stock,
  onClose,
}: {
  target: OfferTarget | null;
  stock: StockItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [rows, setRows] = React.useState<{ sku: string; quantity: number }[]>([]);

  React.useEffect(() => {
    if (!target) return;
    setRows(target.components.length > 0 ? target.components : [{ sku: "", quantity: 1 }]);
  }, [target]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!target) throw new Error("Brak oferty");
      const result = await window.ordly.stock.setRecipe(toRef(target), {
        components: rows
          .filter((row) => row.sku)
          .map((row) => ({ sku: row.sku, quantity: row.quantity })),
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (recipe) => {
      void queryClient.invalidateQueries({ queryKey: ["offer-recipes"] });
      void queryClient.invalidateQueries({ queryKey: ["unmapped-offers"] });
      toast.success(
        "Zapisano powiązanie",
        `${recipe.components.length} składnik(i) - kolejne sprzedaże zdejmą je z magazynu`
      );
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać powiązania",
        error instanceof Error ? error.message : "Sprawdź składniki i spróbuj ponownie."
      );
    },
  });

  const used = new Set(rows.map((row) => row.sku).filter(Boolean));
  const filled = rows.filter((row) => row.sku);
  const hasDuplicate = used.size !== filled.length;
  const canSubmit = filled.length > 0 && !hasDuplicate;

  return (
    <Modal
      open={target !== null}
      onClose={onClose}
      title="Składniki oferty"
      subtitle={target ? (target.offerName ?? target.externalProductId) : ""}
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Anuluj
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!canSubmit || mutation.isPending}>
            {mutation.isPending ? "Zapisuję…" : "Zapisz powiązanie"}
          </Button>
        </>
      }
    >
      <p className="mb-4 text-[12.5px] leading-[1.6] text-slate">
        Sprzedaż <strong className="text-white">jednej sztuki</strong> tej oferty zdejmie z
        magazynu poniższe ilości. Butelka sprzedawana z kroplomierzem i nakrętką ma trzy
        składniki po 1 szt.
      </p>

      <div className="flex flex-col gap-2">
        {rows.map((row, index) => (
          <div key={index} className="flex items-center gap-2">
            <select
              value={row.sku}
              onChange={(event) => {
                const value = event.target.value;
                setRows((current) =>
                  current.map((item, i) => (i === index ? { ...item, sku: value } : item))
                );
              }}
              className="min-w-0 flex-1 rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
            >
              <option value="">— wybierz produkt magazynowy —</option>
              {stock.map((item) => (
                <option key={item.sku} value={item.sku}>
                  {item.name} ({item.sku})
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              value={row.quantity}
              onChange={(event) => {
                const value = Math.max(1, Number(event.target.value) || 1);
                setRows((current) =>
                  current.map((item, i) => (i === index ? { ...item, quantity: value } : item))
                );
              }}
              aria-label="Ilość na sztukę oferty"
              className="o-mono w-[74px] shrink-0 rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
            />
            <button
              onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
              disabled={rows.length === 1}
              aria-label="Usuń składnik"
              className="shrink-0 text-slate-dim transition-colors hover:text-coral disabled:pointer-events-none disabled:opacity-40"
            >
              <TrashIcon size={14} />
            </button>
          </div>
        ))}
      </div>

      {hasDuplicate && (
        <p className="mt-3 text-[11.5px] text-coral">
          Ten sam produkt nie może wystąpić dwa razy - zsumuj go w jednym wierszu.
        </p>
      )}

      <div className="mt-3">
        <MiniButton
          icon={<PlusIcon size={13} />}
          onClick={() => setRows((current) => [...current, { sku: "", quantity: 1 }])}
        >
          Dodaj składnik
        </MiniButton>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------- Korekta wsteczna

function BackfillModal({ offer, onClose }: { offer: OfferRef | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const preview = useQuery({
    queryKey: ["offer-backfill", offer?.marketplace, offer?.externalProductId],
    enabled: offer !== null,
    queryFn: async () => {
      const result = await window.ordly.stock.previewBackfill(offer as OfferRef);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const apply = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.applyBackfill(offer as OfferRef);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (plan: BackfillPlan) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["offer-backfill"] });
      toast.success(
        "Stany uzupełnione",
        `Rozliczono ${plan.lines.length} zamówien(ia) tej oferty`
      );
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Korekta nie przeszła",
        error instanceof Error ? error.message : "Spróbuj ponownie za chwilę."
      );
    },
  });

  const plan = preview.data;
  const pending = plan?.pending_quantity ?? 0;

  return (
    <Modal
      open={offer !== null}
      onClose={onClose}
      title="Uzupełnij stany wstecz"
      subtitle={plan?.offer_name ?? offer?.externalProductId ?? ""}
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={apply.isPending}>
            Zamknij
          </Button>
          <Button
            onClick={() => apply.mutate()}
            disabled={apply.isPending || pending === 0 || preview.isLoading}
          >
            {apply.isPending ? "Odejmuję…" : `Odejmij ${pending} szt.`}
          </Button>
        </>
      }
    >
      {preview.isLoading && <span className="o-skeleton-bar h-24 w-full" />}
      {preview.isError && (
        <p className="text-[12.5px] leading-[1.6] text-coral">
          {preview.error instanceof Error
            ? preview.error.message
            : "Nie udało się policzyć korekty."}
        </p>
      )}

      {plan && pending === 0 && (
        <p className="text-[12.5px] leading-[1.6] text-slate">
          Nie ma czego nadrabiać - cała sprzedaż tej oferty z ostatnich 90 dni jest już
          rozliczona w magazynie.
        </p>
      )}

      {plan && pending > 0 && (
        <>
          <p className="mb-4 text-[12.5px] leading-[1.6] text-slate">
            Sprzedaż sprzed powiązania nie zdjęła nic z magazynu. Po zatwierdzeniu stany
            zmienią się tak:
          </p>
          <div className="mb-4 flex flex-col gap-1.5">
            {plan.components.map((component) => (
              <div
                key={component.sku}
                className="flex items-center gap-3 rounded-md border border-line px-3 py-2 text-[12.5px]"
              >
                <span className="min-w-0 flex-1 truncate text-white">{component.name}</span>
                <span className="o-mono text-slate-dim">{component.current_stock}</span>
                <span className="text-slate-dim">→</span>
                <span className="o-mono text-coral">−{component.quantity}</span>
                <span className="text-slate-dim">→</span>
                <span className="o-mono w-8 text-right text-teal-bright">
                  {component.stock_after}
                </span>
              </div>
            ))}
          </div>

          <SectionLabel>Rozliczane zamówienia</SectionLabel>
          <div className="mt-2 flex flex-col">
            {plan.lines.map((line) => (
              <div
                key={line.order_external_id}
                className="flex items-center gap-3 border-b border-line py-2 text-[12px] last:border-b-0"
              >
                <span className="o-mono w-[92px] shrink-0 text-[10.5px] text-slate-dim">
                  {formatDateTime(line.order_date)}
                </span>
                <span className="o-mono min-w-0 flex-1 truncate text-slate">
                  {line.order_external_id}
                </span>
                <span className="o-mono shrink-0 text-slate">{line.quantity} szt.</span>
                {line.already_applied && <Pill tone="done">rozliczone</Pill>}
              </div>
            ))}
          </div>
        </>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------- Widok

export function PowiazaniaOfertView() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = React.useState<OfferTarget | null>(null);
  const [backfilling, setBackfilling] = React.useState<OfferRef | null>(null);
  const [deleting, setDeleting] = React.useState<OfferRecipe | null>(null);

  const recipes = useQuery({
    queryKey: ["offer-recipes"],
    queryFn: async () => {
      const result = await window.ordly.stock.recipes();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const unmapped = useQuery({
    queryKey: ["unmapped-offers"],
    queryFn: async () => {
      const result = await window.ordly.stock.unmappedOffers();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const stock = useQuery({
    queryKey: ["stock"],
    queryFn: async () => {
      const result = await window.ordly.stock.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (recipe: OfferRecipe) => {
      const result = await window.ordly.stock.deleteRecipe(toRef(recipe));
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["offer-recipes"] });
      void queryClient.invalidateQueries({ queryKey: ["unmapped-offers"] });
      toast.success("Powiązanie usunięte", "Sprzedaż tej oferty nie rusza już magazynu");
      setDeleting(null);
    },
    onError: (error) => {
      toast.error(
        "Nie udało się usunąć powiązania",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  if (recipes.isError || unmapped.isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać powiązań"
        detail="Pi nie odpowiedziało na zapytanie o receptury ofert."
        onRetry={() => {
          void recipes.refetch();
          void unmapped.refetch();
        }}
      />
    );
  }

  const isLoading = recipes.isLoading || unmapped.isLoading;
  const unmappedOffers = unmapped.data ?? [];
  const offerRecipes = recipes.data ?? [];

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-[22px] py-4">
      {isLoading && <SkeletonRows rows={4} />}

      {!isLoading && unmappedOffers.length > 0 && (
        <section className="mb-7">
          <div className="mb-2.5 flex items-center gap-2">
            <AlertIcon size={14} className="text-coral" />
            <SectionLabel>Sprzedają się bez powiązania</SectionLabel>
          </div>
          <p className="mb-3 text-[12px] leading-[1.6] text-slate-dim">
            Te oferty się sprzedały, ale ORDLY nie wie, co zdjąć z półki - dlatego ich stany
            stoją w miejscu.
          </p>
          <div className="flex flex-col gap-2">
            {unmappedOffers.map((offer) => (
              <div
                key={`${offer.marketplace}-${offer.external_product_id}`}
                className="flex items-center gap-3 rounded-lg border border-line bg-panel-2 px-3.5 py-3 shadow-[inset_3px_0_0_var(--coral)]"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] text-white">{offer.name}</p>
                  <p className="o-mono mt-1 text-[10.5px] text-slate-dim">
                    {offer.external_product_id} · {offer.sold_quantity} szt. w{" "}
                    {offer.orders_count} zamówieniach · ostatnio{" "}
                    {formatAge(offer.last_sold_at)} temu
                  </p>
                </div>
                <Button
                  icon={<LinkIcon size={13} />}
                  onClick={() =>
                    setEditing({
                      marketplace: offer.marketplace,
                      externalProductId: offer.external_product_id,
                      offerName: offer.name,
                      components: [],
                    })
                  }
                >
                  Przypisz składniki
                </Button>
              </div>
            ))}
          </div>
        </section>
      )}

      {!isLoading && (
        <section>
          <SectionLabel>Powiązane oferty</SectionLabel>
          <p className="mt-2 mb-1 text-[12px] leading-[1.6] text-slate-dim">
            Jeśli oferta sprzedaje produkt złożony z podproduktów (np. butelka
            z nakrętką i kroplomierzem), wystarczy powiązać ją z samym produktem
            głównym — podprodukty odejmą się automatycznie. Skonfigurujesz je
            w Magazyn → Produkty → Podprodukty.
          </p>
          {offerRecipes.length === 0 ? (
            <div className="mt-2">
              <EmptyState
                pose={unmappedOffers.length > 0 ? "think" : "idle"}
                title="Żadna oferta nie ma jeszcze składników"
                description="Dopóki oferta nie ma powiązania, jej sprzedaż nie zmienia stanów magazynowych."
              />
            </div>
          ) : (
            <div className="mt-2 flex flex-col gap-2">
              {offerRecipes.map((recipe) => (
                <div
                  key={`${recipe.marketplace}-${recipe.external_product_id}`}
                  className="rounded-lg border border-line bg-panel-2 px-3.5 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] text-white">
                        {recipe.offer_name ?? "Oferta bez sprzedaży w ostatnich 90 dniach"}
                      </p>
                      <p className="o-mono mt-1 text-[10.5px] text-slate-dim">
                        {recipe.external_product_id}
                      </p>
                    </div>
                    <MiniButton
                      icon={<PencilIcon size={13} />}
                      onClick={() =>
                        setEditing({
                          marketplace: recipe.marketplace,
                          externalProductId: recipe.external_product_id,
                          offerName: recipe.offer_name,
                          components: recipe.components.map((component) => ({
                            sku: component.sku,
                            quantity: component.quantity,
                          })),
                        })
                      }
                    >
                      Edytuj
                    </MiniButton>
                    <MiniButton onClick={() => setBackfilling(toRef(recipe))}>
                      Uzupełnij wstecz
                    </MiniButton>
                    <MiniButton
                      icon={<TrashIcon size={13} />}
                      onClick={() => setDeleting(recipe)}
                    >
                      Usuń
                    </MiniButton>
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {recipe.components.map((component) => (
                      <span
                        key={component.sku}
                        className="rounded-[6px] border border-line px-2 py-1 text-[11.5px] text-slate"
                      >
                        {component.quantity} × {component.name}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <RecipeModal
        target={editing}
        stock={stock.data ?? []}
        onClose={() => setEditing(null)}
      />
      <BackfillModal offer={backfilling} onClose={() => setBackfilling(null)} />
      <ConfirmDialog
        open={deleting !== null}
        title="Usunąć powiązanie?"
        message={
          deleting
            ? `Sprzedaż oferty "${
                deleting.offer_name ?? deleting.external_product_id
              }" przestanie zdejmować cokolwiek z magazynu. Dotychczasowe ruchy zostają w historii.`
            : ""
        }
        confirmLabel="Usuń powiązanie"
        pending={removeMutation.isPending}
        onConfirm={() => deleting && removeMutation.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}

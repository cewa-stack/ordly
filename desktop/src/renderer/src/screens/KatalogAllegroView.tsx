/**
 * Asortyment pobrany z Allegro - lista ofert, które NAPRAWDĘ istnieją.
 *
 * DLACZEGO TEN WIDOK. Do tej pory jedyną listą ofert w ORDLY była
 * historia sprzedaży, więc ofertę dawało się powiązać dopiero po tym,
 * jak sprzedała się bez powiązania. Ostrzeżenie o braku powiązania
 * wisiało wtedy w kółko, bo nie było skąd wziąć numeru oferty.
 *
 * Tutaj oferty schodzą prosto z API Allegro. Każda niesie stan
 * powiązania w czterech odcieniach i to rozróżnienie jest sednem widoku:
 * zielone "zdejmuje stan" pojawia się WYŁĄCZNIE tam, gdzie sprzedaż
 * naprawdę ruszy magazyn. Sygnatura pasująca do SKU to dopiero
 * podpowiedź do kliknięcia, nie powiązanie - `ComponentResolver` sygnatur
 * nie zna.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertIcon, CheckIcon, LinkIcon, PlusIcon, RefreshIcon, SearchIcon } from "../icons";
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  MiniButton,
  Pill,
  SectionLabel,
  SkeletonRows,
} from "../components/ui";
import { useToast } from "../lib/toast";
import { formatCurrency } from "../lib/format";
import type { CatalogOffer, OfferLinkType } from "../types/api";

/** Co pokazujemy: wszystko czy tylko to, co cicho psuje magazyn. */
type CatalogFilter = "all" | "unlinked";

interface LinkBadge {
  tone: "new" | "warn" | "pack";
  label: string;
}

/**
 * Opis stanu powiązania. `signature` celowo NIE dostaje zielonego
 * odcienia - dopóki receptury nie ma, sprzedaż tej oferty przechodzi
 * obok magazynu, choć sygnatura wygląda obiecująco.
 */
const LINK_BADGE: Record<OfferLinkType, LinkBadge> = {
  recipe: { tone: "new", label: "zdejmuje stan" },
  sku: { tone: "new", label: "zdejmuje stan (po SKU)" },
  signature: { tone: "warn", label: "sygnatura pasuje - dowiąż" },
  none: { tone: "pack", label: "nie rusza magazynu" },
};

export function KatalogAllegroView({
  onLinkOffer,
}: {
  /** Otwiera edytor receptury dla wskazanej oferty. */
  onLinkOffer: (offer: CatalogOffer) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = React.useState<CatalogFilter>("all");
  const [search, setSearch] = React.useState("");
  const [picked, setPicked] = React.useState<Set<string>>(new Set());

  const catalog = useQuery({
    queryKey: ["offer-catalog"],
    queryFn: async () => {
      const result = await window.ordly.stock.catalog();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  /** Po każdej zmianie powiązań odświeżamy wszystko, co je pokazuje. */
  function invalidateLinks() {
    void queryClient.invalidateQueries({ queryKey: ["offer-catalog"] });
    void queryClient.invalidateQueries({ queryKey: ["offer-recipes"] });
    void queryClient.invalidateQueries({ queryKey: ["unmapped-offers"] });
    void queryClient.invalidateQueries({ queryKey: ["stock"] });
  }

  const syncMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.syncCatalog();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (summary) => {
      invalidateLinks();
      setPicked(new Set());
      const linked =
        summary.auto_linked > 0 ? `, dowiązano ${summary.auto_linked} po sygnaturze` : "";
      toast.success(
        "Asortyment pobrany",
        `${summary.fetched} ofert z Allegro${linked}. Bez powiązania: ${summary.unlinked}.`
      );
    },
    onError: (error) => {
      toast.error(
        "Nie udało się pobrać asortymentu",
        error instanceof Error
          ? error.message
          : "Sprawdź połączenie z Allegro w Ustawieniach."
      );
    },
  });

  const relinkMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.relinkCatalog();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: ({ linked }) => {
      invalidateLinks();
      if (linked > 0) {
        toast.success(
          "Dowiązano po sygnaturze",
          `${linked} ofert(y) zdejmuje od teraz stan magazynowy`
        );
      } else {
        toast.success(
          "Nie było czego dowiązać",
          "Żadna sygnatura oferty nie wskazuje produktu z magazynu"
        );
      }
    },
    onError: (error) => {
      toast.error(
        "Dowiązanie nie przeszło",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  const importMutation = useMutation({
    mutationFn: async (externalIds: string[]) => {
      const result = await window.ordly.stock.importOffers(externalIds);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (summary) => {
      invalidateLinks();
      setPicked(new Set());
      const skipped =
        summary.skipped.length > 0 ? ` Pominięto ${summary.skipped.length}.` : "";
      toast.success(
        "Produkty założone",
        `${summary.created.length} nowych pozycji, ${summary.linked.length} powiązań.${skipped}`
      );
    },
    onError: (error) => {
      toast.error(
        "Import nie przeszedł",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  const offers = React.useMemo(() => catalog.data ?? [], [catalog.data]);

  const visible = React.useMemo(() => {
    const needle = search.trim().toLowerCase();
    return offers.filter((offer) => {
      if (filter === "unlinked" && offer.is_linked) return false;
      if (!needle) return true;
      return (
        offer.name.toLowerCase().includes(needle) ||
        offer.external_id.includes(needle) ||
        (offer.signature ?? "").toLowerCase().includes(needle)
      );
    });
  }, [offers, filter, search]);

  const unlinkedCount = offers.filter((offer) => !offer.is_linked).length;
  const suggestedCount = offers.filter((offer) => offer.link_type === "signature").length;

  /** Do importu nadają się tylko oferty jeszcze niezdejmujące stanu. */
  const importable = visible.filter((offer) => !offer.is_linked);
  const pickedList = [...picked];

  function togglePicked(externalId: string) {
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(externalId)) next.delete(externalId);
      else next.add(externalId);
      return next;
    });
  }

  if (catalog.isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać katalogu"
        detail="Pi nie odpowiedziało na zapytanie o asortyment marketplace."
        onRetry={() => void catalog.refetch()}
      />
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Pasek narzędzi: pobranie asortymentu, filtr, szukajka. */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-[22px] py-[11px]">
        <Chip active={filter === "all"} onClick={() => setFilter("all")}>
          Wszystkie
          {offers.length > 0 && (
            <span className="o-mono ml-1.5 text-[10px] text-slate-dim">{offers.length}</span>
          )}
        </Chip>
        <Chip active={filter === "unlinked"} onClick={() => setFilter("unlinked")}>
          Bez powiązania
          {unlinkedCount > 0 && (
            <span className="o-mono ml-1.5 rounded-[5px] bg-[rgba(255,133,99,.16)] px-1.5 py-[1px] text-[10px] text-coral">
              {unlinkedCount}
            </span>
          )}
        </Chip>

        <div className="relative ml-2 min-w-0 flex-1">
          <SearchIcon
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-dim"
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Szukaj po nazwie, numerze oferty lub sygnaturze…"
            aria-label="Szukaj w asortymencie"
            className="w-full rounded-[7px] border border-line bg-ink-raised py-[5px] pl-7 pr-3 text-[11.5px] text-white outline-none placeholder:text-slate-dim focus:border-teal-bright"
          />
        </div>

        {suggestedCount > 0 && (
          <MiniButton
            icon={<LinkIcon size={13} />}
            onClick={() => relinkMutation.mutate()}
            disabled={relinkMutation.isPending}
          >
            {relinkMutation.isPending ? "Wiążę…" : `Dowiąż po sygnaturze (${suggestedCount})`}
          </MiniButton>
        )}
        <Button
          icon={<RefreshIcon size={13} />}
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
        >
          {syncMutation.isPending ? "Pobieram…" : "Pobierz z Allegro"}
        </Button>
      </div>

      {/* Pasek zaznaczenia - pojawia się dopiero, gdy jest co importować. */}
      {pickedList.length > 0 && (
        <div className="flex items-center gap-3 border-b border-line bg-panel-2 px-[22px] py-2.5">
          <span className="text-[12px] text-white">
            Zaznaczono {pickedList.length} ofert(y)
          </span>
          <MiniButton onClick={() => setPicked(new Set())}>Odznacz</MiniButton>
          <div className="ml-auto">
            <Button
              icon={<PlusIcon size={13} />}
              onClick={() => importMutation.mutate(pickedList)}
              disabled={importMutation.isPending}
            >
              {importMutation.isPending ? "Zakładam…" : "Załóż w magazynie i powiąż"}
            </Button>
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-[22px] py-4">
        {catalog.isLoading && <SkeletonRows rows={5} />}

        {!catalog.isLoading && offers.length === 0 && (
          <EmptyState
            pose="idle"
            title="Katalog jest pusty"
            description="Kliknij „Pobierz z Allegro”, żeby ściągnąć swój asortyment. Dopiero wtedy da się powiązać oferty z magazynem, nie czekając, aż sprzedadzą się bez powiązania."
          />
        )}

        {!catalog.isLoading && offers.length > 0 && (
          <>
            {unlinkedCount > 0 && filter === "all" && (
              <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-line bg-panel-2 px-3.5 py-3 shadow-[inset_3px_0_0_var(--coral)]">
                <AlertIcon size={14} className="mt-[2px] shrink-0 text-coral" />
                <p className="text-[12px] leading-[1.6] text-slate">
                  <span className="text-white">
                    {unlinkedCount} ofert nie rusza magazynu.
                  </span>{" "}
                  Zaznacz je i załóż produkty jednym kliknięciem albo przypisz składniki
                  ręcznie, jeśli oferta jest zestawem.
                </p>
              </div>
            )}

            {importable.length > 0 && (
              <div className="mb-2 flex items-center gap-2">
                <MiniButton
                  onClick={() =>
                    setPicked(new Set(importable.map((offer) => offer.external_id)))
                  }
                >
                  Zaznacz wszystkie bez powiązania ({importable.length})
                </MiniButton>
              </div>
            )}

            <SectionLabel>
              {filter === "unlinked" ? "Oferty bez powiązania" : "Asortyment Allegro"}
            </SectionLabel>

            {visible.length === 0 ? (
              <div className="mt-2">
                <EmptyState
                  pose="happy"
                  title={
                    filter === "unlinked"
                      ? "Każda oferta zdejmuje stan"
                      : "Nic nie pasuje do wyszukiwania"
                  }
                  description={
                    filter === "unlinked"
                      ? "Cały pobrany asortyment jest powiązany z magazynem."
                      : "Zmień frazę albo wyczyść pole wyszukiwania."
                  }
                />
              </div>
            ) : (
              <div className="mt-2 flex flex-col gap-2">
                {visible.map((offer) => {
                  const badge = LINK_BADGE[offer.link_type];
                  const selectable = !offer.is_linked;
                  const checked = picked.has(offer.external_id);

                  return (
                    <div
                      key={`${offer.marketplace}-${offer.external_id}`}
                      className={`flex items-center gap-3 rounded-lg border border-line bg-panel-2 px-3.5 py-3 ${
                        offer.is_linked ? "" : "shadow-[inset_3px_0_0_var(--coral)]"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!selectable}
                        onChange={() => togglePicked(offer.external_id)}
                        aria-label={`Zaznacz ofertę ${offer.name}`}
                        className="h-[15px] w-[15px] shrink-0 accent-[var(--teal-bright)] disabled:opacity-25"
                      />

                      {offer.image_url ? (
                        <img
                          src={offer.image_url}
                          alt=""
                          className="h-9 w-9 shrink-0 rounded-md border border-line object-cover"
                        />
                      ) : (
                        <div className="h-9 w-9 shrink-0 rounded-md border border-line bg-ink-raised" />
                      )}

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] text-white">{offer.name}</p>
                        <p className="o-mono mt-1 truncate text-[10.5px] text-slate-dim">
                          {offer.external_id}
                          {offer.signature ? ` · sygn. ${offer.signature}` : ""} ·{" "}
                          {offer.available_stock} szt. na Allegro
                          {offer.price !== null ? ` · ${formatCurrency(offer.price)}` : ""}
                        </p>
                        {offer.components.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {offer.components.map((component) => (
                              <span
                                key={component.sku}
                                className="rounded-[6px] border border-line px-2 py-[2px] text-[11px] text-slate"
                              >
                                {component.quantity} × {component.name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <Pill tone={badge.tone}>{badge.label}</Pill>

                      <MiniButton
                        icon={
                          offer.is_linked ? <CheckIcon size={13} /> : <LinkIcon size={13} />
                        }
                        onClick={() => onLinkOffer(offer)}
                      >
                        {offer.is_linked ? "Edytuj składniki" : "Przypisz składniki"}
                      </MiniButton>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

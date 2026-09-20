/**
 * Magazyn - lista ofert wystawionych na marketplace'ach.
 *
 * Ilosc wisi WPROST na ofercie: nie ma osobnych produktow, receptur ani
 * powiazan. Sprzedaz niczego nie zdejmuje - stan zmienia sie wylacznie
 * recznie, bo tylko czlowiek widzi, co naprawde lezy na polce.
 *
 * Dwie liczby stoja obok siebie celowo. "Wystawione" przychodzi z API
 * marketplace i mowi, ile sztuk obiecuje oferta kupujacym. "Na polce"
 * wpisuje sie tutaj. Rozjazd miedzy nimi jest informacja, nie bledem.
 *
 * `quantity_on_hand === null` znaczy "nigdy nie liczono" i jest czym
 * innym niz 0 ("policzylem, nie ma") - dlatego pusty stan pokazuje
 * przycisk "Wpisz stan", a nie stepper od zera.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClockIcon, RefreshIcon, SearchIcon } from "../icons";
import {
  Button,
  EmptyState,
  ErrorState,
  MarketplaceBadge,
  MiniButton,
  SkeletonRows,
  Stepper,
} from "../components/ui";
import { Modal } from "../components/Modal";
import { useToast } from "../lib/toast";
import { formatCurrency, formatDateTime, formatPlural } from "../lib/format";
import type { MarketplaceOffer, OfferRef } from "../types/api";

/** Oferta nie ma jednego identyfikatora - kanal i numer dopiero razem. */
export function offerKey(offer: { marketplace: string; external_id: string }): string {
  return `${offer.marketplace}:${offer.external_id}`;
}

function toRef(offer: MarketplaceOffer): OfferRef {
  return { marketplace: offer.marketplace, externalId: offer.external_id };
}

interface MagazynScreenProps {
  /** Klucz oferty z palety polecen - wiersz podswietla sie i przewija. */
  focusOffer: string | null;
  onFocusHandled: () => void;
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
      <span className="text-[11px] text-text-3">{hint}</span>
    </label>
  );
}

function HistoryModal({
  offer,
  onClose,
}: {
  offer: MarketplaceOffer | null;
  onClose: () => void;
}) {
  const historyQuery = useQuery({
    queryKey: ["offer-history", offer ? offerKey(offer) : null],
    enabled: offer !== null,
    queryFn: async () => {
      const result = await window.ordly.stock.history(toRef(offer as MarketplaceOffer));
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  return (
    <Modal
      open={offer !== null}
      onClose={onClose}
      title="Historia stanu"
      subtitle={offer?.name ?? ""}
      width={520}
    >
      {historyQuery.isLoading && <span className="o-skeleton-bar h-24 w-full" />}
      {historyQuery.data?.length === 0 && (
        <p className="text-[12.5px] text-text-3">
          Stan tej oferty nie był jeszcze wpisywany.
        </p>
      )}
      <div className="flex flex-col">
        {(historyQuery.data ?? []).map((movement, index) => (
          <div
            key={`${movement.occurred_at}-${index}`}
            className="flex items-center gap-3 border-b border-line py-2.5 text-[12.5px] last:border-b-0"
          >
            <span className="o-mono w-[100px] shrink-0 text-[10.5px] text-text-3">
              {formatDateTime(movement.occurred_at)}
            </span>
            {/* Pierwszy wpis nie ma "o ile" - nie bylo od czego liczyc. */}
            <span
              className={`o-mono w-12 shrink-0 text-right ${
                movement.change === null
                  ? "text-text-3"
                  : movement.change < 0
                    ? "text-coral"
                    : "text-teal"
              }`}
            >
              {movement.change === null
                ? "—"
                : movement.change > 0
                  ? `+${movement.change}`
                  : movement.change}
            </span>
            <span className="o-mono w-14 shrink-0 text-right text-text">
              {movement.quantity_after} szt.
            </span>
            <span className="min-w-0 flex-1 truncate text-text-2">{movement.reason}</span>
          </div>
        ))}
      </div>
    </Modal>
  );
}

/** Powod wpisywany do historii, gdy uzytkownik nie poda swojego. */
const DEFAULT_REASON = "Inwentaryzacja";

/**
 * Reczny wpis stanu.
 *
 * Podglad "12 -> 40 szt." jest czescia funkcji, nie ozdoba: wpis
 * nadpisuje poprzedni stan bez pytania, wiec skutek musi byc widoczny
 * PRZED zapisem.
 */
function QuantityModal({
  offer,
  onClose,
}: {
  offer: MarketplaceOffer | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [quantity, setQuantity] = React.useState("");
  const [reason, setReason] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Zaleznosc po kluczu, nie po calym obiekcie: lista odswieza sie w tle
  // i podmienia referencje `offer`, co przy `[offer]` czyscilo by pole
  // w trakcie wpisywania liczby.
  const key = offer ? offerKey(offer) : null;
  const current = offer?.quantity_on_hand ?? null;

  React.useEffect(() => {
    if (key === null) return;
    setQuantity(current === null ? "" : String(current));
    setReason("");
    // Fokus jawnie na pole liczby: `Modal` po otwarciu ustawia fokus na
    // pierwszym elemencie dialogu. Efekt rodzica idzie po efekcie
    // dziecka, wiec to ustawienie jest tym ostatnim.
    inputRef.current?.focus();
    inputRef.current?.select();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const parsed = Number.parseInt(quantity, 10);
  const amount = Number.isNaN(parsed) ? null : parsed;

  let problem: string | null = null;
  if (amount !== null && amount < 0) {
    problem = "Stan nie może być ujemny.";
  } else if (amount !== null && amount === current) {
    problem = "Ta wartość niczego nie zmienia.";
  }

  const canSubmit = offer !== null && amount !== null && problem === null;

  const mutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.setQuantity(toRef(offer as MarketplaceOffer), {
        quantity: amount as number,
        reason: reason.trim() || DEFAULT_REASON,
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: ["offers"] });
      void queryClient.invalidateQueries({ queryKey: ["offer-history"] });
      toast.success(
        "Stan zapisany",
        `${updated.name} · ${current === null ? "—" : `${current} szt.`} → ${
          updated.quantity_on_hand ?? 0
        } szt.`
      );
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zapisać stanu",
        error instanceof Error ? error.message : "Odśwież listę i spróbuj ponownie."
      );
    },
  });

  return (
    <Modal
      open={offer !== null}
      onClose={onClose}
      title="Stan na półce"
      subtitle={offer?.name ?? ""}
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Anuluj
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!canSubmit || mutation.isPending}
          >
            {mutation.isPending ? "Zapisuję…" : "Zapisz stan"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Liczba sztuk" hint="Tyle sztuk faktycznie leży na półce">
          <input
            ref={inputRef}
            type="number"
            min={0}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            onFocus={(event) => event.target.select()}
            onKeyDown={(event) => {
              if (event.key === "Enter" && canSubmit && !mutation.isPending) {
                event.preventDefault();
                mutation.mutate();
              }
            }}
            className="o-mono w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none focus:border-teal"
          />
        </Field>

        <Field label="Powód" hint={`Trafia do historii. Puste = „${DEFAULT_REASON}”`}>
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={DEFAULT_REASON}
            className="w-full rounded-sm border border-line bg-base px-3 py-2.5 text-[12.5px] text-text outline-none placeholder:text-text-3 focus:border-teal"
          />
        </Field>

        <div className="rounded-sm border border-line bg-base px-3 py-2.5">
          {problem ? (
            <p className="text-[12px] text-coral">{problem}</p>
          ) : amount === null ? (
            <p className="text-[12px] text-text-3">Wpisz liczbę, żeby zobaczyć wynik.</p>
          ) : (
            <p className="o-mono text-[12.5px] text-text-2">
              {current === null ? "nie liczono" : `${current} szt.`}{" "}
              <span className="text-text-3">→</span>{" "}
              <span className="text-teal">{amount} szt.</span>
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}

export function MagazynScreen({ focusOffer, onFocusHandled }: MagazynScreenProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = React.useState("");
  const [historyKey, setHistoryKey] = React.useState<string | null>(null);
  const [quantityKey, setQuantityKey] = React.useState<string | null>(null);
  const [highlight, setHighlight] = React.useState<string | null>(null);
  const rowRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["offers"],
    queryFn: async () => {
      const result = await window.ordly.stock.offers();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const offers = React.useMemo(() => data ?? [], [data]);

  const syncMutation = useMutation({
    mutationFn: async () => {
      const result = await window.ordly.stock.sync();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (summary) => {
      void queryClient.invalidateQueries({ queryKey: ["offers"] });
      // Same liczby, nie "gotowe": po synchronizacji czlowiek chce
      // wiedziec, czy to, co przed chwila wystawil, faktycznie doszlo.
      const parts = [formatPlural(summary.fetched, ["oferta", "oferty", "ofert"])];
      if (summary.added > 0) parts.push(`+${summary.added} nowych`);
      if (summary.removed > 0) parts.push(`−${summary.removed} zniknęło`);
      toast.success("Katalog pobrany", parts.join(" · "));
    },
    onError: (mutationError) => {
      toast.error(
        "Nie udało się pobrać katalogu",
        mutationError instanceof Error
          ? mutationError.message
          : "Sprawdź połączenie z Allegro w Ustawieniach."
      );
    },
  });

  /** Klikniecie w "+"/"−" przy stepperze - zapis bez otwierania modala. */
  const stepMutation = useMutation({
    mutationFn: async ({ offer, next }: { offer: MarketplaceOffer; next: number }) => {
      const result = await window.ordly.stock.setQuantity(toRef(offer), {
        quantity: next,
        reason: "Korekta ręczna",
      });
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["offers"] });
      void queryClient.invalidateQueries({ queryKey: ["offer-history"] });
    },
    onError: (mutationError) => {
      toast.error(
        "Nie udało się zapisać stanu",
        mutationError instanceof Error
          ? mutationError.message
          : "Odśwież listę i spróbuj ponownie."
      );
    },
  });

  React.useEffect(() => {
    if (!focusOffer) return;
    setHighlight(focusOffer);
    const scrollTimer = window.setTimeout(() => {
      rowRefs.current[focusOffer]?.scrollIntoView({ block: "center" });
    }, 60);
    const clearTimer = window.setTimeout(() => setHighlight(null), 2200);
    onFocusHandled();
    return () => {
      window.clearTimeout(scrollTimer);
      window.clearTimeout(clearTimer);
    };
  }, [focusOffer, onFocusHandled]);

  const visible = React.useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return offers;
    return offers.filter(
      (offer) =>
        offer.name.toLowerCase().includes(needle) ||
        offer.external_id.toLowerCase().includes(needle) ||
        (offer.signature ?? "").toLowerCase().includes(needle)
    );
  }, [offers, search]);

  const historyOffer = offers.find((offer) => offerKey(offer) === historyKey) ?? null;
  const quantityOffer = offers.find((offer) => offerKey(offer) === quantityKey) ?? null;

  // Znaczniki z API sa w ISO ze strefa "Z", wiec najswiezszy jest
  // najwiekszy leksykograficznie - nie ma po co parsowac calej listy.
  const lastSynced = offers.reduce<string | null>(
    (newest, offer) =>
      offer.synced_at !== null && (newest === null || offer.synced_at > newest)
        ? offer.synced_at
        : newest,
    null
  );

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać ofert"
        detail={`Pi nie odpowiedziało na zapytanie o listę ofert. ${
          error instanceof Error ? error.message : ""
        }`}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-[22px] py-[11px]">
        <div className="relative min-w-0 flex-1">
          <SearchIcon
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-3"
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Szukaj po nazwie, numerze oferty lub sygnaturze…"
            aria-label="Szukaj w ofertach"
            className="w-full rounded-[7px] border border-line bg-base py-[5px] pl-7 pr-3 text-[11.5px] text-text outline-none placeholder:text-text-3 focus:border-teal"
          />
        </div>

        <span className="o-mono text-[10.5px] text-text-3">
          {lastSynced ? `Pobrano ${formatDateTime(lastSynced)}` : "Katalog jeszcze niepobrany"}
        </span>

        <Button
          icon={<RefreshIcon size={13} />}
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
        >
          {syncMutation.isPending ? "Pobieram…" : "Synchronizuj"}
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-[22px] py-4">
        {isLoading && <SkeletonRows rows={6} />}

        {!isLoading && offers.length === 0 && (
          <EmptyState
            title="Nie ma jeszcze żadnych ofert"
            description="Kliknij „Synchronizuj”, żeby pobrać to, co masz wystawione na marketplace'ach."
          />
        )}

        {!isLoading && offers.length > 0 && visible.length === 0 && (
          <EmptyState
            title="Nic nie pasuje do wyszukiwania"
            description="Zmień frazę albo wyczyść pole wyszukiwania."
          />
        )}

        {!isLoading && visible.length > 0 && (
          <div className="flex flex-col gap-2">
            {visible.map((offer) => {
              const key = offerKey(offer);
              const onHand = offer.quantity_on_hand;
              return (
                <div
                  key={key}
                  ref={(element) => {
                    rowRefs.current[key] = element;
                  }}
                  className={`flex items-center gap-3 rounded-lg border border-line px-3.5 py-3 transition-colors duration-150 ease-ordly ${
                    highlight === key ? "bg-teal-glow" : "bg-panel-2"
                  }`}
                >
                  {offer.image_url ? (
                    <img
                      src={offer.image_url}
                      alt=""
                      className="h-10 w-10 shrink-0 rounded-md border border-line object-cover"
                    />
                  ) : (
                    <div className="h-10 w-10 shrink-0 rounded-md border border-line bg-base" />
                  )}

                  <MarketplaceBadge marketplace={offer.marketplace} />

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-text">{offer.name}</p>
                    <p className="o-mono mt-1 truncate text-[10.5px] text-text-3">
                      {offer.external_id}
                      {offer.signature ? ` · sygn. ${offer.signature}` : ""} · wystawione{" "}
                      {offer.available_stock} szt.
                    </p>
                  </div>

                  {/* Oferta bez ceny to na Allegro wariant z cennikiem -
                      kreska mowi "tu nie ma jednej kwoty", a nie "0 zl". */}
                  <span className="o-mono w-[88px] shrink-0 text-right text-[12.5px] text-text">
                    {offer.price === null ? "—" : formatCurrency(offer.price)}
                  </span>

                  <div className="w-[118px] shrink-0 text-right">
                    {onHand === null ? (
                      <MiniButton onClick={() => setQuantityKey(key)}>Wpisz stan</MiniButton>
                    ) : (
                      <Stepper
                        value={onHand}
                        disabled={stepMutation.isPending}
                        onDecrease={() =>
                          stepMutation.mutate({ offer, next: Math.max(0, onHand - 1) })
                        }
                        onIncrease={() => stepMutation.mutate({ offer, next: onHand + 1 })}
                        onEdit={() => setQuantityKey(key)}
                      />
                    )}
                  </div>

                  <MiniButton
                    icon={<ClockIcon size={13} />}
                    aria-label={`Historia stanu ${offer.name}`}
                    onClick={() => setHistoryKey(key)}
                  >
                    Historia
                  </MiniButton>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <HistoryModal offer={historyOffer} onClose={() => setHistoryKey(null)} />
      <QuantityModal offer={quantityOffer} onClose={() => setQuantityKey(null)} />
    </div>
  );
}

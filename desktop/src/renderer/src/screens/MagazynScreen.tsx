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
 *
 * Produkty glowne i podprodukty: butelka 10 ml sprzedaje sie zawsze
 * z nakretka i kroplomierzem, wiec te dwa sa jej PODPRODUKTAMI. Glowna
 * lista pokazuje wtedy sama butelke - nakretka i kroplomierz siedza pod
 * strzalka rozwijania, zeby nie zasmiecac widoku trzema wierszami o tym
 * samym. Filtry "Ponizej progu" i "Zerowy stan" celowo lamia te zasade
 * i pokazuja podprodukty wprost: ich zadaniem jest znalezc to, co sie
 * konczy, a schowana nakretka skonczylaby sie po cichu.
 *
 * Warunki na `parent_sku` sa CELOWO luzne (`!item.parent_sku`), a nie
 * `=== null`: starszy backend tego pola w ogole nie zwraca, a wtedy
 * `undefined === null` jest falszem i cala lista magazynowa zniknelaby
 * z ekranu. Brak pola ma znaczyc "produkt samodzielny", bo dokladnie
 * tym byly wszystkie produkty przed ta zmiana.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronIcon, ClockIcon, LinkIcon, PlusIcon, TrashIcon } from "../icons";
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
import { ConfirmDialog, Modal } from "../components/Modal";
import { Mascot } from "../components/Mascot";
import { PowiazaniaOfertView } from "./PowiazaniaOfertView";
import { useToast } from "../lib/toast";
import { formatDateTime, formatPlural, formatStock } from "../lib/format";
import type { StockItem } from "../types/api";

type StockFilter = "all" | "low" | "zero";
type MagazynTab = "items" | "links";

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
            key={`${movement.occurred_at}-${index}`}
            className="flex items-center gap-3 border-b border-line py-2.5 text-[12.5px] last:border-b-0"
          >
            <span className="o-mono w-[100px] shrink-0 text-[10.5px] text-slate-dim">
              {formatDateTime(movement.occurred_at)}
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

/**
 * Potwierdzenie usuniecia pozycji magazynowej.
 *
 * Komunikat wylicza SKUTKI zamiast pytac "czy na pewno": stan, ktory
 * zniknie z ewidencji, podprodukty, ktore przestana schodzic razem
 * z produktem, i receptury ofert, z ktorych produkt wypadnie. To
 * jedyna operacja magazynowa bez sladu w historii - wpisy ruchow wisza
 * na SKU i znikaja razem z nim, wiec po fakcie nie ma juz gdzie tego
 * przeczytac.
 *
 * Liczba receptur idzie z tego samego zapytania, ktore karmi zakladke
 * "Powiazania ofert" (klucz `offer-recipes`), wiec zwykle siedzi juz
 * w cache. Kiedy jeszcze leci albo sie nie powiodlo, dialog mowi to
 * wprost - milczenie czytaloby sie jako "zadna receptura", a to
 * najgorszy moment na zgadywanie.
 */
function DeleteProductDialog({
  item,
  subItems,
  onClose,
}: {
  item: StockItem | null;
  subItems: StockItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const recipesQuery = useQuery({
    queryKey: ["offer-recipes"],
    enabled: item !== null,
    queryFn: async () => {
      const result = await window.ordly.stock.recipes();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });

  const recipeCount = React.useMemo(() => {
    if (!item) return 0;
    return (recipesQuery.data ?? []).filter((recipe) =>
      recipe.components.some((component) => component.sku === item.sku)
    ).length;
  }, [item, recipesQuery.data]);

  const mutation = useMutation({
    mutationFn: async (sku: string) => {
      const result = await window.ordly.stock.remove(sku);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (deletion) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["offer-recipes"] });
      void queryClient.invalidateQueries({ queryKey: ["unmapped-offers"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      const skutki = [`${deletion.sku} zniknął z magazynu`];
      if (deletion.detached_sub_items.length > 0) {
        skutki.push(
          `odłączono ${formatPlural(deletion.detached_sub_items.length, [
            "podprodukt",
            "podprodukty",
            "podproduktów",
          ])}`
        );
      }
      if (deletion.removed_offer_links > 0) {
        skutki.push(
          `wypadł z ${formatPlural(deletion.removed_offer_links, [
            "receptury",
            "receptur",
            "receptur",
          ])}`
        );
      }
      toast.success("Usunięto produkt", skutki.join(" · "));
      onClose();
    },
    onError: (error) => {
      toast.error(
        "Nie udało się usunąć produktu",
        error instanceof Error ? error.message : "Odśwież listę i spróbuj ponownie."
      );
    },
  });

  const zdania: string[] = [];
  if (item) {
    zdania.push(
      `„${item.name}" (${item.sku}) zniknie z magazynu razem z całą historią ruchów. Tego nie da się cofnąć.`
    );
    if (item.stock > 0) {
      zdania.push(`Stan ${item.stock} szt. przestanie być liczony.`);
    }
    if (subItems.length > 0) {
      const lista = subItems.map((sub) => sub.sku).join(", ");
      zdania.push(
        subItems.length === 1
          ? `Podprodukt ${lista} zostanie w magazynie, ale przestanie schodzić razem z tym produktem.`
          : `Podprodukty (${lista}) zostaną w magazynie, ale przestaną schodzić razem z tym produktem.`
      );
    }
    if (item.parent_sku) {
      zdania.push(`Produkt główny ${item.parent_sku} zostaje bez zmian.`);
    }
    if (recipesQuery.isLoading) {
      zdania.push("Sprawdzam jeszcze, w ilu recepturach ofert ten produkt występuje…");
    } else if (recipesQuery.isError) {
      zdania.push(
        "Nie udało się sprawdzić receptur ofert - jeśli produkt w którejś jest, wypadnie z niej razem z usunięciem."
      );
    } else if (recipeCount > 0) {
      zdania.push(
        `Produkt wypadnie z ${formatPlural(recipeCount, [
          "receptury",
          "receptur",
          "receptur",
        ])} ofert - ich sprzedaż przestanie ruszać magazyn.`
      );
    }
  }

  return (
    <ConfirmDialog
      open={item !== null}
      title="Usunąć produkt z magazynu?"
      message={zdania.join(" ")}
      confirmLabel="Usuń produkt"
      pending={mutation.isPending}
      onConfirm={() => item && mutation.mutate(item.sku)}
      onClose={onClose}
    />
  );
}

/**
 * Zarzadzanie podproduktami jednego produktu glownego.
 *
 * Dlaczego modal od strony PRODUKTU GLOWNEGO, a nie pole "produkt
 * glowny" w edycji podproduktu: gdy produkt zostanie podproduktem,
 * znika z glownej listy - nie byloby wiersza, z ktorego mozna by go
 * odwiazac. Stad oba kierunki (dodaj / odlacz) siedza tutaj, w jednym
 * miejscu, przy produkcie, ktory na liscie zostaje.
 *
 * Lista kandydatow jest filtrowana po tych samych regulach, ktore
 * egzekwuje backend (jeden poziom zagniezdzenia) - front tylko chowa
 * niedozwolone opcje, decyduje serwer.
 */
function SubItemsModal({
  parent,
  items,
  onClose,
}: {
  parent: StockItem | null;
  items: StockItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [pickedSku, setPickedSku] = React.useState("");

  React.useEffect(() => {
    setPickedSku("");
  }, [parent?.sku]);

  const subItems = React.useMemo(
    () => (parent ? items.filter((item) => item.parent_sku === parent.sku) : []),
    [items, parent]
  );

  const candidates = React.useMemo(() => {
    if (!parent) return [];
    const parents = new Set(
      items.map((item) => item.parent_sku).filter((sku): sku is string => sku !== null)
    );
    return items.filter(
      (item) =>
        item.sku !== parent.sku && !item.parent_sku && !parents.has(item.sku)
    );
  }, [items, parent]);

  const mutation = useMutation({
    mutationFn: async ({ sku, parentSku }: { sku: string; parentSku: string | null }) => {
      const result = await window.ordly.stock.setParent(sku, parentSku);
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      setPickedSku("");
      toast.success(
        item.parent_sku ? "Dodano podprodukt" : "Odłączono podprodukt",
        item.parent_sku
          ? `${item.sku} będzie schodzić razem z ${item.parent_sku}`
          : `${item.sku} jest znowu samodzielnym produktem`
      );
    },
    onError: (error) => {
      toast.error(
        "Nie udało się zmienić powiązania",
        error instanceof Error ? error.message : "Spróbuj ponownie."
      );
    },
  });

  return (
    <Modal
      open={parent !== null}
      onClose={onClose}
      title="Podprodukty"
      subtitle={parent ? `${parent.name} · ${parent.sku}` : ""}
      width={520}
      footer={
        <Button variant="ghost" onClick={onClose}>
          Zamknij
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-[12px] leading-relaxed text-slate-dim">
          Podprodukty schodzą ze stanu razem z tym produktem, sztuka za sztukę, przy
          każdej sprzedaży - niezależnie od oferty i serwisu. Ręczne korekty stanu
          (dostawa, inwentaryzacja) ich nie ruszają.
        </p>

        <div className="flex flex-col">
          {subItems.length === 0 && (
            <p className="text-[12.5px] text-slate-dim">
              Ten produkt nie ma jeszcze podproduktów.
            </p>
          )}
          {subItems.map((item) => (
            <div
              key={item.sku}
              className="flex items-center gap-3 border-b border-line py-2.5 text-[12.5px] last:border-b-0"
            >
              <span className="min-w-0 flex-1 truncate text-white">{item.name}</span>
              <span className="o-mono shrink-0 text-[11px] text-slate-dim">{item.sku}</span>
              <span className="o-mono w-16 shrink-0 text-right text-slate">
                {item.stock} szt.
              </span>
              <MiniButton
                onClick={() => mutation.mutate({ sku: item.sku, parentSku: null })}
                disabled={mutation.isPending}
              >
                Odłącz
              </MiniButton>
            </div>
          ))}
        </div>

        <div className="flex items-end gap-2 border-t border-line pt-4">
          <Field
            label="Dodaj podprodukt"
            hint="Widać tylko produkty samodzielne - zagnieżdżenie jest jednopoziomowe"
          >
            <select
              value={pickedSku}
              onChange={(event) => setPickedSku(event.target.value)}
              className="w-full rounded-sm border border-line bg-ink-raised px-3 py-2.5 text-[12.5px] text-white outline-none focus:border-teal-bright"
            >
              <option value="">Wybierz produkt…</option>
              {candidates.map((item) => (
                <option key={item.sku} value={item.sku}>
                  {item.name} ({item.sku})
                </option>
              ))}
            </select>
          </Field>
          <div className="pb-[22px]">
            <Button
              onClick={() =>
                mutation.mutate({ sku: pickedSku, parentSku: parent?.sku ?? null })
              }
              disabled={pickedSku === "" || mutation.isPending}
            >
              Dodaj
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

/**
 * Przelacznik "Produkty / Powiazania ofert". Licznik przy powiazaniach
 * jest istotny: oferta bez receptury sprzedaje sie, nie ruszajac stanow,
 * a to widac dopiero po tym, ze magazyn stoi w miejscu.
 */
function TabBar({
  tab,
  onChange,
  unmappedCount,
}: {
  tab: MagazynTab;
  onChange: (tab: MagazynTab) => void;
  unmappedCount: number;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-line px-[22px] py-[9px]">
      <Chip active={tab === "items"} onClick={() => onChange("items")}>
        Produkty
      </Chip>
      <Chip active={tab === "links"} onClick={() => onChange("links")}>
        Powiązania ofert
        {unmappedCount > 0 && (
          <span className="o-mono ml-1.5 rounded-[5px] bg-[rgba(255,133,99,.16)] px-1.5 py-[1px] text-[10px] text-coral">
            {unmappedCount}
          </span>
        )}
      </Chip>
    </div>
  );
}

export function MagazynScreen({ focusSku, onFocusHandled }: MagazynScreenProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = React.useState<MagazynTab>("items");
  const [filter, setFilter] = React.useState<StockFilter>("all");
  const [newOpen, setNewOpen] = React.useState(false);
  const [historySku, setHistorySku] = React.useState<string | null>(null);
  const [subItemsSku, setSubItemsSku] = React.useState<string | null>(null);
  const [deleteSku, setDeleteSku] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
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

  // Licznik na zakladce - jedyny sygnal, ze sprzedaz omija magazyn.
  const unmappedQuery = useQuery({
    queryKey: ["unmapped-offers"],
    queryFn: async () => {
      const result = await window.ordly.stock.unmappedOffers();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
  });
  const unmappedCount = unmappedQuery.data?.length ?? 0;

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

  const items = React.useMemo(() => data ?? [], [data]);

  /** Podprodukty pogrupowane po SKU produktu glownego. */
  const subItemsByParent = React.useMemo(() => {
    const grouped = new Map<string, StockItem[]>();
    for (const item of items) {
      if (!item.parent_sku) continue;
      const bucket = grouped.get(item.parent_sku);
      if (bucket) bucket.push(item);
      else grouped.set(item.parent_sku, [item]);
    }
    return grouped;
  }, [items]);

  // "Wszystkie" pokazuje hierarchie (same produkty glowne i samodzielne).
  // Filtry problemow pokazuja wszystko, co pasuje - lacznie z
  // podproduktami, bo po to sie ich uzywa.
  const visible =
    filter === "all"
      ? items.filter((item) => !item.parent_sku)
      : items.filter((item) =>
          filter === "low" ? item.is_low_stock : item.stock === 0
        );

  const subItemsParent =
    subItemsSku === null ? null : (items.find((i) => i.sku === subItemsSku) ?? null);

  const deleteTarget =
    deleteSku === null ? null : (items.find((i) => i.sku === deleteSku) ?? null);

  function toggleExpanded(sku: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(sku)) next.delete(sku);
      else next.add(sku);
      return next;
    });
  }

  if (tab === "links") {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <TabBar tab={tab} onChange={setTab} unmappedCount={unmappedCount} />
        <PowiazaniaOfertView />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <TabBar tab={tab} onChange={setTab} unmappedCount={unmappedCount} />
        <ErrorState
          title="Nie udało się pobrać magazynu"
          detail={`Pi nie odpowiedziało na zapytanie o stan magazynowy. ${
            error instanceof Error ? error.message : ""
          }`}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TabBar tab={tab} onChange={setTab} unmappedCount={unmappedCount} />
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
                {["Produkt", "SKU", "Zapas", "Korekta", "Status", "Akcje"].map(
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
                const subItems = subItemsByParent.get(item.sku) ?? [];
                const isExpanded = expanded.has(item.sku);
                return (
                  <React.Fragment key={item.sku}>
                  <tr
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
                        {subItems.length > 0 ? (
                          <button
                            type="button"
                            onClick={() => toggleExpanded(item.sku)}
                            aria-expanded={isExpanded}
                            aria-label={
                              isExpanded
                                ? `Zwiń podprodukty ${item.name}`
                                : `Rozwiń podprodukty ${item.name}`
                            }
                            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] text-slate-dim transition-colors duration-150 ease-ordly hover:bg-panel-2 hover:text-white"
                          >
                            <ChevronIcon
                              size={13}
                              className={`transition-transform duration-150 ease-ordly ${
                                isExpanded ? "rotate-90" : ""
                              }`}
                            />
                          </button>
                        ) : (
                          <span className="w-5 shrink-0" />
                        )}
                        {item.is_low_stock && <Mascot pose="think" size={22} floaty={false} />}
                        {item.name}
                        {subItems.length > 0 && (
                          <span className="o-mono shrink-0 rounded-[5px] bg-teal-dim px-1.5 py-[1px] text-[10px] text-teal-bright">
                            +{subItems.length}{" "}
                            {subItems.length === 1 ? "podprodukt" : "podprodukty"}
                          </span>
                        )}
                        {item.parent_sku ? (
                          <span className="o-mono shrink-0 text-[10px] text-slate-dim">
                            podprodukt {item.parent_sku}
                          </span>
                        ) : null}
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
                      <span className="flex items-center justify-end gap-1.5">
                        {!item.parent_sku && (
                          <MiniButton
                            icon={<LinkIcon size={13} />}
                            onClick={() => setSubItemsSku(item.sku)}
                          >
                            Podprodukty
                          </MiniButton>
                        )}
                        <MiniButton
                          icon={<ClockIcon size={13} />}
                          onClick={() => setHistorySku(item.sku)}
                        >
                          Historia
                        </MiniButton>
                        <MiniButton
                          icon={<TrashIcon size={13} />}
                          aria-label={`Usuń produkt ${item.name}`}
                          onClick={() => setDeleteSku(item.sku)}
                          className="hover:!border-coral hover:!text-coral"
                        >
                          Usuń
                        </MiniButton>
                      </span>
                    </td>
                  </tr>
                  {isExpanded &&
                    subItems.map((sub) => (
                      <tr key={sub.sku} className="bg-panel-2/40">
                        <td className="border-b border-line py-2.5 pl-[52px] pr-[22px] text-[12.5px] text-slate">
                          <span className="flex items-center gap-2.5">
                            {sub.is_low_stock && (
                              <Mascot pose="think" size={18} floaty={false} />
                            )}
                            {sub.name}
                          </span>
                        </td>
                        <td className="o-mono border-b border-line px-3 py-2.5 text-[11.5px] text-slate-dim">
                          {sub.sku}
                        </td>
                        <td className="o-mono border-b border-line px-3 py-2.5 text-[11.5px] text-slate">
                          {sub.stock} szt.
                        </td>
                        <td
                          className="border-b border-line px-3 py-2.5 text-[11px] text-slate-dim"
                          colSpan={2}
                        >
                          Schodzi razem z „{item.name}"
                        </td>
                        <td className="border-b border-line px-[22px] py-2.5 text-right">
                          <span className="flex items-center justify-end">
                            <MiniButton
                              icon={<TrashIcon size={13} />}
                              aria-label={`Usuń podprodukt ${sub.name}`}
                              onClick={() => setDeleteSku(sub.sku)}
                              className="hover:!border-coral hover:!text-coral"
                            >
                              Usuń
                            </MiniButton>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <NewProductModal open={newOpen} onClose={() => setNewOpen(false)} />
      <HistoryModal sku={historySku} onClose={() => setHistorySku(null)} />
      <SubItemsModal
        parent={subItemsParent}
        items={items}
        onClose={() => setSubItemsSku(null)}
      />
      <DeleteProductDialog
        item={deleteTarget}
        subItems={deleteTarget ? (subItemsByParent.get(deleteTarget.sku) ?? []) : []}
        onClose={() => setDeleteSku(null)}
      />
    </div>
  );
}

/**
 * Zwroty - dwie sekcje z podzakladkami statusow obslugi (pozycja z Notion
 * "Podzial zwrotow i anulowanych zamowien na osobne podzakladki oraz
 * statusy obslugi"):
 *
 *   Zwroty | Anulowane zamowienia
 *   Zgloszony | W trakcie realizacji | Zakonczony
 *
 * Status obslugi (decyzja D6-a):
 * - zwroty - automatycznie z Allegro (`handling_status` z GET /returns,
 *   ta sama regula co "wymaga dzialania");
 * - anulowane zamowienia - recznie, w wierszu rekordu (nowe startuja jako
 *   "Zgloszony").
 *
 * Karty zwrotow (sekcja 4.4): odznaka kanalu, produkt, wiek zgloszenia.
 * SWIADOMA ROZNICA WOBEC KONCEPCJI: brak przyciskow "Odrzuc / Przyjmij
 * zwrot" - przyjecie zwrotu na Allegro to zwrot pieniedzy, operacja
 * finansowa, ktorej to narzedzie swiadomie nie wykonuje. Zamiast martwego
 * przycisku jest przejscie do panelu Allegro. Patrz
 * [[feedback-no-phantom-features]].
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalIcon } from "../icons";
import {
  Chip,
  EmptyState,
  ErrorState,
  MarketplaceBadge,
  MiniButton,
  Pill,
  SkeletonRows,
} from "../components/ui";
import { formatAge, formatDateTime } from "../lib/format";
import { returnHandlingOf, returnStatusLabel, returnStatusTone } from "../lib/returns";
import {
  CASE_HANDLING_LABEL,
  CustomerCasesPanel,
  type CaseKindChoice,
} from "../components/CustomerCasesPanel";
import type { CaseHandling, CaseKind, CustomerCase } from "../types/api";

const ALLEGRO_RETURNS_URL = "https://allegro.pl/moje-allegro/sprzedaz/zwroty";

type Section = "returns" | "cancelled";

const SECTION_LABEL: Record<Section, string> = {
  returns: "Zwroty",
  cancelled: "Anulowane zamówienia",
};

const HANDLING_TABS: CaseHandling[] = ["REPORTED", "IN_PROGRESS", "DONE"];

/** Anulowania (takze z oddanymi pieniedzmi) - domyslny widok sekcji. */
const CANCELLED_KINDS: CaseKind[] = ["CANCELLATION", "BOTH"];

/**
 * Rejestr trzyma tez zwroty pieniedzy bez anulowania (z procesu zwrotu) -
 * zeby dalo sie je przefiltrowac, sekcja pozwala przelaczyc rodzaj.
 */
const KIND_CHOICES: CaseKindChoice[] = [
  { label: "Rodzaj: anulowania", kinds: CANCELLED_KINDS },
  { label: "Rodzaj: zwroty pieniędzy", kinds: ["REFUND", "BOTH"] },
  { label: "Rodzaj: wszystkie", kinds: [] },
];

/** Pusta lista rodzajow = wszystkie. */
function matchesKinds(item: CustomerCase, kinds: CaseKind[]): boolean {
  return kinds.length === 0 || kinds.includes(item.kind);
}

function useReturns() {
  return useQuery({
    queryKey: ["returns"],
    queryFn: async () => {
      const result = await window.ordly.returns.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });
}

/** Rekordy rejestru (bez filtra statusu) - liczniki podzakladek i dane do kart zwrotow. */
function useAllCases() {
  return useQuery({
    queryKey: ["customer-cases", "all"],
    queryFn: async () => {
      const result = await window.ordly.cases.list({});
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });
}

function ReturnsSection({
  handling,
  casesByOrder,
}: {
  handling: CaseHandling;
  casesByOrder: Map<string, CustomerCase>;
}) {
  const { data, isLoading, isError, error, refetch } = useReturns();
  const visible = (data ?? []).filter((item) => returnHandlingOf(item) === handling);

  if (isError) {
    return (
      <ErrorState
        title="Nie udało się pobrać zwrotów"
        detail={`Pi nie odpowiedziało na zapytanie o zwroty klientów. ${
          error instanceof Error ? error.message : ""
        }`}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <>
      {isLoading && <SkeletonRows rows={4} />}

      {!isLoading && visible.length === 0 && (
        <EmptyState
          prop="box"
          title={`Brak zwrotów: ${CASE_HANDLING_LABEL[handling]}`}
          description={
            handling === "REPORTED"
              ? "Wszystkie zamówienia idą gładko. Ordi da znać, gdy pojawi się nowy zwrot."
              : "Gdy zwrot zmieni status na Allegro, pojawi się w tej zakładce."
          }
        />
      )}

      {visible.map((item) => {
        const record = casesByOrder.get(item.order_external_id);
        return (
          <div
            key={item.external_id}
            className="flex items-center gap-4 rounded-md border border-line bg-panel-2 px-[17px] py-[15px]"
          >
            <MarketplaceBadge marketplace={item.marketplace} />
            <div className="min-w-0 flex-1">
              <h4 className="mb-1 truncate text-[13.5px] font-semibold">
                {item.products_summary}
              </h4>
              <p className="o-mono truncate text-[12px] text-text-3">
                {item.buyer_login} · zgłoszony {formatAge(item.return_date)} ·{" "}
                {formatDateTime(item.return_date)}
              </p>
              {record && (
                <p className="truncate text-[11px] text-text-3">
                  Powód: {record.reason_label}
                  {record.refunded_at
                    ? ` · pieniądze zwrócone ${formatDateTime(record.refunded_at)}`
                    : ""}
                </p>
              )}
            </div>
            <Pill tone={returnStatusTone(item)}>{returnStatusLabel(item)}</Pill>
            <MiniButton
              icon={<ExternalIcon size={13} />}
              onClick={() => window.open(ALLEGRO_RETURNS_URL, "_blank", "noopener,noreferrer")}
            >
              Obsłuż na Allegro
            </MiniButton>
          </div>
        );
      })}

      {visible.length > 0 && (
        <p className="pb-2 pt-1 text-[11.5px] leading-[1.6] text-text-3">
          Status obsługi zwrotu wynika z Allegro. Decyzję o przyjęciu zwrotu i zwrocie pieniędzy
          podejmujesz w panelu Allegro - ORDLY pokazuje stan i pilnuje, żeby żaden zwrot Ci nie
          umknął.
        </p>
      )}
    </>
  );
}

export function ReturnsScreen() {
  const [section, setSection] = React.useState<Section>("returns");
  const [handling, setHandling] = React.useState<CaseHandling>("REPORTED");
  const [kindIndex, setKindIndex] = React.useState(0);
  const selectedKinds = KIND_CHOICES[kindIndex].kinds;
  const returns = useReturns();
  const cases = useAllCases();

  const casesByOrder = React.useMemo(
    () => new Map((cases.data ?? []).map((item) => [item.order_external_id, item])),
    [cases.data]
  );

  /** Licznik przy kazdej podzakladce - liczy to, co zakladka naprawde pokaze. */
  const counts = React.useMemo(() => {
    const result: Record<CaseHandling, number> = { REPORTED: 0, IN_PROGRESS: 0, DONE: 0 };
    if (section === "returns") {
      for (const item of returns.data ?? []) result[returnHandlingOf(item)] += 1;
    } else {
      for (const item of cases.data ?? []) {
        if (matchesKinds(item, selectedKinds)) result[item.handling_status] += 1;
      }
    }
    return result;
  }, [section, returns.data, cases.data, selectedKinds]);

  const sectionCounts: Record<Section, number> = {
    returns: (returns.data ?? []).filter((item) => returnHandlingOf(item) !== "DONE").length,
    cancelled: (cases.data ?? []).filter(
      (item) => CANCELLED_KINDS.includes(item.kind) && item.handling_status !== "DONE"
    ).length,
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      {/* ----------------------------------------------------- sekcje */}
      <div role="tablist" aria-label="Sekcje zwrotów" className="flex gap-5 border-b border-line">
        {(Object.keys(SECTION_LABEL) as Section[]).map((option) => (
          <button
            key={option}
            role="tab"
            aria-selected={section === option}
            onClick={() => setSection(option)}
            className={`-mb-px flex items-center gap-2 border-b-2 pb-2 text-[13px] font-semibold transition-colors ${
              section === option
                ? "border-teal text-text"
                : "border-transparent text-text-3 hover:text-text-2"
            }`}
          >
            {SECTION_LABEL[option]}
            {sectionCounts[option] > 0 && (
              <span className="o-mono text-[10px] opacity-70">{sectionCounts[option]}</span>
            )}
          </button>
        ))}
      </div>

      {/* ---------------------------------------------- podzakladki */}
      <div role="tablist" aria-label="Status obsługi" className="flex flex-wrap gap-2">
        {HANDLING_TABS.map((option) => (
          <Chip
            key={option}
            role="tab"
            aria-selected={handling === option}
            active={handling === option}
            count={counts[option]}
            onClick={() => setHandling(option)}
          >
            {CASE_HANDLING_LABEL[option]}
          </Chip>
        ))}
      </div>

      {section === "returns" ? (
        <ReturnsSection handling={handling} casesByOrder={casesByOrder} />
      ) : (
        <>
          <p className="text-[11.5px] leading-[1.6] text-text-3">
            Jeden rekord na zamówienie - zapisywany automatycznie po anulowaniu albo zwrocie
            pieniędzy. Status obsługi zmieniasz w wierszu. Bez telefonu i e-maila: kontakt przez
            Allegro, po numerze zamówienia.
          </p>
          <CustomerCasesPanel
            kindChoices={KIND_CHOICES}
            kindIndex={kindIndex}
            onKindIndexChange={setKindIndex}
            handlingStatus={handling}
            emptyTitle={`Brak spraw: ${CASE_HANDLING_LABEL[handling]}`}
          />
        </>
      )}
    </div>
  );
}

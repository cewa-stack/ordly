/**
 * Zwroty - karty poziome (sekcja 4.4): odznaka kanalu, numer i produkt,
 * powod i wiek zgloszenia, akcje po prawej.
 *
 * SWIADOMA ROZNICA WOBEC KONCEPCJI: koncepcja pokazuje przyciski
 * "Odrzuć / Przyjmij zwrot". ORDLY ich nie rysuje, bo przyjecie zwrotu
 * na Allegro oznacza zwrot pieniedzy - operacje finansowa, ktorej to
 * narzedzie swiadomie nie wykonuje. Zamiast martwego przycisku jest
 * dzialajace przejscie do panelu Allegro, gdzie decyzje podejmuje
 * czlowiek. Patrz [[feedback-no-phantom-features]].
 */
import { useQuery } from "@tanstack/react-query";
import { ExternalIcon } from "../icons";
import {
  EmptyState,
  ErrorState,
  MarketplaceBadge,
  MiniButton,
  Pill,
  SkeletonRows,
  type PillTone,
} from "../components/ui";
import { formatAge, formatDateTime } from "../lib/format";

/** Statusy zwrotow Allegro - tlumaczone, nie surowe. */
const STATUS_LABEL: Record<string, string> = {
  CREATED: "Zgłoszony",
  COMMISSION_REFUND_CLAIMED: "Prowizja do zwrotu",
  COMMISSION_REFUNDED: "Prowizja zwrócona",
  CANCELLED: "Anulowany",
  REJECTED: "Odrzucony",
};

const STATUS_TONE: Record<string, PillTone> = {
  CREATED: "pack",
  COMMISSION_REFUND_CLAIMED: "warn",
  COMMISSION_REFUNDED: "done",
  CANCELLED: "done",
  REJECTED: "done",
};

const ALLEGRO_RETURNS_URL = "https://allegro.pl/moje-allegro/sprzedaz/zwroty";

export function ReturnsScreen() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["returns"],
    queryFn: async () => {
      const result = await window.ordly.returns.list();
      if (!result.ok) throw new Error(result.message);
      return result.data;
    },
    retry: false,
  });

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
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      {isLoading && <SkeletonRows rows={4} />}

      {!isLoading && (data ?? []).length === 0 && (
        <EmptyState
          pose="happy"
          title="Zero zwrotów"
          description="Wszystkie zamówienia idą gładko. Ordi da znać, gdy pojawi się nowy zwrot."
        />
      )}

      {(data ?? []).map((item) => (
        <div
          key={item.external_id}
          className="flex items-center gap-4 rounded-md border border-line bg-panel-2 px-[17px] py-[15px]"
        >
          <MarketplaceBadge marketplace={item.marketplace} />
          <div className="min-w-0 flex-1">
            <h4 className="o-card-title mb-1 truncate">{item.products_summary}</h4>
            <p className="o-mono truncate text-[12px] text-slate-dim">
              {item.buyer_login} · zgłoszony {formatAge(item.return_date)} ·{" "}
              {formatDateTime(item.return_date)}
            </p>
          </div>
          <Pill tone={STATUS_TONE[item.status] ?? "warn"}>
            {STATUS_LABEL[item.status] ?? item.status}
          </Pill>
          <MiniButton
            icon={<ExternalIcon size={13} />}
            onClick={() => window.open(ALLEGRO_RETURNS_URL, "_blank", "noopener,noreferrer")}
          >
            Obsłuż na Allegro
          </MiniButton>
        </div>
      ))}

      {(data ?? []).length > 0 && (
        <p className="pb-2 pt-1 text-[11.5px] leading-[1.6] text-slate-dim">
          Decyzję o przyjęciu zwrotu i zwrocie pieniędzy podejmujesz w panelu Allegro - ORDLY
          pokazuje stan i pilnuje, żeby żaden zwrot Ci nie umknął.
        </p>
      )}
    </div>
  );
}

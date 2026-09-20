/**
 * Komponenty wspolne (sekcja 7 instrukcji "Nokturn"). Wszystko, co
 * powtarza sie na wiecej niz jednym ekranie, mieszka TUTAJ - ekrany nie
 * duplikuja stylow.
 *
 * Nazwy wariantow sa zawsze prefiksowane nazwa bloku (`pill-hot`, a nie
 * samo `hot`) - to wniosek z prawdziwego bledu, gdzie klasa `.unread`
 * znaczyla dwie rozne rzeczy naraz i karty mobilne zapadly sie do
 * rozmiaru kropki.
 */
import * as React from "react";
import { Ordlak, type OrdlakState } from "./Ordlak";

// ------------------------------------------------------------------ Przycisk

type ButtonVariant = "primary" | "ghost";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
}

/**
 * NA JEDNYM EKRANIE MOZE BYC TYLKO JEDEN `primary` (sekcja 7). To jest
 * ten swiecacy punkt - cien `glow-teal` nalezy wylacznie do niego.
 */
const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-teal text-on-teal shadow-glow-teal hover:brightness-[1.06]",
  ghost: "border border-line-2 text-text-2 hover:border-text-3 hover:text-text",
};

export function Button({
  variant = "primary",
  icon,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={`flex items-center justify-center gap-2 rounded-pill px-4 py-[9px] text-[12.5px] font-semibold transition-[transform,filter,background,border-color,color] duration-150 ease-ordly active:scale-[.985] disabled:pointer-events-none disabled:opacity-45 ${BUTTON_VARIANT[variant]} ${className}`}
    >
      {icon}
      {children}
    </button>
  );
}

/** Maly przycisk paska narzedzi - 11,5 px, ikona 13 px, obwodka `--line`. */
export function MiniButton({
  icon,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={`flex items-center gap-1.5 rounded-pill border border-line px-3 py-[5px] text-[11.5px] text-text-2 transition-all duration-150 ease-ordly hover:border-line-2 hover:text-text disabled:pointer-events-none disabled:opacity-45 ${className}`}
    >
      {icon}
      {children}
    </button>
  );
}

/** Przycisk-ikona 26x26 - pole odpowiedzi, akcje wierszowe. */
export function IconButton({
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={`flex h-[26px] w-[26px] items-center justify-center rounded-sm text-text-3 transition-colors duration-150 hover:bg-panel-3 hover:text-text disabled:pointer-events-none disabled:opacity-45 ${className}`}
    >
      {children}
    </button>
  );
}

// -------------------------------------------------------------- Chip filtra

export function Chip({
  active = false,
  count,
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean;
  /** Licznik obok etykiety - mono 10 px, krycie .7 (sekcja 7). */
  count?: number;
}) {
  return (
    <button
      {...rest}
      aria-pressed={active}
      className={`flex items-center gap-1.5 rounded-pill px-3 py-[5px] text-[11.5px] transition-all duration-150 ease-ordly ${
        active
          ? "border border-transparent bg-teal-glow font-semibold text-teal"
          : "border border-line text-text-2 hover:border-line-2 hover:text-text"
      } ${className}`}
    >
      {children}
      {count !== undefined && (
        <span className="o-mono text-[10px] opacity-70">{count}</span>
      )}
    </button>
  );
}

// --------------------------------------------------------- Etykieta kanalu

export type MarketplaceCode = "allegro" | "allegro_lokalnie" | "amazon" | "olx" | "ebay";

/**
 * Kolory kanalow sa STALE w obu atmosferach - uzytkownik uczy sie ich
 * jako etykiet, wiec nigdy nie zmieniamy przypisan.
 */
const MARKETPLACE_STYLE: Record<MarketplaceCode, string> = {
  allegro: "bg-chan-allegro text-coral",
  // TEN SAM odcien co Allegro.pl (ta sama rodzina serwisow), ale
  // slabszy - kanal bez API, w ktorym ORDLY tylko pokazuje. Amber jest
  // zajety przez Amazon, a dwa kanaly w jednym kolorze przestalyby byc
  // etykietami.
  allegro_lokalnie: "bg-chan-lokalnie text-chan-lokalnie-tx",
  amazon: "bg-chan-amazon text-amber",
  olx: "bg-chan-olx text-violet",
  ebay: "bg-teal-glow text-teal",
};

const MARKETPLACE_LABEL: Record<MarketplaceCode, string> = {
  allegro: "Allegro",
  // Etykieta ma 68 px - pelna nazwa "AllegroLokalnie" by sie nie
  // zmiescila, a samo "AL" nic nie mowi. "Lokalnie" jest jednoznaczne
  // obok sasiedniego "Allegro".
  allegro_lokalnie: "Lokalnie",
  amazon: "Amazon",
  olx: "OLX",
  ebay: "eBay",
};

function normalizeMarketplace(code: string): MarketplaceCode | null {
  const lower = code.toLowerCase();
  return lower === "allegro" ||
    lower === "allegro_lokalnie" ||
    lower === "amazon" ||
    lower === "olx" ||
    lower === "ebay"
    ? lower
    : null;
}

/**
 * STALA SZEROKOSC 68 PX JEST OBOWIAZKOWA. Bez niej "Lokalnie" jest
 * szersze od "OLX" i nazwiska w liscie zaczynaja sie w roznych
 * miejscach - to byl najbardziej widoczny blad pierwszej wersji.
 */
export function MarketplaceBadge({ marketplace }: { marketplace: string }) {
  const code = normalizeMarketplace(marketplace);
  return (
    <span
      className={`o-mono w-[68px] shrink-0 overflow-hidden text-ellipsis whitespace-nowrap rounded-[5px] px-[5px] py-[3px] text-center text-[8.5px] font-semibold uppercase tracking-[.06em] ${
        code ? MARKETPLACE_STYLE[code] : "bg-mute text-text-3"
      }`}
    >
      {code ? MARKETPLACE_LABEL[code] : marketplace}
    </span>
  );
}

// -------------------------------------------------------- Pigulka statusu

/**
 * Jezyk statusow jest spojny w calej aplikacji (sekcja 7):
 *
 *   hot  - wymaga dzialania
 *   go   - w toku, dzis
 *   mute - zamkniete
 *
 * "Wyslane" i "Odebrane" sa `mute`, nie `go`. Swiecenie rzeczy juz
 * skonczonych to glowny powod, przez ktory interfejsy robia sie hałaśliwe.
 */
export type PillTone = "hot" | "go" | "mute";

const PILL_TONE: Record<PillTone, string> = {
  hot: "bg-coral-glow text-coral",
  go: "bg-teal-glow text-teal",
  mute: "bg-panel-3 text-text-3",
};

export function Pill({
  tone,
  /** W wierszu listy `min-width:96px` - bez tego prawa krawedz jest poszarpana. */
  fixed = false,
  children,
}: {
  tone: PillTone;
  fixed?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`shrink-0 whitespace-nowrap rounded-pill px-2.5 py-[3px] text-[10.5px] font-semibold ${
        fixed ? "block min-w-[96px] text-center" : ""
      } ${PILL_TONE[tone]}`}
    >
      {children}
    </span>
  );
}

// ------------------------------------------------------------- Kafel KPI

export type KpiTint = "teal" | "coral" | "amber" | "violet";

const KPI_DOT: Record<KpiTint, string> = {
  teal: "bg-teal",
  coral: "bg-coral",
  amber: "bg-amber",
  violet: "bg-violet",
};

const KPI_LINE: Record<KpiTint, string> = {
  teal: "var(--teal)",
  coral: "var(--coral)",
  amber: "var(--amber)",
  violet: "var(--violet)",
};

/**
 * Mikrowykres kafla - `preserveAspectRatio="none"`, bo ma wypelnic cala
 * szerokosc kafla niezaleznie od liczby punktow. Rysuje sie WYLACZNIE
 * tam, gdzie backend oddaje prawdziwy szereg; kafel bez szeregu zostaje
 * bez wykresu, zamiast pokazywac zmyslona linie.
 */
function KpiSpark({ series, tint }: { series: number[]; tint: KpiTint }) {
  if (series.length < 2) return null;
  const max = Math.max(...series, 1);
  const points = series.map((value, index) => {
    const x = (index / (series.length - 1)) * 200;
    const y = 38 - (value / max) * 34;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg
      viewBox="0 0 200 40"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="absolute bottom-0 left-0 right-0 h-[26px] w-full opacity-90"
    >
      <polygon points={`0,40 ${points.join(" ")} 200,40`} fill={KPI_LINE[tint]} opacity=".1" />
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={KPI_LINE[tint]}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function KpiTile({
  label,
  value,
  tint,
  delta,
  deltaTone = "neutral",
  series,
  onClick,
}: {
  label: string;
  value: string;
  tint: KpiTint;
  delta?: string;
  deltaTone?: "up" | "wait" | "neutral";
  series?: number[];
  onClick?: () => void;
}) {
  const deltaClass =
    deltaTone === "up" ? "text-teal" : deltaTone === "wait" ? "text-coral" : "text-text-3";
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      {...(onClick ? { onClick, type: "button" as const } : {})}
      className={`relative min-w-0 overflow-hidden rounded-lg border border-line bg-panel px-[15px] pb-[30px] pt-[13px] text-left transition-[border-color] duration-150 ease-ordly ${
        onClick ? "hover:border-line-2" : ""
      }`}
    >
      {/* Etykieta i liczba maja z-index 1 - inaczej wykres przechodzi przez tekst. */}
      <div className="relative z-[1] flex items-center gap-[7px]">
        <span className={`h-[5px] w-[5px] shrink-0 rounded-full ${KPI_DOT[tint]}`} />
        <span className="o-eyebrow truncate">{label}</span>
      </div>
      <div className="relative z-[1] mt-2 flex items-baseline gap-2">
        <span className="o-kpi truncate">{value}</span>
        {delta && (
          <em className={`o-mono shrink-0 not-italic text-[10.5px] font-semibold ${deltaClass}`}>
            {delta}
          </em>
        )}
      </div>
      {series && <KpiSpark series={series} tint={tint} />}
    </Tag>
  );
}

// ---------------------------------------------------------- Naglowek panelu

export function PanelHeader({
  title,
  count,
  action,
}: {
  title: string;
  /** Licznik w pastylce. MUSI zgadzac sie z liczba widocznych wierszy. */
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2.5 border-b border-line px-4 pb-[9px] pt-[10px]">
      <h3 className="o-panel-title truncate">{title}</h3>
      {count !== undefined && count > 0 && (
        <span className="o-mono shrink-0 rounded-pill bg-coral-glow px-2 py-[1px] text-[10px] font-semibold text-coral">
          {count}
        </span>
      )}
      {action && <div className="ml-auto shrink-0">{action}</div>}
    </div>
  );
}

/** Link tekstowy w naglowku panelu - mono 10 px. */
export function PanelLink({
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={`o-mono text-[10px] uppercase tracking-[.1em] text-text-3 transition-colors duration-150 hover:text-teal ${className}`}
    >
      {children}
    </button>
  );
}

// ------------------------------------------------------------ Pasek zapasu

export function StockBar({
  value,
  max,
  low = false,
  className = "",
}: {
  value: number;
  max: number;
  low?: boolean;
  className?: string;
}) {
  const percent = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <span
      className={`block h-[4px] w-24 overflow-hidden rounded-[2px] bg-panel-3 ${className}`}
    >
      <span
        className={`block h-full rounded-[2px] transition-[width] duration-[800ms] ease-ordly ${
          low ? "bg-coral" : "bg-teal"
        }`}
        style={{ width: `${percent}%` }}
      />
    </span>
  );
}

// ---------------------------------------------------------------- Stepper

export function Stepper({
  value,
  onDecrease,
  onIncrease,
  onEdit,
  disabled = false,
}: {
  value: number;
  onDecrease: () => void;
  onIncrease: () => void;
  /**
   * Klikniecie w sama liczbe - wejscie w reczna korekte. Bez tego
   * jedyna droga do zmiany o 500 sztuk jest 500 klikniec w "+".
   * Kropkowane podkreslenie liczby to jedyny sygnal, ze da sie ja
   * kliknac; bez niego funkcja istnieje, ale nikt jej nie znajduje.
   */
  onEdit?: () => void;
  disabled?: boolean;
}) {
  return (
    <span className="inline-flex items-center overflow-hidden rounded-xs border border-line">
      <button
        type="button"
        onClick={onDecrease}
        disabled={disabled || value <= 0}
        aria-label="Zmniejsz o 1"
        className="flex h-6 w-6 items-center justify-center text-[13px] text-text-2 transition-colors hover:bg-panel-3 hover:text-text disabled:pointer-events-none disabled:opacity-40"
      >
        −
      </button>
      {onEdit ? (
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          title="Kliknij, żeby wpisać stan ręcznie"
          aria-label={`Wpisz stan ręcznie (teraz ${value})`}
          className="o-mono flex h-6 min-w-[34px] items-center justify-center px-1 text-[11.5px] text-text underline decoration-line-2 decoration-dotted underline-offset-[3px] transition-colors hover:bg-panel-3 hover:text-teal hover:decoration-teal disabled:pointer-events-none disabled:opacity-40"
        >
          {value}
        </button>
      ) : (
        <span className="o-mono min-w-[34px] text-center text-[11.5px] text-text">{value}</span>
      )}
      <button
        type="button"
        onClick={onIncrease}
        disabled={disabled}
        aria-label="Zwiększ o 1"
        className="flex h-6 w-6 items-center justify-center text-[13px] text-text-2 transition-colors hover:bg-panel-3 hover:text-text disabled:pointer-events-none disabled:opacity-40"
      >
        +
      </button>
    </span>
  );
}

// -------------------------------------------------------------- Przelacznik

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-[23px] w-10 shrink-0 rounded-pill transition-colors duration-[220ms] ease-ordly disabled:opacity-45 ${
        checked ? "bg-teal-deep" : "bg-panel-3"
      }`}
    >
      <span
        className={`absolute left-[3px] top-[3px] h-[17px] w-[17px] rounded-full transition-[transform,background] duration-[220ms] ease-ordly ${
          checked ? "translate-x-[17px] bg-teal" : "bg-text-3"
        }`}
      />
    </button>
  );
}

// ------------------------------------------------------------------ Awatar

export function InitialAvatar({
  name,
  size = 32,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const initials = name
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={`o-mono flex shrink-0 items-center justify-center rounded-full border border-line-2 bg-panel-2 font-semibold text-text-2 ${className}`}
    >
      {initials || "?"}
    </span>
  );
}

// -------------------------------------------------------------- Stan pusty

/**
 * Pusty stan listy to jedno z dwoch miejsc, gdzie Ordlak spi (sekcja 6) -
 * "brak zwrotow" nie jest awaria i nie ma po co swiecic.
 */
export function EmptyState({
  state = "sleep",
  title,
  description,
}: {
  state?: OrdlakState;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3.5 px-6 py-14 text-center">
      <Ordlak state={state} size={88} />
      <h4 className="o-panel-title text-[15px]">{title}</h4>
      <p className="max-w-[280px] text-[12.5px] leading-[1.55] text-text-3">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------- Skeleton

/** Ladowanie przez przelaczanie klas, nigdy przez podmiane innerHTML. */
export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="border-b border-line px-4 py-[13px]">
          <span className="o-skeleton-bar mb-2.5 h-[11px] w-[56%]" />
          <span className="o-skeleton-bar mb-2 h-[9px] w-[82%]" />
          <span className="o-skeleton-bar h-[9px] w-[40%]" />
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ Stan bledu

/** Blad mowi CO sie stalo i CO zrobic - nie przeprasza i nie jest ogolnikowy. */
export function ErrorState({
  title,
  detail,
  onRetry,
}: {
  title: string;
  detail: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3.5 px-6 py-14 text-center">
      <Ordlak state="alert" size={72} />
      <h4 className="o-panel-title text-[15px] text-coral">{title}</h4>
      <p className="max-w-[380px] text-[12.5px] leading-[1.55] text-text-3">{detail}</p>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry} className="mt-1">
          Spróbuj ponownie
        </Button>
      )}
    </div>
  );
}

// ------------------------------------------------------------- Etykiety

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="o-eyebrow">{children}</div>;
}

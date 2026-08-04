/**
 * Biblioteka komponentow z sekcji 5 specyfikacji. Wszystko, co powtarza
 * sie na wiecej niz jednym ekranie, mieszka TUTAJ - ekrany nie duplikuja
 * stylow (kryterium odbioru 10.3).
 *
 * Nazwy wariantow sa zawsze prefiksowane nazwa bloku (`pill-new`, a nie
 * samo `new`) - to wniosek z prawdziwego bledu opisanego w sekcji 10.3,
 * gdzie klasa `.unread` znaczyla dwie rozne rzeczy naraz i karty
 * mobilne zapadly sie do rozmiaru kropki.
 */
import * as React from "react";
import { Mascot, type OrdiPose } from "./Mascot";

// ------------------------------------------------------------------ Przycisk

type ButtonVariant = "primary" | "ghost";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
}

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-teal-bright text-[#052321] hover:brightness-110",
  ghost: "bg-panel-2 text-white border border-line-strong hover:bg-panel-3",
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
      className={`flex items-center justify-center gap-2 rounded-[9px] px-3.5 py-2.5 text-[12.5px] font-medium transition-[transform,filter,background] duration-150 ease-ordly active:scale-[.985] disabled:pointer-events-none disabled:opacity-45 ${BUTTON_VARIANT[variant]} ${className}`}
    >
      {icon}
      {children}
    </button>
  );
}

/** Maly przycisk paska narzedzi - 11.5 px, ikona 13 px, obramowanie `--line`. */
export function MiniButton({
  icon,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={`flex items-center gap-1.5 rounded-[7px] border border-line px-2.5 py-[5px] text-[11.5px] text-slate transition-all duration-150 ease-ordly hover:border-line-strong hover:bg-panel-2 hover:text-white disabled:pointer-events-none disabled:opacity-45 ${className}`}
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
      className={`flex h-[26px] w-[26px] items-center justify-center rounded-md text-slate-dim transition-colors duration-150 hover:bg-panel-3 hover:text-white disabled:pointer-events-none disabled:opacity-45 ${className}`}
    >
      {children}
    </button>
  );
}

// -------------------------------------------------------------- Chip filtra

export function Chip({
  active = false,
  className = "",
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      {...rest}
      aria-pressed={active}
      className={`rounded-[20px] px-[11px] py-[5px] text-[11.5px] transition-all duration-150 ease-ordly ${
        active
          ? "border border-transparent bg-teal-dim text-teal-bright"
          : "border border-line text-slate hover:border-line-strong hover:text-white"
      } ${className}`}
    >
      {children}
    </button>
  );
}

// --------------------------------------------------------- Odznaka kanalu

export type MarketplaceCode = "allegro" | "amazon" | "olx" | "ebay";

const MARKETPLACE_STYLE: Record<MarketplaceCode, string> = {
  allegro: "bg-[rgba(255,133,99,.14)] text-coral",
  amazon: "bg-[rgba(245,192,101,.14)] text-amber",
  olx: "bg-[rgba(167,155,255,.14)] text-violet",
  ebay: "bg-teal-dim text-teal-bright",
};

const MARKETPLACE_LABEL: Record<MarketplaceCode, string> = {
  allegro: "Allegro",
  amazon: "Amazon",
  olx: "OLX",
  ebay: "eBay",
};

function normalizeMarketplace(code: string): MarketplaceCode | null {
  const lower = code.toLowerCase();
  return lower === "allegro" || lower === "amazon" || lower === "olx" || lower === "ebay"
    ? lower
    : null;
}

/**
 * Kolory kanalow sa STALE w obu motywach - uzytkownik uczy sie ich jako
 * etykiet, wiec nigdy nie zmieniamy przypisan (sekcja 2.3).
 */
export function MarketplaceBadge({ marketplace }: { marketplace: string }) {
  const code = normalizeMarketplace(marketplace);
  return (
    <span
      className={`o-mono w-[60px] shrink-0 rounded-[5px] px-1.5 py-[3.5px] text-center text-[9px] font-semibold uppercase tracking-[.05em] ${
        code ? MARKETPLACE_STYLE[code] : "bg-panel-3 text-slate"
      }`}
    >
      {code ? MARKETPLACE_LABEL[code] : marketplace}
    </span>
  );
}

// -------------------------------------------------------- Pigulka statusu

export type PillTone = "new" | "pack" | "done" | "warn";

const PILL_TONE: Record<PillTone, string> = {
  new: "bg-teal-dim text-teal-bright",
  pack: "bg-coral-dim text-coral",
  done: "bg-[rgba(147,166,160,.12)] text-slate",
  warn: "bg-[rgba(245,192,101,.13)] text-amber",
};

export function Pill({ tone, children }: { tone: PillTone; children: React.ReactNode }) {
  return (
    <span
      className={`shrink-0 whitespace-nowrap rounded-[20px] px-2.5 py-1 text-[10.5px] font-medium ${PILL_TONE[tone]}`}
    >
      {children}
    </span>
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
      className={`block h-[5px] w-24 overflow-hidden rounded-[3px] bg-panel-3 ${className}`}
    >
      <span
        className={`block h-full rounded-[3px] transition-[width] duration-[800ms] ease-ordly ${
          low ? "bg-coral" : "bg-teal-bright"
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
  disabled = false,
}: {
  value: number;
  onDecrease: () => void;
  onIncrease: () => void;
  disabled?: boolean;
}) {
  return (
    <span className="inline-flex items-center overflow-hidden rounded-[7px] border border-line">
      <button
        type="button"
        onClick={onDecrease}
        disabled={disabled || value <= 0}
        aria-label="Zmniejsz o 1"
        className="flex h-6 w-6 items-center justify-center text-[13px] text-slate transition-colors hover:bg-panel-3 hover:text-white disabled:pointer-events-none disabled:opacity-40"
      >
        −
      </button>
      <span className="o-mono min-w-[34px] text-center text-[11.5px] text-white">{value}</span>
      <button
        type="button"
        onClick={onIncrease}
        disabled={disabled}
        aria-label="Zwiększ o 1"
        className="flex h-6 w-6 items-center justify-center text-[13px] text-slate transition-colors hover:bg-panel-3 hover:text-white disabled:pointer-events-none disabled:opacity-40"
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
      className={`relative h-[23px] w-10 shrink-0 rounded-[20px] transition-colors duration-[220ms] ease-ordly disabled:opacity-45 ${
        checked ? "bg-teal-deep" : "bg-panel-3"
      }`}
    >
      <span
        className={`absolute left-[3px] top-[3px] h-[17px] w-[17px] rounded-full transition-[transform,background] duration-[220ms] ease-ordly ${
          checked ? "translate-x-[17px] bg-teal-bright" : "bg-slate-dim"
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
      className={`o-display flex shrink-0 items-center justify-center rounded-full border border-line-strong bg-panel-3 font-semibold text-slate ${className}`}
    >
      {initials || "?"}
    </span>
  );
}

// -------------------------------------------------------------- Stan pusty

export function EmptyState({
  pose = "happy",
  title,
  description,
}: {
  pose?: OrdiPose;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3.5 px-6 py-14 text-center">
      <Mascot pose={pose} size={88} className="opacity-90" />
      <h4 className="o-display text-[15px] font-semibold">{title}</h4>
      <p className="max-w-[280px] text-[12.5px] leading-[1.55] text-slate-dim">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------- Skeleton

/**
 * Ladowanie przez przelaczanie klas, nigdy przez podmiane innerHTML
 * (kryterium odbioru 10.3). Trzy paski o szerokosciach 56% / 82% / 40%.
 */
export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="border-b border-line px-[22px] py-[15px]">
          <span className="o-skeleton-bar mb-2.5 h-[11px] w-[56%]" />
          <span className="o-skeleton-bar mb-2 h-[9px] w-[82%]" />
          <span className="o-skeleton-bar h-[9px] w-[40%]" />
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ Stan bledu

/**
 * Blad mowi CO sie stalo i CO zrobic (sekcja 7.3) - nie przeprasza
 * i nie jest ogolnikowy.
 */
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
      <Mascot pose="think" size={72} className="opacity-90" />
      <h4 className="o-display text-[15px] font-semibold text-coral">{title}</h4>
      <p className="max-w-[380px] text-[12.5px] leading-[1.55] text-slate-dim">{detail}</p>
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

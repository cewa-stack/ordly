/**
 * Pasek boczny - 238 px (sekcja 10 instrukcji "Nokturn").
 *
 * Kolejnosc od gory: marka -> GLOWNE -> ZAPLECZE -> Ustawienia
 * i wskaznik stanu przyklejone do dolu.
 *
 * Aktywna pozycja ma tlo `--panel-2` i pasek `--teal` 2 px po lewej -
 * BEZ OBWODKI. Ten sam wzorzec (pasek zamiast ramki) powtarza sie na
 * wybranym wierszu listy zamowien; dzieki temu "wybrane" wyglada wszedzie
 * tak samo.
 *
 * Kazda pozycja MUSI prowadzic do dzialajacego ekranu - slepe zaulki sa
 * bledem krytycznym.
 */
import type { ReactNode } from "react";
import {
  BoxIcon,
  CalendarIcon,
  ChartIcon,
  ChatIcon,
  GearIcon,
  GridIcon,
  HomeIcon,
  MailIcon,
  ReturnIcon,
  SparkIcon,
  TagIcon,
  TruckIcon,
} from "../icons";
import { Ordlak } from "./Ordlak";
import { OrdlakIndicator } from "./OrdlakIndicator";

export type ViewId =
  | "start"
  | "zamowienia"
  | "dyskusje"
  | "magazyn"
  | "poczta"
  | "zwroty"
  | "ordlak"
  | "hurtownie"
  | "olx"
  | "statystyki"
  | "kalendarz"
  | "ustawienia";

interface NavItemDef {
  id: ViewId;
  label: string;
  icon: ReactNode;
}

/** Ikona pozycji nawigacji - 15 px, stroke 1,7 (sekcja 10). */
const NAV_ICON = { size: 15, strokeWidth: 1.7 } as const;

export const MAIN_NAV: NavItemDef[] = [
  { id: "start", label: "Start", icon: <HomeIcon {...NAV_ICON} /> },
  { id: "zamowienia", label: "Zamówienia", icon: <BoxIcon {...NAV_ICON} /> },
  { id: "dyskusje", label: "Dyskusje", icon: <ChatIcon {...NAV_ICON} /> },
  { id: "magazyn", label: "Magazyn", icon: <GridIcon {...NAV_ICON} /> },
  { id: "poczta", label: "Poczta", icon: <MailIcon {...NAV_ICON} /> },
  { id: "zwroty", label: "Zwroty", icon: <ReturnIcon {...NAV_ICON} /> },
  { id: "ordlak", label: "Ordlak", icon: <SparkIcon {...NAV_ICON} /> },
];

export const BACKSTAGE_NAV: NavItemDef[] = [
  { id: "hurtownie", label: "Hurtownie", icon: <TruckIcon {...NAV_ICON} /> },
  { id: "olx", label: "OLX", icon: <TagIcon {...NAV_ICON} /> },
  { id: "statystyki", label: "Statystyki", icon: <ChartIcon {...NAV_ICON} /> },
  { id: "kalendarz", label: "Kalendarz", icon: <CalendarIcon {...NAV_ICON} /> },
];

/** Liczniki po prawej stronie pozycji - `alert` gdy wymagaja dzialania. */
export interface NavCounts {
  zamowienia?: number;
  dyskusje?: { value: number; alert: boolean };
  poczta?: number;
  zwroty?: number;
}

interface SidebarProps {
  active: ViewId;
  onSelect: (view: ViewId) => void;
  counts: NavCounts;
  /** Wersja i host - druga linijka pod marka. */
  hostname: string;
  version: string;
}

function NavItem({
  item,
  active,
  onSelect,
  count,
  alert = false,
}: {
  item: NavItemDef;
  active: boolean;
  onSelect: (view: ViewId) => void;
  count?: number;
  alert?: boolean;
}) {
  return (
    <button
      onClick={() => onSelect(item.id)}
      aria-current={active ? "page" : undefined}
      className={`relative flex w-full items-center gap-[11px] rounded-sm px-2.5 py-2 text-left text-[13px] transition-[background,color] duration-150 ease-ordly ${
        active ? "bg-panel-2 text-text" : "text-text-2 hover:bg-panel-2 hover:text-text"
      }`}
    >
      {/* Pasek 2 px na lewej krawedzi paska bocznego - bez obwodki. */}
      {active && (
        <span className="absolute -left-3 bottom-2 top-2 w-[2px] rounded-r-[2px] bg-teal" />
      )}
      <span className={`shrink-0 ${active ? "text-teal" : ""}`}>{item.icon}</span>
      <span className="truncate">{item.label}</span>
      {count !== undefined && count > 0 && (
        <span
          className={`o-mono ml-auto shrink-0 text-[10.5px] ${
            alert ? "text-coral" : "text-text-3"
          }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export function Sidebar({ active, onSelect, counts, hostname, version }: SidebarProps) {
  function countFor(id: ViewId): { value?: number; alert: boolean } {
    switch (id) {
      case "zamowienia":
        return { value: counts.zamowienia, alert: (counts.zamowienia ?? 0) > 0 };
      case "dyskusje":
        return { value: counts.dyskusje?.value, alert: counts.dyskusje?.alert ?? false };
      case "poczta":
        return { value: counts.poczta, alert: false };
      case "zwroty":
        return { value: counts.zwroty, alert: false };
      default:
        return { alert: false };
    }
  }

  // Ponizej 940 px pasek boczny znika - nawigacja zostaje przez Ctrl+K
  // i skroty `G` + litera.
  return (
    <aside className="flex w-[238px] shrink-0 flex-col border-r border-line px-3 pb-3 pt-4 max-[940px]:hidden">
      {/*
       * Logo jest ZNAKIEM, nie wskaznikiem - maskotka stoi tu na stale
       * w stanie `idle`. Stan systemu pokazuje wylacznie stopka.
       */}
      <div className="flex items-center gap-[11px] px-2.5 pb-1">
        <Ordlak state="idle" size={26} className="shrink-0" />
        <div className="min-w-0">
          <div className="o-display text-[16px] tracking-[.09em]">ORDLY</div>
          <div className="o-mono truncate text-[9px] text-text-3">
            {version} · {hostname || "offline"}
          </div>
        </div>
      </div>

      <div className="o-eyebrow px-2.5 pb-2 pt-4">Główne</div>
      <nav className="flex flex-col gap-0.5">
        {MAIN_NAV.map((item) => {
          const { value, alert } = countFor(item.id);
          return (
            <NavItem
              key={item.id}
              item={item}
              active={active === item.id}
              onSelect={onSelect}
              count={value}
              alert={alert}
            />
          );
        })}
      </nav>

      <div className="o-eyebrow px-2.5 pb-2 pt-4">Zaplecze</div>
      <nav className="flex flex-col gap-0.5">
        {BACKSTAGE_NAV.map((item) => (
          <NavItem
            key={item.id}
            item={item}
            active={active === item.id}
            onSelect={onSelect}
          />
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-line pt-3">
        <NavItem
          item={{ id: "ustawienia", label: "Ustawienia", icon: <GearIcon {...NAV_ICON} /> }}
          active={active === "ustawienia"}
          onSelect={onSelect}
        />
        <OrdlakIndicator />
      </div>
    </aside>
  );
}

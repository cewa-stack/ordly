/**
 * Pasek boczny 224 px (sekcja 4.2). Kolejnosc od gory: marka -> grupa
 * glowna -> grupa "Zaplecze" -> Ustawienia i wskaznik Ordiego przyklejone
 * do dolu.
 *
 * Kazda pozycja MUSI prowadzic do dzialajacego ekranu - slepe zaulki sa
 * bledem krytycznym (sekcja 4.4).
 */
import type { ReactNode } from "react";
import {
  BoxIcon,
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
import { OrdiIndicator } from "./OrdiIndicator";

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
  | "ustawienia";

interface NavItemDef {
  id: ViewId;
  label: string;
  icon: ReactNode;
}

export const MAIN_NAV: NavItemDef[] = [
  { id: "start", label: "Start", icon: <HomeIcon /> },
  { id: "zamowienia", label: "Zamówienia", icon: <BoxIcon /> },
  { id: "dyskusje", label: "Dyskusje", icon: <ChatIcon /> },
  { id: "magazyn", label: "Magazyn", icon: <GridIcon /> },
  { id: "poczta", label: "Poczta", icon: <MailIcon /> },
  { id: "zwroty", label: "Zwroty", icon: <ReturnIcon /> },
  { id: "ordlak", label: "Ordlak", icon: <SparkIcon /> },
];

export const BACKSTAGE_NAV: NavItemDef[] = [
  { id: "hurtownie", label: "Hurtownie", icon: <TruckIcon /> },
  { id: "olx", label: "OLX", icon: <TagIcon /> },
  { id: "statystyki", label: "Statystyki", icon: <ChartIcon /> },
];

/** Liczniki po prawej stronie pozycji - `alert` gdy wymagaja uwagi. */
export interface NavCounts {
  zamowienia?: number;
  dyskusje?: { value: number; alert: boolean };
  magazyn?: { value: number; alert: boolean };
  poczta?: number;
  zwroty?: number;
}

interface SidebarProps {
  active: ViewId;
  onSelect: (view: ViewId) => void;
  counts: NavCounts;
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
      className={`relative flex w-full items-center gap-[11px] rounded-[9px] px-2.5 py-[9px] text-left text-[13.5px] transition-[background,color] duration-150 ease-ordly ${
        active
          ? "bg-teal-dim text-teal-bright"
          : "text-slate hover:bg-panel-2 hover:text-white"
      }`}
    >
      {active && (
        <span className="absolute -left-3 top-1/2 h-[17px] w-[3px] -translate-y-1/2 rounded-r-[3px] bg-teal-bright" />
      )}
      <span className={active ? "opacity-100" : "opacity-80"}>{item.icon}</span>
      {item.label}
      {count !== undefined && count > 0 && (
        <span
          className={`o-mono ml-auto text-[10.5px] ${
            alert ? "text-coral" : active ? "text-teal-bright" : "text-slate-dim"
          }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}

export function Sidebar({ active, onSelect, counts }: SidebarProps) {
  function countFor(id: ViewId): { value?: number; alert: boolean } {
    switch (id) {
      case "zamowienia":
        return { value: counts.zamowienia, alert: false };
      case "dyskusje":
        return { value: counts.dyskusje?.value, alert: counts.dyskusje?.alert ?? false };
      case "magazyn":
        return { value: counts.magazyn?.value, alert: counts.magazyn?.alert ?? false };
      case "poczta":
        return { value: counts.poczta, alert: false };
      case "zwroty":
        return { value: counts.zwroty, alert: false };
      default:
        return { alert: false };
    }
  }

  // Ponizej 940 px pasek boczny znika (tak jak w koncepcji) - nawigacja
  // zostaje przez Ctrl+K i skroty `G` + litera.
  return (
    <aside className="flex w-[224px] shrink-0 flex-col border-r border-line bg-ink-raised px-3 py-[18px] max-[940px]:hidden">
      <div className="flex items-center gap-[11px] px-2 pb-5 pt-1.5">
        <div
          className="o-display flex h-7 w-7 items-center justify-center rounded-[9px] text-[14px] font-bold text-[#04211F] shadow-brand"
          style={{
            background: "linear-gradient(150deg, var(--teal-bright), var(--teal-deep))",
          }}
        >
          O
        </div>
        <div className="o-display text-[15.5px] font-semibold tracking-[-.015em]">ORDLY</div>
        <span className="o-mono ml-auto rounded-[5px] border border-line px-[5px] py-0.5 text-[9px] text-slate-dim">
          v2
        </span>
      </div>

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

      <div className="flex flex-col gap-0.5">
        <div className="o-mono px-2.5 pb-[7px] pt-4 text-[9.5px] uppercase tracking-[.13em] text-slate-dim">
          Zaplecze
        </div>
        {BACKSTAGE_NAV.map((item) => (
          <NavItem
            key={item.id}
            item={item}
            active={active === item.id}
            onSelect={onSelect}
          />
        ))}
      </div>

      <div className="mt-auto flex flex-col gap-2.5 border-t border-line pt-4">
        <NavItem
          item={{ id: "ustawienia", label: "Ustawienia", icon: <GearIcon /> }}
          active={active === "ustawienia"}
          onSelect={onSelect}
        />
        <OrdiIndicator />
      </div>
    </aside>
  );
}

import type { ReactNode } from "react";
import mascotSrc from "../assets/mascot.png";
import {
  BarsIcon,
  BoxIcon,
  ChatIcon,
  LogoutIcon,
  MailIcon,
  ReceiptIcon,
  TagIcon,
  UndoIcon,
  WarehouseIcon,
} from "../icons";
import { useAuth } from "../lib/auth";

export type ViewId =
  | "magazyn"
  | "zamowienia"
  | "zwroty"
  | "dyskusje"
  | "hurtownia"
  | "skrzynka"
  | "olx"
  | "statystyki";

interface NavItemDef {
  id: ViewId;
  label: string;
  icon: ReactNode;
}

interface SoonItemDef {
  label: string;
  icon: ReactNode;
  stage: string;
}

const liveItems: NavItemDef[] = [
  { id: "magazyn", label: "Magazyn", icon: <BoxIcon /> },
  { id: "zamowienia", label: "Zamówienia", icon: <ReceiptIcon /> },
  { id: "zwroty", label: "Zwroty i anulowane", icon: <UndoIcon /> },
  { id: "dyskusje", label: "Dyskusje", icon: <ChatIcon /> },
  { id: "hurtownia", label: "Hurtownia", icon: <WarehouseIcon /> },
  { id: "skrzynka", label: "Skrzynka", icon: <MailIcon /> },
  { id: "olx", label: "OLX", icon: <TagIcon /> },
  { id: "statystyki", label: "Statystyki", icon: <BarsIcon /> },
];

// Wszystkie etapy z files/ordly_roadmap_2026-07-31.html sa juz zbudowane.
const soonItems: SoonItemDef[] = [];

interface SidebarProps {
  active: ViewId;
  onSelect: (view: ViewId) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  const { session, logout } = useAuth();

  return (
    <aside className="flex w-[236px] shrink-0 flex-col border-r border-border bg-surface p-3">
      <div className="flex items-center gap-2 px-2 pb-4 pt-1">
        <img src={mascotSrc} alt="" width={24} height={24} className="shrink-0 rounded-[7px]" />
        <div className="text-[13px] font-extrabold tracking-[0.22em]">ORDLY</div>
      </div>

      <nav className="flex flex-col gap-0.5">
        {liveItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`relative flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-left text-[13.5px] font-semibold transition-colors ${
              active === item.id
                ? "bg-primary-tint text-primary"
                : "text-text-secondary hover:bg-surface-raised"
            }`}
          >
            {active === item.id && (
              <span className="absolute -left-3 top-2 bottom-2 w-[3px] rounded-r-[3px] bg-primary" />
            )}
            <span className="shrink-0">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {soonItems.length > 0 && <div className="my-2.5 h-px bg-border" />}

      <nav className="flex flex-col gap-0.5">
        {soonItems.map((item) => (
          <div
            key={item.label}
            title={`Zaplanowane — etap ${item.stage}`}
            className="flex cursor-not-allowed items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13.5px] font-semibold text-text-secondary opacity-40"
          >
            <span className="shrink-0">{item.icon}</span>
            {item.label}
            <span className="ml-auto rounded-[6px] bg-surface-raised px-1.5 py-0.5 font-mono text-[9.5px] text-text-dim">
              {item.stage}
            </span>
          </div>
        ))}
      </nav>

      <div className="mt-auto flex items-center gap-2.5 border-t border-border pt-3">
        <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border border-border bg-surface-raised text-[12px] font-bold text-text-secondary">
          {session?.username.slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[12.5px] font-semibold text-text">{session?.username}</div>
          <div className="text-[10.5px] text-text-dim">Połączono</div>
        </div>
        <button
          type="button"
          title="Wyloguj"
          aria-label="Wyloguj"
          onClick={() => void logout()}
          className="shrink-0 text-text-dim hover:text-danger"
        >
          <LogoutIcon size={16} />
        </button>
      </div>
    </aside>
  );
}

/**
 * Gorny pasek obszaru roboczego - 54 px (sekcja 10 instrukcji).
 *
 * Tytul ekranu -> kontekst -> wyszukiwarka dosunieta w prawo -> ikony.
 * Kontekst zmienia sie RAZEM z ekranem i niesie stan (np. aktywny
 * filtr), zeby uzytkownik widzial, na co patrzy.
 *
 * Dzwonek nie jest ozdoba: rozwija liste rzeczy, ktore naprawde czekaja,
 * i kazda pozycja prowadzi na wlasciwy ekran. Kropka zapala sie tylko
 * wtedy, gdy ta lista nie jest pusta.
 */
import * as React from "react";
import { BellIcon, SearchIcon } from "../icons";
import { InitialAvatar } from "./ui";
import type { ViewId } from "./Sidebar";

export interface TopbarAlert {
  id: string;
  label: string;
  detail: string;
  view: ViewId;
  /** `true` gdy rzecz wymaga dzialania - wtedy kropka i tekst sa koralowe. */
  hot: boolean;
}

interface TopbarProps {
  title: string;
  crumb: string;
  initials: string;
  alerts: TopbarAlert[];
  onOpenPalette: () => void;
  onNavigate: (view: ViewId) => void;
}

export function Topbar({
  title,
  crumb,
  initials,
  alerts,
  onOpenPalette,
  onNavigate,
}: TopbarProps) {
  const [bellOpen, setBellOpen] = React.useState(false);
  const bellRef = React.useRef<HTMLDivElement>(null);

  // Zamkniecie klikiem obok i Escape - inaczej lista zostaje otwarta
  // po przejsciu na inny ekran i wisi nad nowa zawartoscia.
  React.useEffect(() => {
    if (!bellOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!bellRef.current?.contains(event.target as Node)) setBellOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setBellOpen(false);
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [bellOpen]);

  return (
    <div className="flex h-[54px] shrink-0 items-center gap-4 border-b border-line px-[22px]">
      <h2 className="o-screen-title shrink-0">{title}</h2>
      <div className="o-mono min-w-0 flex-1 truncate text-[10.5px] uppercase tracking-[.12em] text-text-3">
        {crumb}
      </div>

      <button
        onClick={onOpenPalette}
        className="flex h-8 w-[268px] shrink-0 items-center gap-2 overflow-hidden whitespace-nowrap rounded-pill border border-line px-3 text-[12px] text-text-3 transition-[border-color,color] duration-150 ease-ordly hover:border-line-2 hover:text-text-2"
      >
        <SearchIcon size={14} className="shrink-0 opacity-75" />
        Szukaj lub przejdź do…
        <span className="o-mono ml-auto shrink-0 rounded-[5px] border border-line-2 px-1.5 py-[1px] text-[9.5px]">
          Ctrl K
        </span>
      </button>

      <div ref={bellRef} className="relative shrink-0">
        <button
          onClick={() => setBellOpen((open) => !open)}
          aria-label={
            alerts.length > 0
              ? `Powiadomienia (${alerts.length})`
              : "Powiadomienia - nic nie czeka"
          }
          aria-expanded={bellOpen}
          className={`relative flex h-[31px] w-[31px] items-center justify-center rounded-full transition-colors duration-150 ${
            bellOpen ? "bg-panel-2 text-text" : "text-text-2 hover:bg-panel-2 hover:text-text"
          }`}
        >
          <BellIcon size={16} />
          {alerts.length > 0 && (
            <span className="absolute right-[6px] top-[6px] h-[5px] w-[5px] rounded-full bg-coral" />
          )}
        </button>

        {bellOpen && (
          <div className="animate-fade-up absolute right-0 top-[38px] z-30 w-[290px] overflow-hidden rounded-md border border-line-2 bg-panel shadow-palette">
            <div className="o-eyebrow border-b border-line px-3.5 py-2.5">
              Czeka na Ciebie
            </div>
            {alerts.length === 0 ? (
              <p className="px-3.5 py-4 text-[12px] text-text-3">
                Nic nie czeka. Ordlak pilnuje kanałów i da znać.
              </p>
            ) : (
              alerts.map((alert) => (
                <button
                  key={alert.id}
                  onClick={() => {
                    onNavigate(alert.view);
                    setBellOpen(false);
                  }}
                  className="flex w-full items-center gap-2.5 border-b border-line px-3.5 py-2.5 text-left transition-colors duration-150 last:border-b-0 hover:bg-panel-2"
                >
                  <span
                    className={`h-[5px] w-[5px] shrink-0 rounded-full ${
                      alert.hot ? "bg-coral" : "bg-teal"
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12px] font-semibold text-text">
                      {alert.label}
                    </span>
                    <span className="o-mono block truncate text-[9.5px] text-text-3">
                      {alert.detail}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <InitialAvatar name={initials} size={31} className="shrink-0" />
    </div>
  );
}

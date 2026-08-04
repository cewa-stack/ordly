/**
 * Wskaznik Ordiego - element sygnaturowy produktu (sekcja 3.2).
 *
 * Pokazuje stan systemu bez koniecznosci czytania: spoczynek (unoszenie),
 * praca (pierscien obracajacy sie wokol orba, 0.95 s liniowo), sukces
 * ("pop" 1 -> 1.2 -> 1 w 550 ms).
 *
 * Klikniecie uruchamia synchronizacje. Powtorne klikniecie w trakcie
 * cyklu jest ignorowane - blokada siedzi w `SyncProvider`.
 */
import { Mascot } from "./Mascot";
import { useSync } from "../lib/sync";

export function OrdiIndicator() {
  const { phase, pose, title, subtitle, sync } = useSync();
  const isWorking = phase === "working";
  const isSuccess = phase === "success";

  return (
    <button
      onClick={sync}
      aria-label="Synchronizuj z marketplace"
      className="flex w-full items-center gap-[11px] rounded-md border border-line bg-panel-2 p-[9px] text-left transition-[border-color,background] duration-200 ease-ordly hover:border-line-strong hover:bg-panel-3"
    >
      <span
        className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
        style={{
          background: "radial-gradient(circle at 34% 28%, #20423E, var(--ink-raised) 72%)",
        }}
      >
        <span
          aria-hidden="true"
          className={`absolute -inset-[3px] rounded-full transition-opacity duration-[250ms] ease-ordly ${
            isWorking ? "animate-spin-ring opacity-100" : "opacity-0"
          }`}
          style={{
            background:
              "conic-gradient(from 0deg, var(--teal-bright), rgba(95,217,204,0) 62%)",
          }}
        />
        <Mascot
          pose={pose}
          size={26}
          floaty={false}
          className={`relative z-[1] ${
            isWorking ? "" : isSuccess ? "animate-pop" : "animate-bob"
          }`}
        />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-[11.5px] font-semibold text-white">{title}</span>
        <span className="o-mono truncate text-[9.5px] text-slate-dim">{subtitle}</span>
      </span>
    </button>
  );
}

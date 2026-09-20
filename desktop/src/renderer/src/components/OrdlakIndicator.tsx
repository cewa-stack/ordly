/**
 * Wskaznik stanu w stopce paska bocznego (sekcja 10 instrukcji).
 *
 * To JEDYNE miejsce w pasku bocznym, ktore pokazuje stan. Logo w
 * naglowku jest znakiem, NIE wskaznikiem - nie podpina sie pod nie
 * stanu synchronizacji.
 *
 * Klikniecie uruchamia synchronizacje. Powtorne klikniecie w trakcie
 * cyklu jest ignorowane - blokada siedzi w `SyncProvider`.
 */
import { Ordlak } from "./Ordlak";
import { useSync } from "../lib/sync";
import { useOrdlakState } from "../lib/ordlakState";

export function OrdlakIndicator() {
  const { phase, title, subtitle, sync } = useSync();
  const { state, alertReason } = useOrdlakState();

  // Przy alarmie wskaznik mowi, CO jest nie tak - maskotka sama tego nie
  // powie, a czytnik ekranu nie dostaje stanu w etykiecie (sekcja 14).
  const headline = alertReason ?? title;
  const detail = alertReason ? "Kliknij, żeby spróbować ponownie" : subtitle;

  return (
    <button
      onClick={sync}
      disabled={phase === "working"}
      aria-label="Synchronizuj teraz"
      className="flex w-full items-center gap-[11px] rounded-md bg-panel p-[9px] pr-[10px] text-left transition-colors duration-150 ease-ordly hover:bg-panel-2 disabled:cursor-default"
    >
      <Ordlak state={state} size={26} className="shrink-0" />
      <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
        <span
          className={`truncate text-[11.5px] font-semibold ${
            alertReason ? "text-coral" : "text-text"
          }`}
        >
          {headline}
        </span>
        <span className="o-mono truncate text-[9.5px] text-text-3">{detail}</span>
      </span>
    </button>
  );
}

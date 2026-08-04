/**
 * Maszyna stanów synchronizacji na mobile - ta sama, co na desktopie
 * (sekcja 3.2 specyfikacji), bo Ordi ma zachowywać się identycznie
 * w obu aplikacjach.
 *
 *   SPOCZYNEK  ->  PRACA  ->  SUKCES  ->  SPOCZYNEK
 *      idle       think      happy       idle
 *                >=1700ms    1900ms
 *
 * Synchronizacja to JEDYNE działanie w całej aplikacji mobilnej
 * (sekcja 1). Wszystko inne to podgląd - dlatego stan tej jednej akcji
 * mieszka w kontekście, a nie w ekranie: pigułka w nagłówku i skeleton
 * w treści zakładki muszą reagować na to samo zdarzenie.
 */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useTriggerSync } from "@/api/hooks";
import type { MascotPose } from "@/components/Mascot";

/** Czasy 1:1 z tabelą w sekcji 2.6 specyfikacji. */
const WORK_PHASE_MIN_MS = 1700;
const SUCCESS_PHASE_MS = 1900;

export type SyncPhase = "idle" | "working" | "success";

interface SyncContextValue {
  phase: SyncPhase;
  pose: MascotPose;
  title: string;
  subtitle: string;
  /** Czy treść zakładki ma pokazać skeleton zamiast listy (sekcja 6.3 pkt 3). */
  isBusy: boolean;
  sync: () => void;
}

const SyncContext = React.createContext<SyncContextValue | null>(null);

function humanizeSince(date: Date | null): string {
  if (!date) return "Dotknij, aby odświeżyć";
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "Przed chwilą · dotknij, aby odświeżyć";
  if (minutes < 60) return `${minutes} min temu · dotknij, aby odświeżyć`;
  const hours = Math.floor(minutes / 60);
  return `${hours} godz. temu · dotknij, aby odświeżyć`;
}

function orderWord(n: number): string {
  if (n === 1) return "nowe zamówienie";
  const few = n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14);
  return few ? "nowe zamówienia" : "nowych zamówień";
}

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = React.useState<SyncPhase>("idle");
  const [lastSyncAt, setLastSyncAt] = React.useState<Date | null>(null);
  const [successSubtitle, setSuccessSubtitle] = React.useState("");
  const busy = React.useRef(false);
  const queryClient = useQueryClient();
  const triggerSync = useTriggerSync();

  // Odświeża podpis "N min temu" bez czekania na kolejną synchronizację.
  const [, tick] = React.useReducer((n: number) => n + 1, 0);
  React.useEffect(() => {
    const timer = setInterval(tick, 30_000);
    return () => clearInterval(timer);
  }, []);

  const sync = React.useCallback(() => {
    // Blokada ponownego uruchomienia w trakcie cyklu jest obowiązkowa
    // (sekcja 3.2) - bez niej podwójne dotknięcie pigułki rozjeżdża
    // fazy i Ordi zostaje w pozie "think".
    if (busy.current) return;
    busy.current = true;
    setPhase("working");

    const startedAt = Date.now();

    void (async () => {
      let newOrders = 0;
      let failed = false;

      try {
        const result = await triggerSync.mutateAsync();
        newOrders = result.new_orders_count;
      } catch {
        failed = true;
      }

      // Faza pracy nie może być krótsza niż 1700 ms - inaczej "pop"
      // Ordiego mignąłby, zanim użytkownik zdąży go zauważyć.
      const elapsed = Date.now() - startedAt;
      if (elapsed < WORK_PHASE_MIN_MS) {
        await new Promise((resolve) => setTimeout(resolve, WORK_PHASE_MIN_MS - elapsed));
      }

      if (failed) {
        setPhase("idle");
        busy.current = false;
        return;
      }

      setLastSyncAt(new Date());
      setSuccessSubtitle(
        newOrders > 0 ? `Przed chwilą · ${newOrders} ${orderWord(newOrders)}` : "Przed chwilą · bez zmian"
      );
      setPhase("success");
      void queryClient.invalidateQueries();

      setTimeout(() => {
        setPhase("idle");
        busy.current = false;
      }, SUCCESS_PHASE_MS);
    })();
  }, [queryClient, triggerSync]);

  const value = React.useMemo<SyncContextValue>(() => {
    const pose: MascotPose =
      phase === "working" ? "thinking" : phase === "success" ? "happy" : "default";
    const title =
      phase === "working"
        ? "Synchronizuję…"
        : phase === "success"
          ? "Wszystko aktualne"
          : "Zsynchronizowano";
    const subtitle =
      phase === "working"
        ? "Allegro · Amazon · OLX · eBay"
        : phase === "success"
          ? successSubtitle
          : humanizeSince(lastSyncAt);

    return { phase, pose, title, subtitle, isBusy: phase === "working", sync };
  }, [phase, successSubtitle, lastSyncAt, sync]);

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSync(): SyncContextValue {
  const ctx = React.useContext(SyncContext);
  if (!ctx) {
    throw new Error("useSync musi być użyty wewnątrz SyncProvider");
  }
  return ctx;
}

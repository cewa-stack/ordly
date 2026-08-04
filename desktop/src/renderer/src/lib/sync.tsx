/**
 * Maszyna stanow synchronizacji - sygnaturowy element produktu
 * (sekcja 3.2 specyfikacji), wspolny dla wskaznika Ordiego w pasku
 * bocznym, skrotu Ctrl+R i przycisku "Synchronizuj" na ekranie Start.
 *
 *   SPOCZYNEK  ->  PRACA  ->  SUKCES  ->  SPOCZYNEK
 *      idle       think      happy       idle
 *                >=1700ms    1900ms
 *
 * Roznica wobec koncepcji: faza PRACY trwa co najmniej 1700 ms, ale
 * konczy sie dopiero, gdy realne zadanie do Pi wroci. Sztywne 1700 ms
 * klamaloby przy wolnym laczu - Ordi pokazywalby "gotowe", zanim dane
 * faktycznie przyszly.
 *
 * Blokada ponownego uruchomienia w trakcie cyklu (flaga `busy`) jest
 * obowiazkowa - wymog specyfikacji.
 */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "./toast";
import type { OrdiPose } from "../components/Mascot";

/** Czasy 1:1 z tabela w sekcji 2.6. */
const WORK_PHASE_MIN_MS = 1700;
const SUCCESS_PHASE_MS = 1900;

export type SyncPhase = "idle" | "working" | "success";

interface SyncContextValue {
  phase: SyncPhase;
  pose: OrdiPose;
  /** Tytul wskaznika, np. "Ordi czuwa" / "Synchronizuję…". */
  title: string;
  /** Podtytul, np. "Synchronizacja 3 min temu". */
  subtitle: string;
  lastSyncAt: Date | null;
  sync: () => void;
}

const SyncContext = React.createContext<SyncContextValue | null>(null);

function humanizeSince(date: Date | null): string {
  if (!date) return "Jeszcze nie synchronizowano";
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "Synchronizacja przed chwilą";
  if (minutes === 1) return "Synchronizacja 1 min temu";
  if (minutes < 60) return `Synchronizacja ${minutes} min temu`;
  const hours = Math.floor(minutes / 60);
  return hours === 1 ? "Synchronizacja 1 godz. temu" : `Synchronizacja ${hours} godz. temu`;
}

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = React.useState<SyncPhase>("idle");
  const [lastSyncAt, setLastSyncAt] = React.useState<Date | null>(null);
  const [successSubtitle, setSuccessSubtitle] = React.useState("");
  const busy = React.useRef(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  // Odswieza podtytul "N min temu" bez czekania na kolejna synchronizacje.
  const [, forceTick] = React.useReducer((n: number) => n + 1, 0);
  React.useEffect(() => {
    const timer = window.setInterval(forceTick, 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const sync = React.useCallback(() => {
    if (busy.current) return;
    busy.current = true;
    setPhase("working");

    const startedAt = Date.now();

    void (async () => {
      const ordersResult = await window.ordly.orders.sync();
      const mailResult = await window.ordly.mailbox.sync();

      // Faza pracy nie moze byc krotsza niz 1700 ms - inaczej "pop"
      // Ordiego mignalby, zanim uzytkownik zdazy go zauwazyc.
      const elapsed = Date.now() - startedAt;
      if (elapsed < WORK_PHASE_MIN_MS) {
        await new Promise((resolve) =>
          window.setTimeout(resolve, WORK_PHASE_MIN_MS - elapsed)
        );
      }

      if (!ordersResult.ok) {
        setPhase("idle");
        busy.current = false;
        toast.error("Synchronizacja nie doszła do skutku", ordersResult.message);
        return;
      }

      const newOrders = ordersResult.data.new_orders_count;
      const newMail = mailResult.ok ? mailResult.data.new_count : 0;
      const parts: string[] = [];
      if (newOrders > 0) parts.push(`${newOrders} ${orderWord(newOrders)}`);
      if (newMail > 0) parts.push(`${newMail} ${mailWord(newMail)}`);
      const summary = parts.length > 0 ? parts.join(" · ") : "bez zmian";

      setLastSyncAt(new Date());
      setSuccessSubtitle(`Przed chwilą · ${summary}`);
      setPhase("success");

      // Odswiezenie wszystkich widokow dopiero PO zakonczeniu zapisu na Pi.
      void queryClient.invalidateQueries();

      if (!mailResult.ok) {
        // Poczta jest opcjonalna (IMAP bywa wylaczony), wiec jej blad nie
        // przewraca calej synchronizacji - ale musi byc widoczny.
        // 404 ma osobny komunikat, bo znaczy cos zupelnie innego niz awaria
        // skrzynki: na Pi chodzi backend sprzed dodania `/mail/sync`.
        toast.error(
          "Skrzynka nie odpowiedziała",
          mailResult.status === 404
            ? "Na Pi działa starsza wersja backendu - wgraj aktualizację i zrestartuj usługę ordly."
            : mailResult.message
        );
      } else {
        toast.success("Wszystko aktualne", summary === "bez zmian" ? "Bez zmian" : summary);
      }

      window.setTimeout(() => {
        setPhase("idle");
        busy.current = false;
      }, SUCCESS_PHASE_MS);
    })();
  }, [queryClient, toast]);

  const value = React.useMemo<SyncContextValue>(() => {
    const pose: OrdiPose =
      phase === "working" ? "think" : phase === "success" ? "happy" : "idle";
    const title =
      phase === "working"
        ? "Synchronizuję…"
        : phase === "success"
          ? "Wszystko aktualne"
          : "Ordi czuwa";
    const subtitle =
      phase === "working"
        ? "Allegro · Amazon · OLX · eBay"
        : phase === "success"
          ? successSubtitle
          : humanizeSince(lastSyncAt);
    return { phase, pose, title, subtitle, lastSyncAt, sync };
  }, [phase, successSubtitle, lastSyncAt, sync]);

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

function orderWord(n: number): string {
  if (n === 1) return "nowe zamówienie";
  return n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)
    ? "nowe zamówienia"
    : "nowych zamówień";
}

function mailWord(n: number): string {
  if (n === 1) return "nowy mail";
  return n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)
    ? "nowe maile"
    : "nowych maili";
}

export function useSync(): SyncContextValue {
  const ctx = React.useContext(SyncContext);
  if (!ctx) {
    throw new Error("useSync musi być użyty wewnątrz SyncProvider");
  }
  return ctx;
}

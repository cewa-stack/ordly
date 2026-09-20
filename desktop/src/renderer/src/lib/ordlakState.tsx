/**
 * Stan Ordlaka jako POCHODNA DANYCH (sekcja 6 instrukcji "Nokturn").
 *
 * Zasada trzecia redesignu: "Ordlak zyje, a nie pozuje". Kazdy stan ma
 * wyzwalacz w systemie; nie ma stanow losowych ani dekoracyjnych.
 * Jesli czegos nie da sie powiazac ze zdarzeniem - taki stan nie powstaje.
 *
 *   sync   - trwa cykl synchronizacji albo reczne odswiezenie
 *   happy  - 1,2 s po nowym zamowieniu albo oznaczeniu paczki jako
 *            wyslanej, potem wraca do idle
 *   alert  - druga nieudana synchronizacja poczty, wygasly token
 *            Allegro, brak lacznosci z Pi
 *   think  - Ordlak generuje odpowiedz w rozmowie
 *   sleep  - po 22:00 bez zdarzen
 *   idle   - wszystko pozostale
 *
 * Pierwszenstwo jest wazniejsze niz lista: alarm bije mocniej niz
 * synchronizacja, bo synchronizacja wroci sama, a awaria nie.
 */
import * as React from "react";
import type { OrdlakState } from "../components/Ordlak";
import { useSync } from "./sync";

/** "1,2 s po nowym zamowieniu (...), potem wraca do idle". */
const CELEBRATION_MS = 1200;
/** Godzina, po ktorej Ordlak zasypia, o ile nic sie nie dzieje. */
const SLEEP_FROM_HOUR = 22;
const SLEEP_TO_HOUR = 6;

/** Zrodla alarmu. Klucz zamiast `boolean`, zeby dwa powody sie nie zjadaly. */
export type OrdlakAlert = "pi" | "mail" | "allegro";

const ALERT_TEXT: Record<OrdlakAlert, string> = {
  pi: "Brak łączności z Pi",
  mail: "Skrzynka nie odpowiada",
  allegro: "Token Allegro wygasł",
};

interface OrdlakStateValue {
  /** Stan maskotki pokazywany w pasku bocznym i na karcie powitalnej. */
  state: OrdlakState;
  /** Powod alarmu albo `null`. Stan komunikuje TEKST, nie sama maskotka. */
  alertReason: string | null;
  /** Blysk radosci po udanej akcji uzytkownika. */
  celebrate: () => void;
  /** Wlacza/wylacza `think` na czas generowania odpowiedzi asystenta. */
  setThinking: (thinking: boolean) => void;
  /** Zglasza albo odwoluje jeden powod alarmu. */
  setAlert: (alert: OrdlakAlert, active: boolean) => void;
}

const OrdlakStateContext = React.createContext<OrdlakStateValue | null>(null);

function isQuietHour(now: Date): boolean {
  const hour = now.getHours();
  return hour >= SLEEP_FROM_HOUR || hour < SLEEP_TO_HOUR;
}

export function OrdlakStateProvider({ children }: { children: React.ReactNode }) {
  const { phase, mailFailedTwice } = useSync();
  const [celebrating, setCelebrating] = React.useState(false);
  const [thinking, setThinking] = React.useState(false);
  const [alerts, setAlerts] = React.useState<Set<OrdlakAlert>>(() => new Set());
  const celebrationTimer = React.useRef(0);

  // Zegar pory dnia. Minuta wystarczy - granica zasypiania jest pelna
  // godzina, a czestsze budzenie Reacta niczego nie poprawia.
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const celebrate = React.useCallback(() => {
    window.clearTimeout(celebrationTimer.current);
    setCelebrating(true);
    celebrationTimer.current = window.setTimeout(
      () => setCelebrating(false),
      CELEBRATION_MS
    );
  }, []);

  React.useEffect(() => () => window.clearTimeout(celebrationTimer.current), []);

  const setAlert = React.useCallback((alert: OrdlakAlert, active: boolean) => {
    setAlerts((prev) => {
      if (prev.has(alert) === active) return prev;
      const next = new Set(prev);
      if (active) next.add(alert);
      else next.delete(alert);
      return next;
    });
  }, []);

  // Druga nieudana synchronizacja poczty z rzedu - nie pierwsza. Jedna
  // nieudana proba zdarza sie przy przelaczeniu sieci i nie jest awaria.
  React.useEffect(() => {
    setAlert("mail", mailFailedTwice);
  }, [mailFailedTwice, setAlert]);

  const value = React.useMemo<OrdlakStateValue>(() => {
    const alertList = [...alerts];
    const state: OrdlakState = alertList.length > 0
      ? "alert"
      : celebrating || phase === "success"
        ? "happy"
        : phase === "working"
          ? "sync"
          : thinking
            ? "think"
            : isQuietHour(now)
              ? "sleep"
              : "idle";

    return {
      state,
      alertReason:
        alertList.length === 0
          ? null
          : alertList.length === 1
            ? ALERT_TEXT[alertList[0]]
            : `${alertList.length} rzeczy wymagają uwagi`,
      celebrate,
      setThinking,
      setAlert,
    };
  }, [alerts, celebrating, phase, thinking, now, celebrate, setAlert]);

  return (
    <OrdlakStateContext.Provider value={value}>{children}</OrdlakStateContext.Provider>
  );
}

export function useOrdlakState(): OrdlakStateValue {
  const ctx = React.useContext(OrdlakStateContext);
  if (!ctx) {
    throw new Error("useOrdlakState musi być użyty wewnątrz OrdlakStateProvider");
  }
  return ctx;
}

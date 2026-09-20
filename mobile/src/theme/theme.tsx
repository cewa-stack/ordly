/**
 * Przelaczanie atmosfer (sekcja 11 instrukcji "Nokturn").
 *
 * GODZINA plus RECZNE NADPISANIE w Ustawieniach - decyzja 2 z sekcji 16.
 * Czujnik jasnosci jest kuszacy, ale skacze przy kazdym przejsciu pod
 * lampa. Domyslnie: dzien 6:00-20:00.
 *
 * Kazdy komponent czyta kolory z tego kontekstu. Zaden nie pyta, ktora
 * atmosfera jest aktywna - klucze palety sa identyczne w obu zestawach.
 */
import * as React from "react";
import { AccessibilityInfo } from "react-native";

import { day, night, type Palette } from "./colors";
import { loadThemePreference, saveThemePreference } from "@/utils/secureStorage";

/** Dzien trwa 6:00-20:00 (sekcja 11). */
const DAY_FROM_HOUR = 6;
const DAY_TO_HOUR = 20;

export type ThemeMode = "night" | "day";
/** `auto` = wedlug godziny. Pozostale dwie to reczne nadpisanie. */
export type ThemePreference = "auto" | ThemeMode;

interface ThemeValue {
  /** Aktywna paleta. */
  c: Palette;
  /** Ktora atmosfera faktycznie swieci. */
  mode: ThemeMode;
  /** Ustawienie uzytkownika (`auto` dopoki nie nadpisze). */
  preference: ThemePreference;
  setPreference: (next: ThemePreference) => void;
  /** `prefers-reduced-motion` systemu - maskotka zostaje w pozie spoczynku. */
  reduceMotion: boolean;
}

const ThemeContext = React.createContext<ThemeValue | null>(null);

function modeForHour(date: Date): ThemeMode {
  const hour = date.getHours();
  return hour >= DAY_FROM_HOUR && hour < DAY_TO_HOUR ? "day" : "night";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = React.useState<ThemePreference>("auto");
  const [autoMode, setAutoMode] = React.useState<ThemeMode>(() => modeForHour(new Date()));
  const [reduceMotion, setReduceMotion] = React.useState(false);

  // Wybor uzytkownika przezywa restart aplikacji - inaczej "zawsze noc"
  // trzeba by ustawiac po kazdym uruchomieniu.
  React.useEffect(() => {
    void loadThemePreference().then((stored) => {
      if (stored === "auto" || stored === "day" || stored === "night") {
        setPreferenceState(stored);
      }
    });
  }, []);

  // Granica atmosfery to pelna godzina, wiec minuta wystarczy.
  React.useEffect(() => {
    const timer = setInterval(() => setAutoMode(modeForHour(new Date())), 60_000);
    return () => clearInterval(timer);
  }, []);

  // Odpowiednik `prefers-reduced-motion` z sekcji 14 po stronie systemu.
  React.useEffect(() => {
    let alive = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (alive) setReduceMotion(enabled);
    });
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReduceMotion
    );
    return () => {
      alive = false;
      subscription.remove();
    };
  }, []);

  const setPreference = React.useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    void saveThemePreference(next);
  }, []);

  const value = React.useMemo<ThemeValue>(() => {
    const mode: ThemeMode = preference === "auto" ? autoMode : preference;
    return {
      c: mode === "day" ? day : night,
      mode,
      preference,
      setPreference,
      reduceMotion,
    };
  }, [preference, autoMode, reduceMotion, setPreference]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme musi być użyty wewnątrz ThemeProvider");
  return ctx;
}

/**
 * Arkusz stylow zalezny od atmosfery.
 *
 *   const styles = useThemedStyles(createStyles);
 *
 * `factory` musi byc STALA modulowa (nie funkcja tworzona w renderze) -
 * inaczej `useMemo` przeliczy arkusz przy kazdym renderze.
 */
export function useThemedStyles<T>(factory: (c: Palette) => T): T {
  const { c } = useTheme();
  return React.useMemo(() => factory(c), [c, factory]);
}

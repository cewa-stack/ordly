/**
 * Motyw React Navigation - budowany z AKTYWNEJ atmosfery (sekcja 11).
 *
 * Wczesniej byla tu jedna stala. Przy dwoch atmosferach to za malo:
 * tlo nawigatora zostawaloby jasne po zapadnieciu nocy i kazde przejscie
 * miedzy ekranami dawaloby biale mrugniecie pod ciemnym ekranem.
 */
import { DarkTheme, DefaultTheme, type Theme } from "@react-navigation/native";

import type { Palette } from "@/theme/colors";
import type { ThemeMode } from "@/theme/theme";

export function navigationThemeFor(c: Palette, mode: ThemeMode): Theme {
  const base = mode === "day" ? DefaultTheme : DarkTheme;
  return {
    ...base,
    colors: {
      ...base.colors,
      background: c.bg,
      card: c.card,
      text: c.tx,
      border: c.line,
      primary: c.acc,
      notification: c.coral,
    },
  };
}

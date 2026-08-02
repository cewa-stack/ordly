/**
 * Motyw React Navigation - bez tego przejścia między ekranami błyskają
 * na biało (domyślny `DefaultTheme` zakłada jasne tło).
 */
import { DarkTheme, type Theme } from "@react-navigation/native";

import { colors } from "@/theme/colors";

export const navigationTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.background,
    text: colors.text,
    border: colors.border,
    primary: colors.primary,
    notification: colors.danger,
  },
};

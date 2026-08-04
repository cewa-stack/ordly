/**
 * Motyw React Navigation.
 *
 * Bazą jest `DefaultTheme` (jasny), bo mobile jest jasny celowo -
 * sekcja 2.2 specyfikacji. Wcześniej stał tu `DarkTheme`; zostawienie
 * go po zmianie palety dawałoby ciemne błyski przy przejściach między
 * ekranami, mimo że same ekrany są jasne.
 */
import { DefaultTheme, type Theme } from "@react-navigation/native";

import { colors } from "@/theme/colors";

export const navigationTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.background,
    card: colors.surface,
    text: colors.text,
    border: colors.border,
    primary: colors.primary,
    notification: colors.danger,
  },
};

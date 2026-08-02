/**
 * Paleta kolorów ORDLY Mobile — tokeny UI motywu ciemnego wg
 * "ORDLY — Kompletny projekt UX/UI" §15.1. Pochodna kolorów księgi znaku
 * (#3EAAAF / #313E37 / #F0F4EF): primary to rozjaśniony Brand Teal,
 * zoptymalizowany kontrastowo pod tło #0D1117.
 * Nie dodawaj tu kolorów "na oko" — najpierw token w specyfikacji.
 */
export const colors = {
  // Akcenty
  primary: "#56E0D0",
  secondary: "#4ABFAF",
  accent: "#7FF7EA",

  // Powierzchnie
  background: "#0D1117",
  surface: "#161B22",
  surfaceRaised: "#1B222B",
  border: "#2A2F38",

  // Semantyczne
  success: "#35D07F",
  warning: "#F5B942",
  danger: "#FF5C5C",

  // Tekst
  text: "#FFFFFF",
  textSecondary: "#9CA3AF",
  textDim: "#6B7280",

  // Tekst na wypełnieniu primary (CTA)
  onPrimary: "#0D1117",

  // Tła statusów: kolor przy ~12% krycia + pełny kolor tekstu (§15.10)
  primaryTint: "rgba(86,224,208,0.12)",
  primaryBorder: "rgba(86,224,208,0.4)",
  successTint: "rgba(53,208,127,0.12)",
  warningTint: "rgba(245,185,66,0.12)",
  dangerTint: "rgba(255,92,92,0.12)",
} as const;

export type StockStatus = "ok" | "warning" | "critical";

export const stockStatusColor: Record<StockStatus, string> = {
  ok: colors.success,
  warning: colors.warning,
  critical: colors.danger,
};

/** Mapa statusów zamówień (§15.10): Nowe primary · Pakowanie warning ·
 *  Wysłane success · Anulowane danger. Klucze = etykiety z fulfillmentLabel. */
export const orderStatusColor: Record<string, string> = {
  Nowe: colors.primary,
  Pakowanie: colors.warning,
  Wysłane: colors.success,
  Anulowane: colors.danger,
};

export const orderStatusTint: Record<string, string> = {
  Nowe: colors.primaryTint,
  Pakowanie: colors.warningTint,
  Wysłane: colors.successTint,
  Anulowane: colors.dangerTint,
};

/**
 * Paleta ORDLY Mobile - motyw JASNY, wg sekcji 2.2 specyfikacji
 * (`ORDLY-spec-implementacyjny.md`).
 *
 * Mobile jest jasny CELOWO: używa się go w magazynie i w słońcu, gdzie
 * ciemny motyw traci czytelność. To nie jest inwersja desktopu - to
 * osobna, świadoma paleta. Desktop zostaje dark-mode-first i nie ma
 * wariantu jasnego.
 *
 * Nie dodawaj tu kolorów "na oko" - najpierw wartość w specyfikacji,
 * potem tutaj.
 */
export const colors = {
  // Akcenty. `primary` jest CIEMNIEJSZY niż na desktopie (--teal-deep,
  // nie --teal-bright) - jasny teal na bieli nie przechodzi kontrastu.
  primary: "#1F7D80",
  secondary: "#3EAAAF",
  accent: "#5FD9CC",

  // Powierzchnie
  background: "#EFF4F1",
  surface: "#FFFFFF",
  surfaceRaised: "#E4EDE8",
  border: "rgba(35,43,39,0.055)",
  borderStrong: "rgba(35,43,39,0.12)",

  // Semantyczne
  success: "#166F72",
  warning: "#9A6F22",
  danger: "#C4523A",

  // Tekst
  text: "#232B27",
  textSecondary: "#68766F",
  textDim: "#96A49E",
  textOnIcon: "#9CAAA4",

  // Tekst na wypełnieniu primary (CTA)
  onPrimary: "#FFFFFF",

  // Tła statusów w wariancie jasnym (sekcja 2.4)
  primaryTint: "#D9F0EC",
  primaryBorder: "rgba(31,125,128,0.3)",
  successTint: "#D9F0EC",
  warningTint: "#FBF0D8",
  dangerTint: "#FFE5D8",

  // Tor paska zapasu (2.2)
  trackStock: "#E7EDEA",

  // Cień karty (2.6) - w RN rozbity na osobne właściwości.
  cardShadow: "rgba(35,43,39,0.06)",
} as const;

export type StockStatus = "ok" | "warning" | "critical";

export const stockStatusColor: Record<StockStatus, string> = {
  ok: colors.primary,
  warning: colors.warning,
  critical: colors.danger,
};

/**
 * Kolory kanałów sprzedaży (sekcja 2.3), wariant jasny.
 *
 * Każdy kanał ma STAŁY kolor w obu motywach - użytkownik uczy się ich
 * jako etykiet, więc tych przypisań nigdy się nie zmienia.
 */
export const marketplaceColor: Record<string, { background: string; text: string }> = {
  allegro: { background: "#FFE7DE", text: "#C4523A" },
  // Allegro Lokalnie: TEN SAM odcień co Allegro.pl (bo to ta sama
  // rodzina serwisów), ale słabszy - kanał bez API, w którym ORDLY
  // tylko pokazuje, a zarządza się na stronie. Amber jest zajęty przez
  // Amazon, a dwa kanały w jednym kolorze przestałyby być etykietami.
  allegro_lokalnie: { background: "#FFF1EC", text: "#D9765C" },
  amazon: { background: "#FBF0D8", text: "#9A6F22" },
  olx: { background: "#E9E7FE", text: "#5A4FD1" },
  ebay: { background: "#D9F0EC", text: "#166F72" },
};

/** Mapa statusów zamówień (sekcja 2.4) - klucze = etykiety z fulfillmentLabel. */
export const orderStatusColor: Record<string, string> = {
  Nowe: "#166F72",
  "Do spakowania": "#C4523A",
  Pakowanie: "#C4523A",
  Wysłane: "#68766F",
  Odebrane: "#68766F",
  Anulowane: "#9A6F22",
};

export const orderStatusTint: Record<string, string> = {
  Nowe: "#D9F0EC",
  "Do spakowania": "#FFE5D8",
  Pakowanie: "#FFE5D8",
  Wysłane: "#ECEFED",
  Odebrane: "#ECEFED",
  Anulowane: "#FBF0D8",
};

/**
 * Skala typografii ORDLY Mobile — "ORDLY — Kompletny projekt UX/UI" §15.2.
 * Display/Title w wadze Bold, dane liczbowe zawsze z `tabular-nums`.
 * Siatka: baza 4 pt, rytm 8 pt (§15.3). Promienie: 12 (pola/chipy),
 * 16 (karty), 20 (karty hero), 24 (sheety).
 */
import type { TextStyle } from "react-native";

const tabularNums: Pick<TextStyle, "fontVariant"> = {
  fontVariant: ["tabular-nums"],
};

export const typography = {
  /** Kwoty KPI, hero — Display 30/36 Bold. */
  display: { fontSize: 30, fontWeight: "700", lineHeight: 36, ...tabularNums } satisfies TextStyle,
  /** Large titles ekranów — Title 1 24/30 Bold. */
  title1: { fontSize: 24, fontWeight: "700", lineHeight: 30 } satisfies TextStyle,
  /** Nagłówki sekcji i sheetów — Title 2 19/25 Bold. */
  title2: { fontSize: 19, fontWeight: "700", lineHeight: 25 } satisfies TextStyle,
  /** Tytuły kart, top bar — Headline 15.5/21 SemiBold. */
  headline: { fontSize: 15.5, fontWeight: "600", lineHeight: 21 } satisfies TextStyle,
  /** Tekst podstawowy — Body 15/22. */
  body: { fontSize: 15, fontWeight: "400", lineHeight: 22 } satisfies TextStyle,
  /** Treści kart, nazwiska klientów — Callout 14/20. */
  callout: { fontSize: 14, fontWeight: "400", lineHeight: 20 } satisfies TextStyle,
  calloutSemibold: { fontSize: 14, fontWeight: "600", lineHeight: 20 } satisfies TextStyle,
  /** Metadane, opisy — Footnote 12/17. */
  footnote: { fontSize: 12, fontWeight: "400", lineHeight: 17 } satisfies TextStyle,
  /** Timestampy, etykiety — Caption 11/15 Medium. */
  caption: { fontSize: 11, fontWeight: "500", lineHeight: 15 } satisfies TextStyle,
  /** Nr zamówień, SKU, tracking — mono/tabular 12/17. */
  mono: { fontSize: 12, fontWeight: "500", lineHeight: 17, ...tabularNums } satisfies TextStyle,

  // Role pochodne (używane w wielu miejscach)
  sectionTitle: { fontSize: 15.5, fontWeight: "600", lineHeight: 21 } satisfies TextStyle,
  statValue: { fontSize: 18, fontWeight: "700", lineHeight: 23, ...tabularNums } satisfies TextStyle,
  rowAmount: { fontSize: 15, fontWeight: "700", lineHeight: 20, ...tabularNums } satisfies TextStyle,
  tabLabel: { fontSize: 9.5, fontWeight: "600" } satisfies TextStyle,
  buttonLabel: { fontSize: 15, fontWeight: "600" } satisfies TextStyle,
  badgeLabel: { fontSize: 11, fontWeight: "600" } satisfies TextStyle,
} as const;

export const radii = {
  /** Miniatury, małe elementy. */
  xs: 10,
  /** Pola, chipy prostokątne, wyszukiwarka. */
  sm: 12,
  /** Pola formularzy 56 pt. */
  md: 14,
  /** Karty. */
  lg: 16,
  /** Karty hero. */
  xl: 20,
  /** Sheety, dialogi. */
  sheet: 24,
  /** Pastylki, FAB, awatary. */
  full: 999,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
} as const;

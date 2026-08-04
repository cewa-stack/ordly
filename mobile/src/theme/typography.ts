/**
 * Skala typografii ORDLY Mobile - sekcja 2.5 specyfikacji
 * (`ORDLY-spec-implementacyjny.md`), część "Skala mobilna".
 *
 * Skala jest CIASNIEJSZA niż na desktopie i celowo drobniejsza niż
 * poprzednia wersja tego pliku: telefon pokazuje listy do przejrzenia
 * jednym rzutem oka, a nie do czytania.
 *
 * Reguła twarda z sekcji 2.5: każda liczba, którą użytkownik może
 * porównać z inną liczbą, jest tabelaryczna. Stąd `tabularNums` przy
 * wszystkich rolach niosących dane maszynowe.
 */
import type { TextStyle } from "react-native";

const tabularNums: Pick<TextStyle, "fontVariant"> = {
  fontVariant: ["tabular-nums"],
};

export const typography = {
  /** Powitanie w nagłówku - 17/600 (sekcja 2.5, skala mobilna). */
  greeting: { fontSize: 17, fontWeight: "600", lineHeight: 22 } satisfies TextStyle,
  /** Nagłówek zakładki - 15.5/600. */
  tabHeading: { fontSize: 15.5, fontWeight: "600", lineHeight: 21 } satisfies TextStyle,
  /** Tytuł karty - 13/600. */
  cardTitle: { fontSize: 13, fontWeight: "600", lineHeight: 18 } satisfies TextStyle,
  /** Treść karty - 12, line-height 1.5. */
  cardBody: { fontSize: 12, fontWeight: "400", lineHeight: 18 } satisfies TextStyle,
  /** Czas / SKU - 9.5 mono. */
  meta: { fontSize: 9.5, fontWeight: "500", lineHeight: 13, ...tabularNums } satisfies TextStyle,
  /** Etykieta zakładki - 9/500. */
  tabLabel: { fontSize: 9, fontWeight: "500" } satisfies TextStyle,

  // Role pochodne używane na ekranach szczegółów i formularzach.
  display: { fontSize: 28, fontWeight: "700", lineHeight: 34, ...tabularNums } satisfies TextStyle,
  title1: { fontSize: 22, fontWeight: "700", lineHeight: 28 } satisfies TextStyle,
  title2: { fontSize: 17, fontWeight: "600", lineHeight: 23 } satisfies TextStyle,
  headline: { fontSize: 15, fontWeight: "600", lineHeight: 20 } satisfies TextStyle,
  body: { fontSize: 14, fontWeight: "400", lineHeight: 21 } satisfies TextStyle,
  callout: { fontSize: 13, fontWeight: "400", lineHeight: 19 } satisfies TextStyle,
  calloutSemibold: { fontSize: 13, fontWeight: "600", lineHeight: 19 } satisfies TextStyle,
  footnote: { fontSize: 12, fontWeight: "400", lineHeight: 17 } satisfies TextStyle,
  caption: { fontSize: 11, fontWeight: "500", lineHeight: 15 } satisfies TextStyle,
  /** Nr zamówień, SKU, kwoty - dane maszynowe. */
  mono: { fontSize: 11.5, fontWeight: "500", lineHeight: 16, ...tabularNums } satisfies TextStyle,

  sectionTitle: { fontSize: 15, fontWeight: "600", lineHeight: 20 } satisfies TextStyle,
  statValue: { fontSize: 18, fontWeight: "700", lineHeight: 23, ...tabularNums } satisfies TextStyle,
  /** Kwota na karcie - 12.5/600 mono (sekcja 6.2). */
  rowAmount: {
    fontSize: 12.5,
    fontWeight: "600",
    lineHeight: 17,
    ...tabularNums,
  } satisfies TextStyle,
  buttonLabel: { fontSize: 14, fontWeight: "600" } satisfies TextStyle,
  badgeLabel: { fontSize: 10, fontWeight: "600" } satisfies TextStyle,
} as const;

/** Promienie z sekcji 2.6 - karta mobilna 17, pasek zakładek 21. */
export const radii = {
  xs: 8,
  sm: 10,
  md: 12,
  lg: 17,
  xl: 21,
  sheet: 24,
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

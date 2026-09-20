/**
 * Typografia ORDLY Mobile - sekcja 5 instrukcji "Nokturn".
 *
 * Trzy kroje, ladowane lokalnie przez `expo-font` z paczek
 * `@expo-google-fonts/*` (prawdziwe pliki .ttf w bundlu, bez CDN):
 *
 *   Bricolage Grotesque  - role wyroznione
 *   Instrument Sans      - tresc, wiersze list
 *   JetBrains Mono       - cyfry, numery, godziny, etykiety wersalikami
 *
 * ZASADA TWARDA: Bricolage wylacznie w rolach wyroznionych - tytul
 * ekranu, powitanie, liczba na kaflu, naglowek panelu. NIGDY w wierszu
 * listy; tam zawsze Instrument Sans albo mono.
 *
 * Kazda liczba, ktora uzytkownik moze porownac z inna liczba, jest
 * tabelarna (`fontVariant: ["tabular-nums"]`). Bez tego kolumny rozjada
 * sie przy kazdej zmianie danych.
 *
 * W React Native NIE MA `fontWeight` dla wczytanych krojow - wage niesie
 * NAZWA RODZINY (`InstrumentSans_600SemiBold`). Podanie `fontWeight`
 * obok wlasnej rodziny jest w najlepszym razie ignorowane, a na
 * Androidzie potrafi podmienic krój na systemowy.
 */
import type { TextStyle } from "react-native";

/** Nazwy rodzin - takie same, jak klucze przekazane do `loadAsync`. */
export const family = {
  display: "BricolageGrotesque_700Bold",
  sans: "InstrumentSans_400Regular",
  sansMedium: "InstrumentSans_500Medium",
  sansSemibold: "InstrumentSans_600SemiBold",
  mono: "JetBrainsMono_500Medium",
  monoBold: "JetBrainsMono_600SemiBold",
} as const;

const tabular: Pick<TextStyle, "fontVariant"> = { fontVariant: ["tabular-nums"] };

/**
 * Role typograficzne. Nazwy odpowiadaja tabeli z sekcji 5, zeby dalo sie
 * je zestawic z instrukcja bez zgadywania.
 */
export const fonts = {
  /** Tytul ekranu - Bricolage 700 / 24 px (sekcja 11). */
  screenTitle: {
    fontFamily: family.display,
    fontSize: 24,
    lineHeight: 29,
    letterSpacing: -0.6,
  } satisfies TextStyle,

  /** Powitanie / tytul karty Ordlaka - Bricolage 700 / 27 px. */
  greeting: {
    fontFamily: family.display,
    fontSize: 27,
    lineHeight: 31,
    letterSpacing: -0.8,
  } satisfies TextStyle,

  /** Liczba na kaflu - Bricolage 700 / 26 px, tabelarna. */
  kpi: {
    fontFamily: family.display,
    fontSize: 26,
    lineHeight: 30,
    letterSpacing: -0.78,
    ...tabular,
  } satisfies TextStyle,

  /** Liczba na wierszu magazynu - Bricolage 700 / 21 px. */
  kpiSmall: {
    fontFamily: family.display,
    fontSize: 21,
    lineHeight: 25,
    letterSpacing: -0.5,
    ...tabular,
  } satisfies TextStyle,

  /** Naglowek sekcji / karty - Bricolage 700 / 14 px. */
  panelTitle: {
    fontFamily: family.display,
    fontSize: 14,
    lineHeight: 19,
    letterSpacing: -0.14,
  } satisfies TextStyle,

  /** Nazwisko w wierszu listy - Instrument Sans 600 / 13,5 px. */
  rowName: {
    fontFamily: family.sansSemibold,
    fontSize: 13.5,
    lineHeight: 18,
  } satisfies TextStyle,

  /** Tytul karty - Instrument Sans 600 / 14 px. */
  cardTitle: {
    fontFamily: family.sansSemibold,
    fontSize: 14,
    lineHeight: 19,
  } satisfies TextStyle,

  /** Tresc, opisy - Instrument Sans 400 / 12,5-13 px. */
  body: {
    fontFamily: family.sans,
    fontSize: 12.5,
    lineHeight: 18,
  } satisfies TextStyle,

  bodyLarge: {
    fontFamily: family.sans,
    fontSize: 14,
    lineHeight: 21,
  } satisfies TextStyle,

  /** Etykieta przycisku. */
  button: {
    fontFamily: family.sansSemibold,
    fontSize: 14,
    lineHeight: 19,
  } satisfies TextStyle,

  /** Cyfry, numery, godziny - mono 11,5 px. */
  mono: {
    fontFamily: family.mono,
    fontSize: 11.5,
    lineHeight: 16,
    letterSpacing: 0.35,
    ...tabular,
  } satisfies TextStyle,

  /** Kwota w wierszu - mono 600 / 13 px. */
  amount: {
    fontFamily: family.monoBold,
    fontSize: 13,
    lineHeight: 17,
    letterSpacing: 0.3,
    ...tabular,
  } satisfies TextStyle,

  /** Etykieta wersalikami - mono 9,5 px, tracking .15em. */
  eyebrow: {
    fontFamily: family.mono,
    fontSize: 9.5,
    lineHeight: 13,
    letterSpacing: 1.43,
    textTransform: "uppercase",
  } satisfies TextStyle,

  /** Etykieta kanalu - mono 8,5 px, STALE 60 px szerokosci (sekcja 7). */
  channel: {
    fontFamily: family.monoBold,
    fontSize: 8.5,
    lineHeight: 12,
    letterSpacing: 0.51,
    textTransform: "uppercase",
  } satisfies TextStyle,

  /** Etykieta zakladki - 9,5 px. */
  tabLabel: {
    fontFamily: family.sansMedium,
    fontSize: 9.5,
    lineHeight: 13,
  } satisfies TextStyle,

  /** Status w wierszu - 10,5 px waga 600. */
  status: {
    fontFamily: family.sansSemibold,
    fontSize: 10.5,
    lineHeight: 14,
  } satisfies TextStyle,

  /** Drobny tekst pod wierszem - 11,5 px. */
  caption: {
    fontFamily: family.sans,
    fontSize: 11.5,
    lineHeight: 15,
  } satisfies TextStyle,
} as const;

/**
 * Zgodnosc wstecz. Ekrany napisane przed redesignem wolaja
 * `typography.*`; kazda z tych rol wskazuje teraz na role z `fonts`,
 * zeby nie trzeba bylo przepisywac wszystkich ekranow naraz, a mimo to
 * caly tekst szedl juz nowymi krojami.
 */
export const typography = {
  greeting: fonts.greeting,
  tabHeading: fonts.panelTitle,
  cardTitle: fonts.cardTitle,
  cardBody: fonts.body,
  meta: fonts.mono,
  tabLabel: fonts.tabLabel,
  display: fonts.kpi,
  title1: fonts.screenTitle,
  title2: fonts.panelTitle,
  headline: fonts.cardTitle,
  body: fonts.bodyLarge,
  callout: fonts.body,
  calloutSemibold: fonts.rowName,
  footnote: fonts.caption,
  caption: fonts.caption,
  mono: fonts.mono,
  sectionTitle: fonts.panelTitle,
  statValue: fonts.kpiSmall,
  rowAmount: fonts.amount,
  buttonLabel: fonts.button,
  badgeLabel: fonts.status,
} as const;

/** Promienie z sekcji 12: karta 24/20/19, wiersz magazynu 17, pastylka 999. */
export const radii = {
  xs: 8,
  sm: 10,
  md: 14,
  lg: 19,
  xl: 21,
  card: 20,
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

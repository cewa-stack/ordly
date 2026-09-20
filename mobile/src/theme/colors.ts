/**
 * Paleta ORDLY Mobile - DWIE ATMOSFERY (sekcja 4 i 11 instrukcji
 * "ORDLY Nokturn").
 *
 * Ten sam uklad, ta sama hierarchia, inne podloze. Klucze sa IDENTYCZNE
 * w obu zestawach - dzieki temu zaden komponent nigdy nie pyta, ktora
 * atmosfera jest aktywna. Jesli komponent musi zapytac, klucz jest zle
 * zaprojektowany.
 *
 * `tx3` i `day.tx3` sa jasniejsze/ciemniejsze, niz moglo by sie wydawac
 * naturalne - to wartosci dobrane pod kontrast 4,5:1 dla tekstu 9-11 px.
 * Nie przyciemniaj ich "dla spokoju"; po zmianie `bg`/`card` przelicz je
 * ponownie.
 */

export interface Palette {
  /** tlo ekranu */
  bg: string;
  /** karta, panel */
  card: string;
  /** karta w karcie, tor paska, aktywna pozycja */
  card2: string;
  line: string;
  line2: string;
  /** tekst glowny */
  tx: string;
  /** tekst drugorzedny */
  tx2: string;
  /** tekst trzeciorzedny - etykiety 9-11 px */
  tx3: string;
  /** akcent: akcja, teraz */
  acc: string;
  /** tekst na wypelnieniu akcentem */
  onAcc: string;
  /** przygaszony akcent - tla pastylek i posiaty */
  accDim: string;
  /** czeka na Ciebie */
  coral: string;
  amber: string;
  violet: string;
  /** kolor cienia karty i galki */
  shadow: string;
}

export const night: Palette = {
  bg: "#0A1413",
  card: "#101D1B",
  card2: "#162724",
  line: "rgba(214,235,228,.075)",
  line2: "rgba(214,235,228,.15)",
  tx: "#EAF3EF",
  tx2: "#93A9A3",
  tx3: "#6F8882",
  acc: "#5FD9CC",
  onAcc: "#042320",
  accDim: "rgba(95,217,204,.16)",
  coral: "#FF8563",
  amber: "#F5C065",
  violet: "#A79BFF",
  shadow: "rgba(0,0,0,.9)",
};

export const day: Palette = {
  bg: "#EFF3F0",
  card: "#FFFFFF",
  card2: "#E6EDE9",
  line: "rgba(15,26,23,.08)",
  line2: "rgba(15,26,23,.16)",
  tx: "#0F1A17",
  tx2: "#5B6B66",
  tx3: "#64746E",
  acc: "#12706F",
  onAcc: "#FFFFFF",
  accDim: "rgba(18,112,111,.11)",
  coral: "#B4462E",
  amber: "#8A6218",
  violet: "#4F44C4",
  shadow: "rgba(15,26,23,.4)",
};

/**
 * Kolory kanalow sprzedazy. Przypisanie kanal -> barwa jest STALE w obu
 * atmosferach (uzytkownik uczy sie ich jako etykiet), ale etykiety w
 * atmosferze dziennej maja WLASNE tla: przezroczystosci z nocy gina
 * na bieli.
 */
export interface ChannelStyle {
  background: string;
  text: string;
}

export const channelNight: Record<string, ChannelStyle> = {
  allegro: { background: "rgba(255,133,99,.14)", text: "#FF8563" },
  // Allegro Lokalnie: TEN SAM odcien co Allegro.pl (ta sama rodzina
  // serwisow), ale slabszy - kanal bez API, w ktorym ORDLY tylko
  // pokazuje. Amber jest zajety przez Amazon, a dwa kanaly w jednym
  // kolorze przestalyby byc etykietami.
  allegro_lokalnie: { background: "rgba(255,133,99,.08)", text: "rgba(255,133,99,.72)" },
  olx: { background: "rgba(167,155,255,.14)", text: "#A79BFF" },
  amazon: { background: "rgba(245,192,101,.13)", text: "#F5C065" },
  ebay: { background: "rgba(95,217,204,.16)", text: "#5FD9CC" },
};

export const channelDay: Record<string, ChannelStyle> = {
  allegro: { background: "#FFE7DE", text: "#B4462E" },
  allegro_lokalnie: { background: "#FFF1EC", text: "#C4674F" },
  olx: { background: "#E9E7FE", text: "#4F44C4" },
  amazon: { background: "#FBF0D8", text: "#8A6218" },
  ebay: { background: "#D9F0EC", text: "#12706F" },
};

/** Skrocone nazwy kanalow - etykieta ma STALE 60 px (sekcja 7). */
export const CHANNEL_LABEL: Record<string, string> = {
  allegro: "Allegro",
  allegro_lokalnie: "Lokalnie",
  olx: "OLX",
  amazon: "Amazon",
  ebay: "eBay",
};

/**
 * Jezyk statusow - ten sam co na desktopie (sekcja 7):
 *
 *   hot  - wymaga dzialania
 *   go   - w toku, dzis
 *   mute - zamkniete
 *
 * "Wyslane" i "Odebrane" sa `mute`, nie `go`.
 */
export type Tone = "hot" | "go" | "mute";

export function toneStyle(tone: Tone, c: Palette): ChannelStyle {
  switch (tone) {
    case "hot":
      return { background: withAlpha(c.coral, 0.14), text: c.coral };
    case "go":
      return { background: c.accDim, text: c.acc };
    default:
      return { background: c.card2, text: c.tx3 };
  }
}

/** Etykieta zamowienia -> ton. Klucze = wynik `displayFulfillmentLabel`. */
export const ORDER_TONE: Record<string, Tone> = {
  Nowe: "hot",
  "W realizacji": "hot",
  "Do spakowania": "hot",
  Pakowanie: "hot",
  "Gotowe do wysyłki": "go",
  "Do odbioru": "mute",
  Wysłane: "mute",
  Odebrane: "mute",
  Anulowane: "mute",
  Wstrzymane: "hot",
};

/**
 * Przezroczystosc na kolorze zapisanym jako `#RRGGBB`. Potrzebna, bo tla
 * pastylek licza sie z akcentu atmosfery, a RN nie zna `color-mix()`.
 */
export function withAlpha(hex: string, alpha: number): string {
  if (!hex.startsWith("#") || hex.length !== 7) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

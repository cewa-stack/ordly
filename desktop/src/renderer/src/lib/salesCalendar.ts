/**
 * Kalendarz sprzedażowy - statyczne dane referencyjne (święta PL +
 * okresy sprzedażowe istotne dla Allegro/OLX), liczone lokalnie w
 * rendererze. Zero zapytań do backendu - to nie jest funkcja, ktora
 * cokolwiek "zapisuje" czy "synchronizuje", wiec staly zbior danych
 * jest tu wlasciwym rozwiazaniem, a nie przyciskiem-widmem.
 *
 * Kazde wydarzenie ma date szczytu sprzedazy oraz `leadDays` - ile dni
 * wczesniej warto wystawic oferte, zeby zdazyc z widocznoscia przed
 * szczytem popytu (sekcja "kiedy co wystawiac").
 */

export type EventCategory = "swieto" | "sprzedaz";

export interface SalesEventDef {
  id: string;
  title: string;
  category: EventCategory;
  /** Stala data (miesiac 1-12, dzien) albo przesuniecie od Wielkanocy w dniach. */
  fixedDate?: { month: number; day: number };
  easterOffset?: number;
  /** Specjalny przypadek: n-ty (1-based) dany dzien tygodnia danego miesiaca. -1 = ostatni. */
  nthWeekday?: { month: number; weekday: number; nth: number };
  /** Dni doliczone po rozwiazaniu bazowej daty (np. Cyber Monday = Black Friday + 3). */
  offsetDays?: number;
  /** Ile dni przed szczytem warto zaczac wystawiac oferty (tylko "sprzedaz"). */
  leadDays?: number;
  /** Ile dni po szczycie popyt jeszcze trwa. */
  tailDays?: number;
  description: string;
}

export interface SalesEventInstance extends SalesEventDef {
  peak: Date;
  prepStart: Date;
  tailEnd: Date;
}

/** Algorytm Meeusa/Jonesa/Butchera - niedziela wielkanocna dla danego roku. */
export function easterSunday(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function nthWeekdayOfMonth(year: number, month: number, weekday: number, nth: number): Date {
  if (nth > 0) {
    const first = new Date(year, month - 1, 1);
    const offset = (weekday - first.getDay() + 7) % 7;
    return addDays(first, offset + (nth - 1) * 7);
  }
  // nth < 0: liczymy od konca miesiaca
  const last = new Date(year, month, 0);
  const offset = (last.getDay() - weekday + 7) % 7;
  return addDays(last, -offset + (nth + 1) * 7);
}

export const SALES_EVENTS: SalesEventDef[] = [
  // ------------------------------------------------------------ stycze/luty
  {
    id: "nowy-rok",
    title: "Nowy Rok",
    category: "swieto",
    fixedDate: { month: 1, day: 1 },
    description: "Dzień wolny od pracy. Kurierzy i magazyny hurtowni stoją.",
  },
  {
    id: "trzech-kroli",
    title: "Święto Trzech Króli",
    category: "swieto",
    fixedDate: { month: 1, day: 6 },
    description: "Dzień wolny od pracy - opóźnienia w dostawach od hurtowni.",
  },
  {
    id: "walentynki",
    title: "Walentynki",
    category: "sprzedaz",
    fixedDate: { month: 2, day: 14 },
    leadDays: 21,
    tailDays: 0,
    description:
      "Biżuteria, kosmetyki, gadżety i zestawy prezentowe. Wystaw oferty najpóźniej 3 tygodnie wcześniej - ruch na Allegro rośnie już od początku lutego.",
  },
  {
    id: "dzien-kobiet",
    title: "Dzień Kobiet",
    category: "sprzedaz",
    fixedDate: { month: 3, day: 8 },
    leadDays: 18,
    tailDays: 0,
    description:
      "Kwiaty, kosmetyki, biżuteria, akcesoria. Szczyt zamówień przypada na 2-3 dni przed świętem - opisy i zdjęcia muszą być gotowe wcześniej.",
  },
  // ------------------------------------------------------------------ wiosna
  {
    id: "niedziela-palmowa",
    title: "Niedziela Palmowa",
    category: "swieto",
    easterOffset: -7,
    description: "Tydzień przed Wielkanocą - ostatni moment na dosyłkę ofert wielkanocnych.",
  },
  {
    id: "wielkanoc",
    title: "Wielkanoc",
    category: "sprzedaz",
    easterOffset: 0,
    leadDays: 28,
    tailDays: 1,
    description:
      "Dekoracje, akcesoria kuchenne, upominki, art. dziecięce. Zacznij wystawiać ok. 4 tygodnie przed - popyt rośnie skokowo w Wielkim Tygodniu, a kurierzy mają wtedy dni wolne (Poniedziałek Wielkanocny).",
  },
  {
    id: "poniedzialek-wielkanocny",
    title: "Poniedziałek Wielkanocny",
    category: "swieto",
    easterOffset: 1,
    description: "Dzień wolny od pracy - brak dostaw kurierskich.",
  },
  {
    id: "swieto-pracy",
    title: "Święto Pracy",
    category: "swieto",
    fixedDate: { month: 5, day: 1 },
    description: "Dzień wolny od pracy.",
  },
  {
    id: "konstytucja-3-maja",
    title: "Święto Konstytucji 3 Maja",
    category: "swieto",
    fixedDate: { month: 5, day: 3 },
    description:
      "Dzień wolny od pracy. Wraz z 1-2 maja tworzy długi weekend - kurierzy i hurtownie zwalniają na kilka dni, uwzględnij to w terminach realizacji.",
  },
  {
    id: "dzien-matki",
    title: "Dzień Matki",
    category: "sprzedaz",
    fixedDate: { month: 5, day: 26 },
    leadDays: 21,
    tailDays: 0,
    description:
      "Biżuteria, kwiaty, kosmetyki, upominki personalizowane. W Polsce data jest stała (26 maja) - wystaw oferty na początku miesiąca.",
  },
  {
    id: "zielone-swiatki",
    title: "Zielone Świątki",
    category: "swieto",
    easterOffset: 49,
    description: "Dzień wolny od pracy.",
  },
  {
    id: "boze-cialo",
    title: "Boże Ciało",
    category: "swieto",
    easterOffset: 60,
    description: "Dzień wolny od pracy - często kolejny długi weekend.",
  },
  // ------------------------------------------------------------------- lato
  {
    id: "dzien-dziecka",
    title: "Dzień Dziecka",
    category: "sprzedaz",
    fixedDate: { month: 6, day: 1 },
    leadDays: 21,
    tailDays: 0,
    description:
      "Zabawki, gry, art. szkolne, elektronika dziecięca. Popyt narasta przez cały maj - warto mieć oferty aktywne najpóźniej w połowie miesiąca.",
  },
  {
    id: "dzien-ojca",
    title: "Dzień Ojca",
    category: "sprzedaz",
    fixedDate: { month: 6, day: 23 },
    leadDays: 14,
    tailDays: 0,
    description: "Narzędzia, akcesoria motoryzacyjne, gadżety. Mniejszy ruch niż Dzień Matki, ale warto wystawić 2 tygodnie wcześniej.",
  },
  {
    id: "wakacje-powrot-do-szkoly-start",
    title: "Start sezonu \"powrót do szkoły\"",
    category: "sprzedaz",
    fixedDate: { month: 7, day: 15 },
    leadDays: 0,
    tailDays: 45,
    description:
      "Plecaki, przybory, elektronika dla uczniów i studentów. Popyt narasta od połowy lipca i utrzymuje się do września - to najdłuższy okres przygotowawczy w roku, zacznij wystawiać z wyprzedzeniem.",
  },
  {
    id: "wniebowziecie",
    title: "Wniebowzięcie NMP / Święto Wojska Polskiego",
    category: "swieto",
    fixedDate: { month: 8, day: 15 },
    description: "Dzień wolny od pracy - środek sezonu urlopowego, wolniejsza logistyka.",
  },
  // ---------------------------------------------------------------- jesien
  {
    id: "wszystkich-swietych",
    title: "Wszystkich Świętych",
    category: "swieto",
    fixedDate: { month: 11, day: 1 },
    description:
      "Dzień wolny od pracy. Znicze, kwiaty i wiązanki mają lokalny szczyt popytu w ostatnim tygodniu października.",
  },
  {
    id: "niepodleglosci",
    title: "Święto Niepodległości",
    category: "swieto",
    fixedDate: { month: 11, day: 11 },
    description: "Dzień wolny od pracy.",
  },
  {
    id: "black-friday",
    title: "Black Friday",
    category: "sprzedaz",
    nthWeekday: { month: 11, weekday: 5, nth: -1 },
    leadDays: 21,
    tailDays: 3,
    description:
      "Największy szczyt ruchu w roku na Allegro. Ceny i promocje trzeba mieć ustawione min. 3 tygodnie wcześniej - platformy porównują \"cenę z ostatnich 30 dni\", więc podbicie ceny tuż przed BF wygląda podejrzanie i bywa oflagowane.",
  },
  {
    id: "cyber-monday",
    title: "Cyber Monday",
    category: "sprzedaz",
    nthWeekday: { month: 11, weekday: 5, nth: -1 },
    offsetDays: 3,
    leadDays: 0,
    tailDays: 0,
    description:
      "Poniedziałek po Black Friday - przedłużenie promocji, głównie elektronika i akcesoria komputerowe.",
  },
  // ----------------------------------------------------------------- zima
  {
    id: "mikolajki",
    title: "Mikołajki",
    category: "sprzedaz",
    fixedDate: { month: 12, day: 6 },
    leadDays: 21,
    tailDays: 0,
    description: "Drobne prezenty, słodycze, zabawki. Wystaw oferty najpóźniej na początku grudnia.",
  },
  {
    id: "boze-narodzenie",
    title: "Boże Narodzenie",
    category: "sprzedaz",
    fixedDate: { month: 12, day: 24 },
    leadDays: 35,
    tailDays: 2,
    description:
      "Największy sezon prezentowy w roku. Zacznij wystawiać w listopadzie - pamiętaj o ostatnich gwarantowanych terminach dostaw kurierskich przed Wigilią (zwykle 20-21 grudnia) i o tym, że 25-26 grudnia to dni wolne.",
  },
  {
    id: "sylwester",
    title: "Sylwester",
    category: "sprzedaz",
    fixedDate: { month: 12, day: 31 },
    leadDays: 14,
    tailDays: 0,
    description: "Alkohol, fajerwerki (zgodnie z przepisami), dekoracje, akcesoria na imprezy.",
  },
];

function resolveInstanceDate(def: SalesEventDef, year: number): Date {
  let base: Date;
  if (def.fixedDate) {
    base = new Date(year, def.fixedDate.month - 1, def.fixedDate.day);
  } else if (def.nthWeekday) {
    base = nthWeekdayOfMonth(year, def.nthWeekday.month, def.nthWeekday.weekday, def.nthWeekday.nth);
  } else if (def.easterOffset !== undefined) {
    base = addDays(easterSunday(year), def.easterOffset);
  } else {
    throw new Error(`Wydarzenie ${def.id} nie ma zdefiniowanej daty`);
  }
  return def.offsetDays ? addDays(base, def.offsetDays) : base;
}

/** Instancje wszystkich wydarzeń dla podanych lat (zwykle biezacy + kolejny). */
export function buildSalesCalendar(years: number[]): SalesEventInstance[] {
  const instances: SalesEventInstance[] = [];
  for (const year of years) {
    for (const def of SALES_EVENTS) {
      const peak = resolveInstanceDate(def, year);
      const prepStart = addDays(peak, -(def.leadDays ?? 0));
      const tailEnd = addDays(peak, def.tailDays ?? 0);
      instances.push({ ...def, peak, prepStart, tailEnd });
    }
  }
  return instances.sort((a, b) => a.peak.getTime() - b.peak.getTime());
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

export type EventStatus = "trwa" | "nadchodzi" | "minelo";

export function statusOf(instance: SalesEventInstance, today: Date): EventStatus {
  const t = startOfDay(today).getTime();
  if (t >= startOfDay(instance.prepStart).getTime() && t <= startOfDay(instance.tailEnd).getTime()) {
    return "trwa";
  }
  if (t < startOfDay(instance.prepStart).getTime()) return "nadchodzi";
  return "minelo";
}

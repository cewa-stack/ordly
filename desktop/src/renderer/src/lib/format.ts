/**
 * Formaty liczb i dat wg sekcji 7.2 specyfikacji. Jedno miejsce, zeby
 * ekrany nie sklejaly kwot recznie i zeby wszystko wyrownywalo sie w
 * pionie (cyfry tabelaryczne + ten sam separator tysiecy).
 *
 * Waluta: `249,90 zł` - przecinek dziesietny, spacja przed "zł",
 * spacja jako separator tysiecy (`2 340 zł`).
 */

const CURRENCY_FORMAT = new Intl.NumberFormat("pl-PL", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const CURRENCY_FORMAT_ROUND = new Intl.NumberFormat("pl-PL", {
  maximumFractionDigits: 0,
});

const TIME_FORMAT = new Intl.DateTimeFormat("pl-PL", {
  hour: "2-digit",
  minute: "2-digit",
});

const DATE_FORMAT = new Intl.DateTimeFormat("pl-PL", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

const LONG_DATE_FORMAT = new Intl.DateTimeFormat("pl-PL", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

/**
 * Kwota z API jako liczba - odporna na to, ze starszy backend na Pi
 * moze jeszcze oddawac kwoty jako STRINGI ("19.99").
 *
 * Pydantic v2 domyslnie serializuje `Decimal` do stringa; backend
 * naprawiono aliasem `Money` (schemas.py), ale desktop bywa
 * nowszy niz uslugi na Pi. Bez tej konwersji `0 + "19.99" + "19.99"`
 * dawalo sklejony tekst "019.9919.99", a formatCurrency -> `NaN zl`.
 *
 * `NaN`/`null`/`undefined` swiadomie schodza do 0: w podsumowaniu
 * lepiej pokazac `0,00 zl` niz `NaN zl`.
 */
export function toAmount(value: number | string | null | undefined): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value !== "string") return 0;
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

/** `249,90 zł`. Wartosci calkowite bez groszy: `2 340 zł`. */
export function formatCurrency(
  amount: number | string | null | undefined,
  { round = false } = {}
): string {
  const formatter = round ? CURRENCY_FORMAT_ROUND : CURRENCY_FORMAT;
  return `${formatter.format(toAmount(amount))} zł`;
}

/** `08:12` */
export function formatTime(iso: string): string {
  return TIME_FORMAT.format(new Date(iso));
}

/** `04.08, 08:12` */
export function formatDateTime(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
}

/** `wtorek, 4 sierpnia` - okruszek ekranu Start. */
export function formatLongDate(date: Date): string {
  return LONG_DATE_FORMAT.format(date);
}

/**
 * Wiek zgloszenia: "10 min", "1 godz.", "wczoraj", "2 dni".
 * Skala celowo gruba - dokladna minuta sprzed tygodnia nikomu nie pomaga.
 */
export function formatAge(iso: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return "przed chwilą";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? "1 godz." : `${hours} godz.`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "wczoraj";
  return `${days} dni`;
}

/** `8 / 25` - stan magazynowy wobec progu/maksimum. */
export function formatStock(value: number, max: number): string {
  return `${value} / ${max}`;
}

/**
 * Polska odmiana rzeczownika przez liczbe:
 * `formatPlural(2, ["receptura", "receptury", "receptur"])` -> `2 receptury`.
 *
 * Trzy formy, nie dwie: polski ma osobna forme dla 2-4 i osobna dla 5+,
 * a nastolatki (12-14) ida jak 5+. "5 receptury" albo "2 receptur"
 * w potwierdzeniu usuniecia widac natychmiast.
 */
export function formatPlural(
  count: number,
  forms: [one: string, few: string, many: string]
): string {
  const absolute = Math.abs(count);
  const lastDigit = absolute % 10;
  const lastTwo = absolute % 100;
  if (absolute === 1) return `${count} ${forms[0]}`;
  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14)) {
    return `${count} ${forms[1]}`;
  }
  return `${count} ${forms[2]}`;
}

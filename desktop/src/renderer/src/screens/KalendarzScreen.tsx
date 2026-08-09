/**
 * Kalendarz sprzedazowy - siatka miesiaca + panel szczegolow (ten sam
 * uklad `1.5fr / 1fr` co Statystyki). Dane sa statyczne i liczone
 * lokalnie (`lib/salesCalendar.ts`) - swieta PL i okresy sprzedazowe
 * nie zmieniaja sie z dnia na dzien, wiec nie ma tu zadnego zapytania
 * do backendu.
 */
import * as React from "react";
import { Chip } from "../components/ui";
import {
  buildSalesCalendar,
  isSameDay,
  startOfDay,
  statusOf,
  type EventCategory,
  type SalesEventInstance,
} from "../lib/salesCalendar";

const MONTH_LABELS = [
  "Styczeń",
  "Luty",
  "Marzec",
  "Kwiecień",
  "Maj",
  "Czerwiec",
  "Lipiec",
  "Sierpień",
  "Wrzesień",
  "Październik",
  "Listopad",
  "Grudzień",
];

const DAY_LABELS = ["pon", "wt", "śr", "czw", "pt", "sob", "ndz"];

const CATEGORY_LABEL: Record<EventCategory, string> = {
  swieto: "Święto",
  sprzedaz: "Okres sprzedażowy",
};

/** Kolor + ksztalt sa razem nosnikiem informacji (nie samo `currentColor`),
 * zeby swieto (dzien wolny, ostrzegawczy bursztyn, romb) i okres sprzedazowy
 * (szansa, morski, kolko) byly odrozniane nawet przy kilku kropkach obok siebie. */
const CATEGORY_DOT: Record<EventCategory, string> = {
  swieto: "rounded-[2px] rotate-45 bg-amber",
  sprzedaz: "rounded-full bg-teal-bright",
};

const CATEGORY_BADGE: Record<EventCategory, string> = {
  swieto: "bg-[rgba(245,192,101,.14)] text-amber",
  sprzedaz: "bg-teal-dim text-teal-bright",
};

const CATEGORY_CELL_TINT: Record<EventCategory, string> = {
  swieto: "bg-[rgba(245,192,101,.08)]",
  sprzedaz: "bg-teal-dim",
};

/** Gdy dzien ma obie kategorie, sprzedaz "wygrywa" ton tla - to ona niesie akcje do podjecia. */
function dominantCategory(dayEvents: SalesEventInstance[]): EventCategory | null {
  if (dayEvents.some((event) => event.category === "sprzedaz")) return "sprzedaz";
  if (dayEvents.some((event) => event.category === "swieto")) return "swieto";
  return null;
}

const STATUS_LABEL: Record<string, string> = {
  trwa: "Trwa teraz",
  nadchodzi: "Nadchodzi",
  minelo: "Minęło",
};

function monthGridDays(year: number, month: number): Date[] {
  const first = new Date(year, month, 1);
  const startOffset = (first.getDay() + 6) % 7; // 0 = poniedzialek
  const gridStart = new Date(year, month, 1 - startOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
}

function formatDayMonth(date: Date): string {
  return `${date.getDate()} ${MONTH_LABELS[date.getMonth()].toLowerCase()}`;
}

function formatRange(instance: SalesEventInstance): string {
  if (isSameDay(instance.prepStart, instance.peak) && isSameDay(instance.tailEnd, instance.peak)) {
    return formatDayMonth(instance.peak);
  }
  const start = formatDayMonth(instance.prepStart);
  const end = formatDayMonth(instance.tailEnd);
  return `${start} → ${end}`;
}

export function KalendarzScreen() {
  const today = React.useMemo(() => startOfDay(new Date()), []);
  const [cursor, setCursor] = React.useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [category, setCategory] = React.useState<EventCategory | "all">("all");
  const [selectedDay, setSelectedDay] = React.useState<Date>(today);

  const events = React.useMemo(
    () => buildSalesCalendar([cursor.getFullYear(), cursor.getFullYear() + 1, cursor.getFullYear() - 1]),
    [cursor]
  );

  const visibleEvents = React.useMemo(
    () => (category === "all" ? events : events.filter((event) => event.category === category)),
    [events, category]
  );

  const eventsByDay = React.useMemo(() => {
    const map = new Map<string, SalesEventInstance[]>();
    for (const event of visibleEvents) {
      const key = `${event.peak.getFullYear()}-${event.peak.getMonth()}-${event.peak.getDate()}`;
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    return map;
  }, [visibleEvents]);

  const days = monthGridDays(cursor.getFullYear(), cursor.getMonth());

  const selectedDayEvents = visibleEvents.filter((event) => isSameDay(event.peak, selectedDay));

  const upcoming = React.useMemo(() => {
    return visibleEvents
      .filter((event) => statusOf(event, today) !== "minelo")
      .sort((a, b) => a.prepStart.getTime() - b.prepStart.getTime())
      .slice(0, 8);
  }, [visibleEvents, today]);

  function goToMonth(delta: number) {
    setCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto p-[22px]">
      <div className="flex items-center gap-2.5">
        <Chip active={category === "all"} onClick={() => setCategory("all")}>
          Wszystko
        </Chip>
        <Chip active={category === "sprzedaz"} onClick={() => setCategory("sprzedaz")}>
          Okresy sprzedażowe
        </Chip>
        <Chip active={category === "swieto"} onClick={() => setCategory("swieto")}>
          Święta
        </Chip>
        <button
          onClick={() => {
            setCursor(new Date(today.getFullYear(), today.getMonth(), 1));
            setSelectedDay(today);
          }}
          className="ml-auto rounded-[7px] border border-line px-2.5 py-[5px] text-[11.5px] text-slate transition-colors hover:border-line-strong hover:text-white"
        >
          Dziś
        </button>
      </div>

      <div className="grid grid-cols-[1.5fr_minmax(0,1fr)] gap-3.5 max-[940px]:grid-cols-1">
        <div className="flex flex-col gap-3.5 rounded-md border border-line bg-panel-2 p-[18px]">
          <div className="flex items-center justify-between">
            <h4 className="o-display text-[15px] font-semibold">
              {MONTH_LABELS[cursor.getMonth()]} {cursor.getFullYear()}
            </h4>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => goToMonth(-1)}
                aria-label="Poprzedni miesiąc"
                className="flex h-7 w-7 items-center justify-center rounded-md text-slate-dim transition-colors hover:bg-panel-3 hover:text-white"
              >
                ‹
              </button>
              <button
                onClick={() => goToMonth(1)}
                aria-label="Następny miesiąc"
                className="flex h-7 w-7 items-center justify-center rounded-md text-slate-dim transition-colors hover:bg-panel-3 hover:text-white"
              >
                ›
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-1">
            {DAY_LABELS.map((label) => (
              <div key={label} className="o-mono px-1 pb-1 text-center text-[9.5px] uppercase tracking-[.08em] text-slate-dim">
                {label}
              </div>
            ))}
            {days.map((date) => {
              const inMonth = date.getMonth() === cursor.getMonth();
              const isToday = isSameDay(date, today);
              const isSelected = isSameDay(date, selectedDay);
              const key = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
              const dayEvents = eventsByDay.get(key) ?? [];
              const dominant = dominantCategory(dayEvents);

              return (
                <button
                  key={date.toISOString()}
                  onClick={() => setSelectedDay(date)}
                  className={`flex h-[64px] flex-col items-start gap-1.5 rounded-[7px] border px-1.5 py-1 text-left transition-colors duration-150 ease-ordly ${
                    isSelected
                      ? "border-teal-bright bg-teal-dim"
                      : `border-transparent hover:border-line hover:bg-panel-3 ${dominant ? CATEGORY_CELL_TINT[dominant] : ""}`
                  } ${inMonth ? "" : "opacity-35"}`}
                >
                  <span
                    className={`o-mono text-[11px] ${
                      isToday ? "flex h-[18px] w-[18px] items-center justify-center rounded-full bg-coral text-white" : "text-slate"
                    }`}
                  >
                    {date.getDate()}
                  </span>
                  {dayEvents.length > 0 && (
                    <span className="w-full truncate text-[9px] leading-tight text-slate">
                      {dayEvents[0].title}
                    </span>
                  )}
                  <span className="mt-auto flex flex-wrap gap-[4px]">
                    {dayEvents.slice(0, 4).map((event) => (
                      <i key={event.id} className={`h-[6px] w-[6px] shrink-0 ${CATEGORY_DOT[event.category]}`} />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4 border-t border-line pt-3 text-[10.5px] text-slate-dim">
            <span className="flex items-center gap-2">
              <i className="h-[7px] w-[7px] rounded-full bg-teal-bright" /> Okres sprzedażowy
            </span>
            <span className="flex items-center gap-2">
              <i className="h-[7px] w-[7px] rotate-45 rounded-[2px] bg-amber" /> Święto (dzień wolny)
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-3.5">
          <div className="flex flex-col gap-2.5 rounded-md border border-line bg-panel-2 p-[18px]">
            <h4 className="text-[13px] font-semibold">{formatDayMonth(selectedDay)}</h4>
            {selectedDayEvents.length === 0 ? (
              <p className="text-[12px] text-slate-dim">Brak wydarzeń tego dnia.</p>
            ) : (
              selectedDayEvents.map((event) => <EventCard key={event.id} event={event} today={today} />)
            )}
          </div>

          <div className="flex flex-col gap-2.5 rounded-md border border-line bg-panel-2 p-[18px]">
            <h4 className="text-[13px] font-semibold">Najbliższe</h4>
            {upcoming.length === 0 ? (
              <p className="text-[12px] text-slate-dim">Brak nadchodzących wydarzeń w wybranej kategorii.</p>
            ) : (
              upcoming.map((event) => (
                <button
                  key={`${event.id}-${event.peak.toISOString()}`}
                  onClick={() => {
                    setSelectedDay(event.peak);
                    setCursor(new Date(event.peak.getFullYear(), event.peak.getMonth(), 1));
                  }}
                  className="flex items-center gap-3 border-b border-line py-2 text-left text-[12.5px] last:border-b-0 hover:text-white"
                >
                  <i className={`h-[7px] w-[7px] shrink-0 ${CATEGORY_DOT[event.category]}`} />
                  <span className="min-w-0 flex-1 truncate text-white">{event.title}</span>
                  <span
                    className={`o-mono shrink-0 text-[10px] ${
                      statusOf(event, today) === "trwa" ? "text-coral" : "text-slate-dim"
                    }`}
                  >
                    {STATUS_LABEL[statusOf(event, today)]}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EventCard({ event, today }: { event: SalesEventInstance; today: Date }) {
  const status = statusOf(event, today);
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-line bg-panel-3 p-3">
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-semibold text-white">{event.title}</span>
        <span
          className={`o-mono ml-auto shrink-0 rounded-[20px] px-2 py-[3px] text-[9.5px] font-medium ${
            status === "trwa" ? "bg-coral-dim text-coral" : "bg-panel text-slate-dim"
          }`}
        >
          {STATUS_LABEL[status]}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`o-mono shrink-0 rounded-[20px] px-2 py-[3px] text-[9.5px] font-medium ${CATEGORY_BADGE[event.category]}`}
        >
          {CATEGORY_LABEL[event.category]}
        </span>
        <span className="o-mono text-[10.5px] text-slate-dim">{formatRange(event)}</span>
      </div>
      <p className="text-[12px] leading-[1.55] text-slate">{event.description}</p>
    </div>
  );
}

"""
Kalendarz sprzedażowy - święta w Polsce i okresy wzmożonego popytu.

Statyczne dane referencyjne: daty świąt i sezonów sprzedażowych nie
pochodzą z żadnego API, tylko z kalendarza, więc liczymy je lokalnie.

BLIŹNIAK: `desktop/src/renderer/src/lib/salesCalendar.ts` trzyma te same
wydarzenia dla ekranu Kalendarz (renderer nie odpytuje o nie backendu).
Ta kopia istnieje, bo asystent Ordlaka odpowiada po stronie Pi i musi
znać te daty bez pytania aplikacji. **Każde dodane/zmienione wydarzenie
trzeba nanieść w OBU plikach** - inaczej Kalendarz i asystent zaczną
mówić co innego o tym samym dniu.

Uwaga na konwencję dnia tygodnia: TypeScript używa `Date.getDay()`
(0 = niedziela), tutaj obowiązuje `date.weekday()` (0 = poniedziałek).
Black Friday to więc `weekday=5` w TS i `weekday=4` w Pythonie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

EventCategory = Literal["swieto", "sprzedaz"]
EventStatus = Literal["trwa", "nadchodzi", "minelo"]


@dataclass(frozen=True, slots=True)
class SalesEventDef:
    """
    Definicja cyklicznego wydarzenia.

    Data bierze się dokładnie z jednego z trzech pól: `fixed_date`
    (stały dzień roku), `nth_weekday` (n-ty dany dzień tygodnia miesiąca,
    `nth < 0` liczy od końca) albo `easter_offset` (dni od Wielkanocy).
    """

    id: str
    title: str
    category: EventCategory
    description: str
    fixed_date: tuple[int, int] | None = None
    nth_weekday: tuple[int, int, int] | None = None
    easter_offset: int | None = None
    #: Dni doliczone po rozwiązaniu daty bazowej (Cyber Monday = Black Friday + 3).
    offset_days: int = 0
    #: Ile dni przed szczytem warto mieć już wystawione oferty.
    lead_days: int = 0
    #: Ile dni po szczycie popyt jeszcze trwa.
    tail_days: int = 0


@dataclass(frozen=True, slots=True)
class SalesEventInstance:
    """Wydarzenie osadzone w konkretnym roku."""

    definition: SalesEventDef
    peak: date
    prep_start: date
    tail_end: date

    def status(self, today: date) -> EventStatus:
        """Czy okno wydarzenia trwa, dopiero nadchodzi, czy już minęło."""
        if self.prep_start <= today <= self.tail_end:
            return "trwa"
        return "nadchodzi" if today < self.prep_start else "minelo"


def easter_sunday(year: int) -> date:
    """Niedziela wielkanocna dla danego roku (algorytm Meeusa/Jonesa/Butchera)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    """N-ty `weekday` (0 = poniedziałek) w miesiącu; `nth = -1` to ostatni."""
    if nth > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + (nth - 1) * 7)

    next_month = date(year + month // 12, month % 12 + 1, 1)
    last = next_month - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset) + timedelta(days=(nth + 1) * 7)


SALES_EVENTS: tuple[SalesEventDef, ...] = (
    SalesEventDef(
        id="nowy-rok",
        title="Nowy Rok",
        category="swieto",
        fixed_date=(1, 1),
        description="Dzień wolny od pracy. Kurierzy i magazyny hurtowni stoją.",
    ),
    SalesEventDef(
        id="trzech-kroli",
        title="Święto Trzech Króli",
        category="swieto",
        fixed_date=(1, 6),
        description="Dzień wolny od pracy - opóźnienia w dostawach od hurtowni.",
    ),
    SalesEventDef(
        id="walentynki",
        title="Walentynki",
        category="sprzedaz",
        fixed_date=(2, 14),
        lead_days=21,
        description=(
            "Biżuteria, kosmetyki, gadżety i zestawy prezentowe. Wystaw oferty "
            "najpóźniej 3 tygodnie wcześniej - ruch na Allegro rośnie już od "
            "początku lutego."
        ),
    ),
    SalesEventDef(
        id="dzien-kobiet",
        title="Dzień Kobiet",
        category="sprzedaz",
        fixed_date=(3, 8),
        lead_days=18,
        description=(
            "Kwiaty, kosmetyki, biżuteria, akcesoria. Szczyt zamówień przypada "
            "na 2-3 dni przed świętem."
        ),
    ),
    SalesEventDef(
        id="niedziela-palmowa",
        title="Niedziela Palmowa",
        category="swieto",
        easter_offset=-7,
        description="Tydzień przed Wielkanocą - ostatni moment na oferty wielkanocne.",
    ),
    SalesEventDef(
        id="wielkanoc",
        title="Wielkanoc",
        category="sprzedaz",
        easter_offset=0,
        lead_days=28,
        tail_days=1,
        description=(
            "Dekoracje, akcesoria kuchenne, upominki, art. dziecięce. Zacznij "
            "wystawiać ok. 4 tygodnie przed - popyt rośnie skokowo w Wielkim "
            "Tygodniu, a Poniedziałek Wielkanocny to dzień wolny dla kurierów."
        ),
    ),
    SalesEventDef(
        id="poniedzialek-wielkanocny",
        title="Poniedziałek Wielkanocny",
        category="swieto",
        easter_offset=1,
        description="Dzień wolny od pracy - brak dostaw kurierskich.",
    ),
    SalesEventDef(
        id="swieto-pracy",
        title="Święto Pracy",
        category="swieto",
        fixed_date=(5, 1),
        description="Dzień wolny od pracy.",
    ),
    SalesEventDef(
        id="konstytucja-3-maja",
        title="Święto Konstytucji 3 Maja",
        category="swieto",
        fixed_date=(5, 3),
        description=(
            "Dzień wolny od pracy. Razem z 1-2 maja tworzy długi weekend - "
            "kurierzy i hurtownie zwalniają na kilka dni."
        ),
    ),
    SalesEventDef(
        id="dzien-matki",
        title="Dzień Matki",
        category="sprzedaz",
        fixed_date=(5, 26),
        lead_days=21,
        description=(
            "Biżuteria, kwiaty, kosmetyki, upominki personalizowane. W Polsce "
            "data jest stała (26 maja) - wystaw oferty na początku miesiąca."
        ),
    ),
    SalesEventDef(
        id="zielone-swiatki",
        title="Zielone Świątki",
        category="swieto",
        easter_offset=49,
        description="Dzień wolny od pracy.",
    ),
    SalesEventDef(
        id="boze-cialo",
        title="Boże Ciało",
        category="swieto",
        easter_offset=60,
        description="Dzień wolny od pracy - często kolejny długi weekend.",
    ),
    SalesEventDef(
        id="dzien-dziecka",
        title="Dzień Dziecka",
        category="sprzedaz",
        fixed_date=(6, 1),
        lead_days=21,
        description=(
            "Zabawki, gry, art. szkolne, elektronika dziecięca. Popyt narasta "
            "przez cały maj."
        ),
    ),
    SalesEventDef(
        id="dzien-ojca",
        title="Dzień Ojca",
        category="sprzedaz",
        fixed_date=(6, 23),
        lead_days=14,
        description=(
            "Narzędzia, akcesoria motoryzacyjne, gadżety. Mniejszy ruch niż "
            "Dzień Matki, ale warto wystawić 2 tygodnie wcześniej."
        ),
    ),
    SalesEventDef(
        id="wakacje-powrot-do-szkoly-start",
        title='Start sezonu "powrót do szkoły"',
        category="sprzedaz",
        fixed_date=(7, 15),
        tail_days=45,
        description=(
            "Plecaki, przybory, elektronika dla uczniów i studentów. Popyt "
            "narasta od połowy lipca i utrzymuje się do września - to najdłuższy "
            "okres przygotowawczy w roku."
        ),
    ),
    SalesEventDef(
        id="wniebowziecie",
        title="Wniebowzięcie NMP / Święto Wojska Polskiego",
        category="swieto",
        fixed_date=(8, 15),
        description="Dzień wolny od pracy - środek sezonu urlopowego, wolniejsza logistyka.",
    ),
    SalesEventDef(
        id="wszystkich-swietych",
        title="Wszystkich Świętych",
        category="swieto",
        fixed_date=(11, 1),
        description=(
            "Dzień wolny od pracy. Znicze, kwiaty i wiązanki mają lokalny szczyt "
            "popytu w ostatnim tygodniu października."
        ),
    ),
    SalesEventDef(
        id="niepodleglosci",
        title="Święto Niepodległości",
        category="swieto",
        fixed_date=(11, 11),
        description="Dzień wolny od pracy.",
    ),
    SalesEventDef(
        id="black-friday",
        title="Black Friday",
        category="sprzedaz",
        nth_weekday=(11, 4, -1),
        lead_days=21,
        tail_days=3,
        description=(
            "Największy szczyt ruchu w roku na Allegro. Ceny i promocje trzeba "
            'mieć ustawione min. 3 tygodnie wcześniej - platformy porównują "cenę '
            'z ostatnich 30 dni", więc podbicie ceny tuż przed BF bywa oflagowane.'
        ),
    ),
    SalesEventDef(
        id="cyber-monday",
        title="Cyber Monday",
        category="sprzedaz",
        nth_weekday=(11, 4, -1),
        offset_days=3,
        description=(
            "Poniedziałek po Black Friday - przedłużenie promocji, głównie "
            "elektronika i akcesoria komputerowe."
        ),
    ),
    SalesEventDef(
        id="mikolajki",
        title="Mikołajki",
        category="sprzedaz",
        fixed_date=(12, 6),
        lead_days=21,
        description="Drobne prezenty, słodycze, zabawki. Wystaw oferty na początku grudnia.",
    ),
    SalesEventDef(
        id="boze-narodzenie",
        title="Boże Narodzenie",
        category="sprzedaz",
        fixed_date=(12, 24),
        lead_days=35,
        tail_days=2,
        description=(
            "Największy sezon prezentowy w roku. Zacznij wystawiać w listopadzie - "
            "pamiętaj o ostatnich gwarantowanych terminach dostaw przed Wigilią "
            "(zwykle 20-21 grudnia) i o tym, że 25-26 grudnia to dni wolne."
        ),
    ),
    SalesEventDef(
        id="sylwester",
        title="Sylwester",
        category="sprzedaz",
        fixed_date=(12, 31),
        lead_days=14,
        description="Fajerwerki (zgodnie z przepisami), dekoracje, akcesoria na imprezy.",
    ),
)


def _resolve(definition: SalesEventDef, year: int) -> date:
    """Zwraca datę szczytu wydarzenia w podanym roku."""
    if definition.fixed_date is not None:
        month, day = definition.fixed_date
        base = date(year, month, day)
    elif definition.nth_weekday is not None:
        base = _nth_weekday_of_month(year, *definition.nth_weekday)
    elif definition.easter_offset is not None:
        base = easter_sunday(year) + timedelta(days=definition.easter_offset)
    else:  # pragma: no cover - chroni przed definicją bez daty
        raise ValueError(f"Wydarzenie {definition.id} nie ma zdefiniowanej daty")
    return base + timedelta(days=definition.offset_days)


def build_calendar(years: list[int]) -> list[SalesEventInstance]:
    """Instancje wszystkich wydarzeń dla podanych lat, posortowane po dacie."""
    instances: list[SalesEventInstance] = []
    for year in years:
        for definition in SALES_EVENTS:
            peak = _resolve(definition, year)
            instances.append(
                SalesEventInstance(
                    definition=definition,
                    peak=peak,
                    prep_start=peak - timedelta(days=definition.lead_days),
                    tail_end=peak + timedelta(days=definition.tail_days),
                )
            )
    return sorted(instances, key=lambda instance: instance.peak)


def upcoming_events(today: date, days_ahead: int = 60) -> list[SalesEventInstance]:
    """
    Wydarzenia istotne "teraz": takie, których szczyt wypada w najbliższych
    `days_ahead` dniach, oraz te już trwające (okno przygotowań się zaczęło,
    a ogon popytu jeszcze się nie skończył).

    Kalendarz obejmuje rok bieżący i następny, żeby w grudniu było widać
    styczniowe i lutowe okresy sprzedażowe.
    """
    horizon = today + timedelta(days=days_ahead)
    return [
        instance
        for instance in build_calendar([today.year, today.year + 1])
        if instance.tail_end >= today and instance.peak <= horizon
    ]

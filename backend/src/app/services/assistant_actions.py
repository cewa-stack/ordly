"""
Działania zapisujące Ordlaka - katalog, walidacja i wykonanie.

ZASADA NACZELNA: **model PROPONUJE, człowiek ZATWIERDZA, serwer WYKONUJE.**

Asystent nie ma narzędzia, które cokolwiek zapisuje. Ma wyłącznie
narzędzie `zaproponuj_dzialanie`, które odkłada propozycję na bok i wraca
do modelu. Propozycja jedzie do aplikacji razem z odpowiedzią, aplikacja
pokazuje ją jako przycisk, a zapis dzieje się dopiero wtedy, gdy
użytkownik ten przycisk naciśnie - osobnym zapytaniem
`POST /api/v1/ordlak/apply`.

Dlaczego tak, a nie "model woła narzędzie zapisujące":

- dwa z trzech działań widzi KTOŚ POZA sprzedawcą. "Oznacz jako wysłane"
  zmienia to, co kupujący ogląda na Allegro, a odpowiedź w dyskusji jest
  wiadomością do człowieka. Takiej rzeczy nie cofa się przyciskiem
  "wstecz", więc nie może jej uruchomić zdanie źle zrozumiane przez model;
- model bywa pewny siebie także wtedy, gdy się myli - a tu myłby się na
  cudzym zamówieniu.

**Uprawnienia:** `apply` nie daje aplikacji NICZEGO, czego nie mogłaby
zrobić bez Ordlaka. Każde z trzech działań ma swój własny endpoint
(`/orders/{id}/fulfillment`, `/stock/.../quantity`, `/issues/{id}/reply`)
i ten sam token dostępowy. `apply` to skrót, nie nowa władza.

Parametry przychodzące z aplikacji są walidowane PONOWNIE (te same
funkcje, co przy propozycji) - klient nie jest źródłem prawdy o tym, co
wolno wykonać.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger

from app.services.issues_service import IssuesService
from app.services.offer_catalog_service import OfferCatalogService
from app.services.sync_orders_service import SyncOrdersService

#: Rodzaje działań, jakie Ordlak może zaproponować. Lista jest ZAMKNIĘTA -
#: cokolwiek spoza niej jest odrzucane i przy propozycji, i przy zapisie.
ActionKind = Literal["ustaw_stan_oferty", "oznacz_zamowienie", "odpowiedz_w_dyskusji"]

ACTION_KINDS: frozenset[str] = frozenset(
    {"ustaw_stan_oferty", "oznacz_zamowienie", "odpowiedz_w_dyskusji"}
)

#: Ile propozycji może wyjść z jednej odpowiedzi. Trzy przyciski pod
#: jednym akapitem to już nie pomoc, tylko formularz.
MAX_ACTIONS_PER_ANSWER = 3

#: Górna granica ręcznie wpisywanego stanu. Nie ma magazynu, w którym
#: "1000000 sztuk" jest prawdą, a jest sporo literówek, które tak wyglądają.
MAX_QUANTITY = 100_000

#: Odpowiedź w dyskusji to wiadomość, nie elaborat. Allegro i tak tnie
#: dłuższe, a limit chroni przed modelem, który wkleił połowę rozmowy.
MAX_REPLY_CHARS = 2_000

#: Statusy realizacji, jakie wolno ustawić z poziomu asystenta - te same
#: dwa, które ma pod przyciskiem panel szczegółu zamówienia. Cofania
#: statusu ani anulowania asystent nie proponuje.
_STATUS_BY_WORD: dict[str, str] = {
    "spakowane": "READY_FOR_SHIPMENT",
    "wyslane": "SENT",
}

#: Ten sam status po polsku, z ogonkami. Enum narzędzia jest w ASCII (jak
#: cały tekst lecący do modelu), ale etykieta na przycisku i zdanie
#: potwierdzenia czyta człowiek - "Oznacz jako wyslane" byłoby literówką
#: widoczną w interfejsie.
_STATUS_LABEL: dict[str, str] = {
    "spakowane": "spakowane",
    "wyslane": "wysłane",
}


class AssistantActionError(Exception):
    """Propozycja albo żądanie zapisu, którego nie da się wykonać."""


@dataclass(frozen=True, slots=True)
class ProposedAction:
    """
    Jedno działanie zaproponowane przez Ordlaka, czekające na zatwierdzenie.

    `outward` mówi, czy skutek zobaczy ktoś poza sprzedawcą - aplikacja
    używa tego, żeby przy takich działaniach zapytać wprost, a przy
    lokalnych (stan na półce) poprzestać na jednym kliknięciu.
    """

    kind: ActionKind
    #: Napis na przycisku, np. "Oznacz jako wysłane".
    label: str
    #: Jedno zdanie: co dokładnie się stanie po zatwierdzeniu.
    summary: str
    #: Parametry wykonania - wyłącznie klucze znane danemu rodzajowi.
    params: dict[str, Any] = field(default_factory=dict)
    #: `True`, gdy skutek wychodzi poza ORDLY (Allegro, kupujący).
    outward: bool = False


# ----------------------------------------------------------------------
# Walidacja
# ----------------------------------------------------------------------


def _require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise AssistantActionError(f"Brakuje pola '{label}'.")
    return value


def build_action(payload: dict[str, Any]) -> ProposedAction:
    """
    Składa i sprawdza propozycję z surowych parametrów.

    Ta sama funkcja obsługuje propozycję modelu i żądanie zapisu z
    aplikacji - dzięki temu nie ma drogi, którą dałoby się wykonać coś,
    czego nie dałoby się zaproponować.

    Raises:
        AssistantActionError: Gdy rodzaj jest nieznany albo brakuje
            parametru wymaganego przez ten rodzaj.
    """
    kind = str(payload.get("rodzaj") or payload.get("kind") or "").strip()
    if kind not in ACTION_KINDS:
        raise AssistantActionError(
            f"Nieznane dzialanie '{kind}'. Dozwolone: {', '.join(sorted(ACTION_KINDS))}."
        )

    if kind == "ustaw_stan_oferty":
        marketplace = _require_text(payload, "marketplace", "marketplace")
        external_id = _require_text(payload, "numer_oferty", "numer_oferty")
        raw_quantity = payload.get("ilosc")
        try:
            quantity = int(raw_quantity)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise AssistantActionError("Pole 'ilosc' musi byc liczba calkowita.") from None
        if quantity < 0 or quantity > MAX_QUANTITY:
            raise AssistantActionError(f"Ilosc musi miescic sie w 0..{MAX_QUANTITY}.")
        nazwa = str(payload.get("nazwa") or external_id).strip()
        return ProposedAction(
            kind="ustaw_stan_oferty",
            label=f"Wpisz {quantity} szt.",
            summary=f"Ustawi stan na półce dla „{nazwa}” na {quantity} szt. (tylko w ORDLY).",
            params={
                "marketplace": marketplace,
                "numer_oferty": external_id,
                "ilosc": quantity,
                "nazwa": nazwa,
            },
            # Stan na półce jest liczbą wyłącznie dla sprzedawcy - marketplace
            # go nie zna i nie ma go czym nadpisać.
            outward=False,
        )

    if kind == "oznacz_zamowienie":
        external_id = _require_text(payload, "numer_zamowienia", "numer_zamowienia")
        word = _require_text(payload, "status", "status").lower()
        if word not in _STATUS_BY_WORD:
            raise AssistantActionError(
                f"Status musi byc jednym z: {', '.join(_STATUS_BY_WORD)}."
            )
        kupujacy = str(payload.get("kupujacy") or "").strip()
        czyj = f" ({kupujacy})" if kupujacy else ""
        po_polsku = _STATUS_LABEL[word]
        return ProposedAction(
            kind="oznacz_zamowienie",
            label=f"Oznacz jako {po_polsku}",
            summary=(
                f"Zmieni na Allegro status zamówienia {external_id}{czyj} na "
                f"„{po_polsku}”. Kupujący zobaczy to od razu i nie da się tego "
                "cofnąć z ORDLY."
            ),
            params={
                "numer_zamowienia": external_id,
                "status": word,
                "kupujacy": kupujacy,
            },
            outward=True,
        )

    # odpowiedz_w_dyskusji
    issue_id = _require_text(payload, "numer_dyskusji", "numer_dyskusji")
    text = _require_text(payload, "tresc", "tresc")
    if len(text) > MAX_REPLY_CHARS:
        raise AssistantActionError(
            f"Odpowiedz ma {len(text)} znakow, limit to {MAX_REPLY_CHARS}."
        )
    return ProposedAction(
        kind="odpowiedz_w_dyskusji",
        label="Wyślij odpowiedź",
        summary=(
            f"Wyśle tę odpowiedź kupującemu w dyskusji {issue_id}. "
            "Wiadomości wysłanej nie da się cofnąć."
        ),
        params={"numer_dyskusji": issue_id, "tresc": text},
        outward=True,
    )


# ----------------------------------------------------------------------
# Wykonanie
# ----------------------------------------------------------------------


class AssistantActionExecutor:
    """
    Wykonuje zatwierdzone działanie, wołając ten sam serwis, co zwykły
    endpoint aplikacji.

    Nie ma tu własnej logiki biznesowej: reguła "nie da się cofnąć statusu
    anulowanego zamówienia" mieszka w `SyncOrdersService` i ma tam zostać,
    żeby obowiązywała tak samo dla przycisku w panelu i dla Ordlaka.
    """

    def __init__(
        self,
        orders_service: SyncOrdersService,
        offer_catalog_service: OfferCatalogService,
        issues_service: IssuesService,
    ) -> None:
        self._orders = orders_service
        self._catalog = offer_catalog_service
        self._issues = issues_service

    async def apply(self, action: ProposedAction) -> str:
        """
        Wykonuje działanie i zwraca zdanie potwierdzenia dla użytkownika.

        Raises:
            AssistantActionError: Gdy rodzaj jest nieznany.
            OrderNotFoundError / OfferNotFoundError / MarketplaceUnavailableError:
                przepuszczone z serwisów - endpoint mapuje je na kody HTTP,
                tak samo jak przy zwykłych zapisach.
        """
        logger.info("Ordlak: wykonuję zatwierdzone działanie {}", action.kind)

        if action.kind == "ustaw_stan_oferty":
            offer = await self._catalog.set_quantity(
                str(action.params["marketplace"]),
                str(action.params["numer_oferty"]),
                int(action.params["ilosc"]),
                # Powód trafia do historii stanu przy ofercie - po miesiącu
                # ma być widać, że tę liczbę wpisał asystent, a nie człowiek.
                "Ordlak (zatwierdzone w aplikacji)",
            )
            return f"Stan „{offer.name}” to teraz {action.params['ilosc']} szt."

        if action.kind == "oznacz_zamowienie":
            word = str(action.params["status"])
            order = await self._orders.set_fulfillment_status(
                str(action.params["numer_zamowienia"]), _STATUS_BY_WORD[word]
            )
            return f"Zamówienie {order.buyer.login} oznaczone jako {_STATUS_LABEL[word]}."

        if action.kind == "odpowiedz_w_dyskusji":
            await self._issues.reply(
                str(action.params["numer_dyskusji"]), str(action.params["tresc"])
            )
            return "Odpowiedź poszła do kupującego."

        raise AssistantActionError(f"Nieznane dzialanie '{action.kind}'.")

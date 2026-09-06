"""
DTO katalogu ofert marketplace i jego stanu powiązania z magazynem.

Katalog odpowiada na pytanie, którego historia sprzedaży nie potrafiła
postawić: "jakie oferty w ogóle mam i które z nich naprawdę zdejmują
stan?". Każda pozycja niesie ze sobą sposób powiązania, bo "powiązana"
znaczy tu dwie różne rzeczy - jawna receptura albo produkt magazynowy
o SKU równym identyfikatorowi oferty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.shared.dto.offer_mapping_dto import RecipeComponent

#: Oferta ma jawną recepturę w `offer_links`.
LINK_RECIPE = "recipe"
#: Oferta trafia w magazyn przez SKU równe identyfikatorowi oferty.
LINK_SKU = "sku"
#: Sygnatura oferty wskazuje istniejące SKU, ale receptury JESZCZE NIE MA.
#: To propozycja, nie powiązanie - sprzedaż takiej oferty nadal nie rusza
#: stanów, dopóki `OfferCatalogService.relink()` nie zapisze receptury.
LINK_SIGNATURE = "signature"
#: Sprzedaż tej oferty nie rusza magazynu.
LINK_NONE = "none"

#: Stany, w których sprzedaż REALNIE zdejmuje stan magazynowy. Tylko te
#: dwa zna `ComponentResolver`, więc tylko te dwa wolno pokazać jako
#: powiązanie - `LINK_SIGNATURE` jest podpowiedzią do kliknięcia.
RESOLVABLE_LINKS = frozenset({LINK_RECIPE, LINK_SKU})


@dataclass(frozen=True, slots=True)
class CatalogOffer:
    """
    Oferta z katalogu wraz z jej stanem powiązania z magazynem.

    `link_type` celowo rozróżnia recepturę od dopasowania po SKU:
    obie zdejmują stan, ale tylko pierwsza jest widoczna i edytowalna
    w interfejsie, więc bez tego rozróżnienia oferta działająca "po SKU"
    wyglądałaby na niepowiązaną i wołała o naprawę, której nie potrzebuje.
    """

    marketplace: str
    external_id: str
    name: str
    signature: str | None
    status: str
    available_stock: int
    sold_count: int
    price: Decimal | None
    image_url: str | None
    link_type: str
    components: tuple[RecipeComponent, ...] = field(default_factory=tuple)

    @property
    def is_linked(self) -> bool:
        """
        Mówi, czy sprzedaż tej oferty NAPRAWDĘ zdejmuje stan.

        Świadomie ostrzejsze od `link_type != LINK_NONE`: oferta
        z pasującą sygnaturą, ale bez zapisanej receptury, nie jest
        powiązana - wygląda na powiązaną tylko w katalogu, a sprzedaż
        i tak przechodzi obok magazynu.
        """
        return self.link_type in RESOLVABLE_LINKS


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    """Podsumowanie synchronizacji katalogu z marketplace."""

    marketplace: str
    fetched: int
    auto_linked: int
    unlinked: int
    synced_at: datetime


@dataclass(frozen=True, slots=True)
class OfferImportResult:
    """
    Skutek utworzenia produktów magazynowych z ofert katalogu.

    `skipped` zbiera oferty pominięte razem z powodem - import ma nie
    przerywać się na pierwszej kolizji SKU, ale też nie udawać, że
    zaimportował wszystko.
    """

    created: tuple[str, ...] = field(default_factory=tuple)
    linked: tuple[str, ...] = field(default_factory=tuple)
    skipped: tuple[tuple[str, str], ...] = field(default_factory=tuple)

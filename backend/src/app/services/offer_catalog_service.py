"""
Katalog asortymentu marketplace jako podstawa powiązań magazynowych.

DLACZEGO TEN SERWIS ISTNIEJE. Automatyczne odejmowanie stanów działa
tylko dla ofert, które `ComponentResolver` potrafi rozwiązać na produkty
magazynowe. Do tej pory jedyną listą ofert w systemie była historia
sprzedaży - identyfikator oferty poznawaliśmy dopiero po pierwszym
zamówieniu, czyli po sprzedaży, która magazynu już nie ruszyła. Efekt
był taki, że ostrzeżenie o braku powiązania nie dawało się zdjąć
z wyprzedzeniem: żeby powiązać ofertę, trzeba było najpierw pozwolić jej
sprzedać się bez powiązania.

Katalog odwraca tę kolejność. Asortyment schodzi z API marketplace,
więc oferta jest znana, zanim cokolwiek się sprzeda, a powiązanie
wskazuje na realnie istniejącą ofertę, nie na przepisany z ręki numer.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    MarketplaceUnavailableError,
)
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.shared.dto.offer_catalog_dto import (
    LINK_NONE,
    LINK_RECIPE,
    LINK_SIGNATURE,
    LINK_SKU,
    RESOLVABLE_LINKS,
    CatalogOffer,
    CatalogSyncResult,
    OfferImportResult,
)
from app.shared.dto.offer_mapping_dto import RecipeComponent
from app.utils.time import utc_now


class OfferCatalogService:
    """Pobiera asortyment z marketplace i pilnuje jego powiązania z magazynem."""

    def __init__(
        self,
        plugin: MarketplacePlugin,
        catalog_repository: OfferCatalogRepository,
        inventory_repository: InventoryRepository,
    ) -> None:
        """
        Args:
            plugin: Plugin marketplace, z którego schodzi asortyment.
            catalog_repository: Lokalna kopia katalogu ofert.
            inventory_repository: Magazyn (produkty i receptury).
        """
        self._plugin = plugin
        self._catalog = catalog_repository
        self._inventory = inventory_repository

    @property
    def marketplace(self) -> str:
        """Kod marketplace obsługiwanego przez wstrzyknięty plugin."""
        return self._plugin.marketplace_code

    async def sync(self) -> CatalogSyncResult:
        """
        Pobiera asortyment z marketplace i odświeża lokalny katalog.

        Po zapisie próbuje dowiązać oferty do magazynu po sygnaturze
        sprzedawcy - patrz `_auto_link`.

        Returns:
            Podsumowanie: ile ofert zeszło, ile udało się dowiązać
            automatycznie i ile zostało bez powiązania.

        Raises:
            MarketplaceUnavailableError: Gdy API marketplace odmówiło
                odpowiedzi. Katalog zostaje wtedy nietknięty - lepiej
                pokazać wczorajszy asortyment niż wyczyścić powiązania
                z powodu chwilowej awarii sieci.
        """
        try:
            offers = await self._plugin.get_offers()
        except AllegroApiError as exc:
            logger.error("Nie udało się pobrać asortymentu z Allegro: {}", exc)
            raise MarketplaceUnavailableError(str(exc)) from exc

        await self._catalog.replace_all(self.marketplace, offers)

        auto_linked = await self._auto_link(offers)
        catalog = await self.get_catalog()
        unlinked = sum(1 for offer in catalog if not offer.is_linked)

        logger.info(
            "Katalog {}: {} ofert, {} dowiązanych automatycznie, {} bez powiązania",
            self.marketplace,
            len(offers),
            auto_linked,
            unlinked,
        )
        return CatalogSyncResult(
            marketplace=self.marketplace,
            fetched=len(offers),
            auto_linked=auto_linked,
            unlinked=unlinked,
            synced_at=utc_now(),
        )

    async def relink(self) -> int:
        """
        Dowiązuje po sygnaturze oferty już leżące w katalogu, bez
        odpytywania marketplace.

        Potrzebne, bo dopasowanie po sygnaturze zależy od OBU stron:
        po synchronizacji użytkownik zakłada nowy produkt magazynowy
        i dopiero wtedy sygnatura ma w co trafić. Bez tej metody
        jedynym sposobem na dowiązanie byłoby ponowne ściągnięcie
        całego asortymentu.

        Returns:
            Liczba ofert dowiązanych w tym przebiegu.
        """
        offers = await self._catalog.get_all(self.marketplace)
        return await self._auto_link(offers)

    async def get_catalog(self, only_unlinked: bool = False) -> list[CatalogOffer]:
        """
        Zwraca katalog ofert wraz ze stanem powiązania każdej z nich.

        Args:
            only_unlinked: Gdy True, zwraca wyłącznie oferty, których
                sprzedaż nie rusza magazynu.
        """
        offers = await self._catalog.get_all(self.marketplace)
        recipes = {
            recipe.external_product_id: recipe.components
            for recipe in await self._inventory.get_all_offer_links()
            if recipe.marketplace == self.marketplace
        }

        described: list[CatalogOffer] = []
        for offer in offers:
            link_type, components = await self._describe_link(offer, recipes)
            if only_unlinked and link_type in RESOLVABLE_LINKS:
                continue
            described.append(
                CatalogOffer(
                    marketplace=offer.marketplace,
                    external_id=offer.external_id,
                    name=offer.name,
                    signature=offer.signature,
                    status=offer.status,
                    available_stock=offer.available_stock,
                    sold_count=offer.sold_count,
                    price=offer.price,
                    image_url=offer.image_url,
                    link_type=link_type,
                    components=components,
                )
            )
        return described

    async def import_to_stock(self, external_ids: list[str]) -> OfferImportResult:
        """
        Zakłada produkty magazynowe na podstawie wskazanych ofert i od
        razu je z nimi wiąże (jedna oferta = jeden produkt, ilość 1).

        To punkt startowy dla pustego magazynu, a nie model docelowy:
        ofertę będącą zestawem trzeba potem rozpisać na składniki
        w edytorze receptury. Dlatego import NIE nadpisuje niczego, co
        już istnieje - kolizja SKU kończy się pominięciem z powodem,
        żeby nie podmienić ręcznie opisanego produktu nazwą z Allegro.

        Stan początkowy bierzemy z liczby sztuk wystawionych w ofercie -
        to jedyna liczba, jaką marketplace o tym towarze zna. Gdy kilka
        ofert dzieli jeden fizyczny produkt, ta liczba będzie zawyżona
        i trzeba ją poprawić ręczną korektą; import zakłada tyle
        produktów, ile wskazano ofert, i nie zgaduje ich wspólnoty.
        """
        created: list[str] = []
        linked: list[str] = []
        skipped: list[tuple[str, str]] = []

        for external_id in external_ids:
            offer = await self._catalog.get(self.marketplace, external_id)
            if offer is None:
                skipped.append((external_id, "Oferty nie ma w katalogu"))
                continue

            sku = offer.signature or offer.external_id
            existing = await self._inventory.get_by_sku(sku)
            if existing is None:
                try:
                    await self._inventory.create(
                        InventoryItem(
                            sku=sku,
                            name=offer.name,
                            stock=offer.available_stock,
                            min_stock=0,
                            sale_price=offer.price,
                        )
                    )
                except DuplicateInventoryItemError:
                    skipped.append((external_id, f"SKU {sku} już istnieje"))
                    continue
                created.append(sku)

            await self._inventory.add_offer_link(self.marketplace, offer.external_id, sku, 1)
            linked.append(offer.external_id)

        logger.info(
            "Import z katalogu {}: {} nowych produktów, {} powiązań, {} pominięć",
            self.marketplace,
            len(created),
            len(linked),
            len(skipped),
        )
        return OfferImportResult(
            created=tuple(created), linked=tuple(linked), skipped=tuple(skipped)
        )

    async def _describe_link(
        self, offer: MarketplaceOffer, recipes: dict[str, tuple[RecipeComponent, ...]]
    ) -> tuple[str, tuple[RecipeComponent, ...]]:
        """
        Ustala, którą drogą sprzedaż tej oferty trafia w magazyn.

        Kolejność jest ta sama, co w `ComponentResolver`, bo inaczej
        interfejs opowiadałby o powiązaniu, którego mechanizm odejmujący
        nie stosuje. Dopasowanie po sygnaturze jest tu wyłącznie
        informacyjne - resolver go NIE zna, więc oferta trafiająca
        w magazyn tylko sygnaturą nadal wymaga receptury i `_auto_link`
        ją zakłada.
        """
        components = recipes.get(offer.external_id)
        if components:
            return LINK_RECIPE, components

        by_offer_id = await self._inventory.get_by_sku(offer.external_id)
        if by_offer_id is not None:
            return LINK_SKU, (
                RecipeComponent(sku=by_offer_id.sku, name=by_offer_id.name, quantity=1),
            )

        if offer.signature:
            by_signature = await self._inventory.get_by_sku(offer.signature)
            if by_signature is not None:
                return LINK_SIGNATURE, (
                    RecipeComponent(sku=by_signature.sku, name=by_signature.name, quantity=1),
                )

        return LINK_NONE, ()

    async def _auto_link(self, offers: list[MarketplaceOffer]) -> int:
        """
        Zakłada recepturę tam, gdzie sygnatura oferty wskazuje istniejące SKU.

        Dopasowujemy WYŁĄCZNIE po sygnaturze, nigdy po nazwie. Nazwa
        oferty jest tekstem marketingowym - "Butelka 60 ml szkło
        oranżowe + kroplomierz GRATIS" trafiłaby w butelkę i cicho
        pominęła kroplomierz, a błędne powiązanie odejmuje realny towar
        z półki. Sygnaturę sprzedawca wpisuje sam i to jedyne pole,
        w którym deklaruje własne SKU.

        Istniejące receptury zostają nietknięte - ręczna decyzja
        użytkownika jest ważniejsza od zgadywania.

        Returns:
            Liczba ofert dowiązanych w tym przebiegu.
        """
        existing = {
            recipe.external_product_id
            for recipe in await self._inventory.get_all_offer_links()
            if recipe.marketplace == self.marketplace
        }

        linked = 0
        for offer in offers:
            if not offer.signature or offer.external_id in existing:
                continue
            item = await self._inventory.get_by_sku(offer.signature)
            if item is None:
                continue
            await self._inventory.add_offer_link(
                self.marketplace, offer.external_id, item.sku, 1
            )
            linked += 1
            logger.debug(
                "Oferta {} dowiązana po sygnaturze do SKU {}", offer.external_id, item.sku
            )
        return linked

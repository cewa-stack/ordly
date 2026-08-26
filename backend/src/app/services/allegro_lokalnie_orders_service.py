"""
Zamiana sprzedaży z Allegro Lokalnie na pełnoprawne zamówienie ORDLY.

Allegro Lokalnie nie ma API, więc jedynym źródłem danych jest powiadomienie
e-mail. To, co z niego wyczytamy, wchodzi jednak do tych samych torów co
zamówienia z Allegro.pl: odejmuje stany magazynowe, liczy się do statystyk
sprzedaży i trafia na listę „do spakowania" wraz z przypomnieniem o 20:00.

Dlatego próg jest tu wyższy niż przy zwykłym powiadomieniu: rekord powstaje
WYŁĄCZNIE z kompletu danych (`AllegroLokalnieEvent.can_become_order`).
Niepełne zdarzenie nie staje się zamówieniem „na tyle, na ile się da" -
zamówienie z domyślonymi liczbami zafałszowałoby magazyn i przychód, czyli
dokładnie to, po co ORDLY istnieje. Takie zdarzenie zostaje zwykłym
powiadomieniem ze skrzynki.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.exceptions.domain_exceptions import DuplicateOrderError
from app.domain.fulfillment import FULFILLMENT_NEW
from app.domain.interfaces.order_repository import OrderRepository
from app.infrastructure.mail.allegro_lokalnie import offer_external_id

#: Kod kanału - ten sam, którym `classify_sender` opisuje pocztę z Lokalnie.
MARKETPLACE_ALLEGRO_LOKALNIE = "allegro_lokalnie"

#: Status płatności. Mail „Sprzedano…" przychodzi dopiero PO zaksięgowaniu
#: wpłaty ("Płatność zakończona"), więc zamówienie od razu jest opłacone -
#: nie ma tu odpowiednika stanu "czeka na płatność".
STATUS_PAID = "PAID"


class AllegroLokalnieOrdersService:
    """Tworzy zamówienia ORDLY na podstawie powiadomień o sprzedaży."""

    def __init__(self, order_repository: OrderRepository) -> None:
        """
        Args:
            order_repository: Repozytorium zamówień - to samo, którego
                używa synchronizacja Allegro.pl.
        """
        self._orders = order_repository

    async def create_from_event(self, event: AllegroLokalnieEvent) -> Order | None:
        """
        Zapisuje zamówienie odczytane ze zdarzenia sprzedaży.

        Returns:
            Zapisane zamówienie albo `None`, gdy zdarzenie nie jest
            sprzedażą, nie ma kompletu danych, albo to zamówienie jest
            już w bazie. `None` NIE jest błędem - wywołujący traktuje je
            jako "nie ma czego publikować".
        """
        if not event.can_become_order:
            if event.event_type == "new_order":
                logger.warning(
                    "Sprzedaż z Allegro Lokalnie ({}) bez kompletu danych - "
                    "zostaje powiadomieniem, nie zamówieniem",
                    event.message_id,
                )
            return None

        order = self._build(event)
        if await self._orders.exists(order.marketplace, order.external_id):
            return None

        try:
            await self._orders.save(order)
        except DuplicateOrderError:
            # Ten sam mail przetwarzany równolegle przez ręczną
            # synchronizację i job schedulera - drugi zapis odpada.
            logger.debug(
                "Zamówienie {} z Allegro Lokalnie zapisane równolegle - pomijam",
                order.external_id,
            )
            return None

        logger.info(
            "Zapisano zamówienie {} z Allegro Lokalnie ({} szt. {})",
            order.external_id,
            event.quantity,
            event.listing_title,
        )
        return order

    @staticmethod
    def _build(event: AllegroLokalnieEvent) -> Order:
        """
        Składa `Order` ze zdarzenia.

        `external_id` to numer transakcji z linku w mailu - jedyny
        stabilny identyfikator, jaki Allegro Lokalnie podaje, i zarazem
        klucz chroniący przed podwójnym zapisem tej samej sprzedaży.

        `total_amount` to kwota, którą kupujący ZAPŁACIŁ (z dostawą), więc
        suma pozycji bywa od niej niższa - dokładnie tak samo jak przy
        zamówieniach z Allegro.pl, gdzie kwota z checkout-formu też
        zawiera koszt przesyłki.

        Danych kontaktowych kupującego (telefon, e-mail) świadomie NIE
        zapisujemy, mimo że mail je zawiera: ORDLY nie ma dla nich
        zastosowania przy tym kanale (wysyłkę umawia się na stronie
        serwisu), a każde niepotrzebnie przechowywane dane osobowe to
        zobowiązanie, nie funkcja.
        """
        assert event.transaction_id is not None  # gwarantuje can_become_order
        assert event.listing_title is not None
        assert event.quantity is not None
        assert event.unit_amount is not None
        assert event.amount is not None

        first_name, _, last_name = (event.buyer_name or "").partition(" ")
        return Order(
            external_id=event.transaction_id,
            marketplace=MARKETPLACE_ALLEGRO_LOKALNIE,
            buyer=Customer(
                login=event.buyer_login or event.buyer_name or "nieznany",
                first_name=first_name or None,
                last_name=last_name or None,
            ),
            products=[
                Product(
                    external_id=offer_external_id(event.listing_title),
                    name=event.listing_title,
                    quantity=event.quantity,
                    unit_price=event.unit_amount,
                )
            ],
            total_amount=event.amount,
            currency="PLN",
            status=STATUS_PAID,
            order_date=event.received_at,
            # Mail przychodzi w momencie opłacenia, więc paczka dopiero
            # czeka na spakowanie - dzięki temu zamówienie wchodzi do
            # listy „do spakowania" i do przypomnienia o 20:00.
            fulfillment_status=FULFILLMENT_NEW,
        )

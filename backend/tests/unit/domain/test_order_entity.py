"""Testy jednostkowe encji domenowej Order."""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities.product import Product


class TestOrderEntity:
    """Testy zachowania encji Order, w szczególności products_summary."""

    def test_products_summary_wylicza_czytelne_podsumowanie(self, sample_order):
        """Sprawdza, że products_summary poprawnie formatuje listę produktów."""
        assert sample_order.products_summary == "Kubek ceramiczny x2"

    def test_products_summary_dla_pustej_listy_produktow(self):
        """Sprawdza fallback 'brak danych' gdy zamówienie nie ma produktów."""
        from datetime import datetime

        from app.domain.entities.customer import Customer
        from app.domain.entities.order import Order

        order = Order(
            external_id="EMPTY-1",
            marketplace="allegro",
            buyer=Customer(login="test"),
            products=[],
            total_amount=Decimal("0.00"),
            currency="PLN",
            status="NEW",
            order_date=datetime(2026, 1, 1),
        )
        assert order.products_summary == "brak danych"

    def test_product_total_price_mnozy_cene_przez_ilosc(self):
        """Sprawdza wyliczenie total_price w encji Product."""
        product = Product(
            external_id="P1", name="Test", quantity=3, unit_price=Decimal("10.00")
        )
        assert product.total_price == Decimal("30.00")

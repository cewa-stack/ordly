"""Model ORM tabeli katalogu ofert pobranych z marketplace."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class MarketplaceOfferModel(Base, TimestampMixin):
    """
    Tabela `marketplace_offers`.

    Lokalna kopia asortymentu wystawionego na marketplace, odświeżana
    przez `OfferCatalogService`. Celowo NIE ma klucza obcego do
    `inventory_items` - powiązanie oferty z magazynem żyje w
    `offer_links` i bywa wieloskładnikowe (butelka + nakrętka +
    kroplomierz), więc kolumna "jeden do jednego" tylko by kłamała.
    """

    __tablename__ = "marketplace_offers"
    __table_args__ = (
        UniqueConstraint("marketplace", "external_id", name="uq_marketplace_offer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    #: Sygnatura sprzedawcy z Allegro (`external.id`) - zwykle własne SKU.
    signature: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    available_stock: Mapped[int] = mapped_column(nullable=False, default=0)
    sold_count: Mapped[int] = mapped_column(nullable=False, default=0)
    price: Mapped[Decimal | None] = mapped_column(nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(nullable=False)

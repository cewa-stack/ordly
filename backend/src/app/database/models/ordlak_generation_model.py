"""Model ORM tabeli historii generacji ofert Ordlaka."""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class OrdlakGenerationModel(Base, TimestampMixin):
    """
    Tabela `ordlak_generations`.

    Kwoty trzymamy jako `Float`, a nie `Numeric` - to wejście do kalkulacji
    orientacyjnej ceny ofertowej, a nie zapis księgowy transakcji (te żyją
    w `orders`). Zdjęcia nie są przechowywane, tylko ich liczba.
    """

    __tablename__ = "ordlak_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # wejście od użytkownika
    user_note: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    purchase_cost: Mapped[float] = mapped_column(Float, nullable=False)
    inbound_shipping_cost: Mapped[float] = mapped_column(Float, nullable=False)
    buyer_shipping_cost: Mapped[float] = mapped_column(Float, nullable=False)
    commission_percent: Mapped[float] = mapped_column(Float, nullable=False)
    target_margin_percent: Mapped[float] = mapped_column(Float, nullable=False)
    photo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # wynik modelu AI
    generated_title: Mapped[str] = mapped_column(String(200), nullable=False)
    generated_description_html: Mapped[str] = mapped_column(Text, nullable=False)
    ai_condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # wynik kalkulacji (deterministyczny)
    suggested_price: Mapped[float] = mapped_column(Float, nullable=False)

    # ręczna korekta użytkownika przed skopiowaniem na Allegro
    final_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    final_description_html: Mapped[str | None] = mapped_column(Text, nullable=True)

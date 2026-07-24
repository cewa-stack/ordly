"""Model ORM tabeli subskrypcji Web Push."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class PushSubscriptionModel(Base, TimestampMixin):
    """
    Tabela `push_subscriptions`.

    Jeden wiersz na jedną aktywną subskrypcję przeglądarki/urządzenia
    (TOOM Mobile uruchomiony jako PWA). `endpoint` bywa długim URL-em
    (dostawcy push jak FCM/Mozilla potrafią zwracać >200 znaków),
    stąd szeroka kolumna.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(
        String(1000), nullable=False, unique=True, index=True
    )
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)

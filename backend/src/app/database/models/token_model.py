"""Model ORM tabeli tokenów OAuth2."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class TokenModel(Base, TimestampMixin):
    """
    Tabela `tokens`.

    Przechowuje zaszyfrowane tokeny OAuth2 (access + refresh) dla
    danego marketplace. Szyfrowanie odbywa się w warstwie
    infrastructure/plugins/{marketplace}/auth.py przed zapisem -
    ta tabela nigdy nie widzi tokenu w plaintext.
    """

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    encrypted_access_token: Mapped[str] = mapped_column(nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

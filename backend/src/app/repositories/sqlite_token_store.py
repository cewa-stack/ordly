"""Implementacja TokenStore oparta o SQLite (tabela tokens)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.token_model import TokenModel
from app.domain.interfaces.token_store import StoredTokens, TokenStore


class SqliteTokenStore(TokenStore):
    """Przechowuje zaszyfrowane tokeny OAuth2 w tabeli `tokens`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tokens(self, marketplace: str) -> StoredTokens | None:
        """Odczytuje zapisane (zaszyfrowane) tokeny dla danego marketplace."""
        stmt = select(TokenModel).where(TokenModel.marketplace == marketplace)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return StoredTokens(
            encrypted_access_token=model.encrypted_access_token,
            encrypted_refresh_token=model.encrypted_refresh_token,
            expires_at=model.expires_at,
        )

    async def save_tokens(
        self,
        marketplace: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
    ) -> None:
        """
        Zapisuje lub nadpisuje tokeny dla danego marketplace (upsert).

        Używamy natywnego UPSERT SQLite (ON CONFLICT), ponieważ kolumna
        `marketplace` ma unique constraint.
        """
        stmt = sqlite_insert(TokenModel).values(
            marketplace=marketplace,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["marketplace"],
            set_={
                "encrypted_access_token": encrypted_access_token,
                "encrypted_refresh_token": encrypted_refresh_token,
                "expires_at": expires_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

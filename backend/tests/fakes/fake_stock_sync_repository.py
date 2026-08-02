"""Fake implementacja StockSyncRepository - znaczniki w pamięci do testów."""

from __future__ import annotations

from app.domain.interfaces.stock_sync_repository import StockSyncRepository


class FakeStockSyncRepository(StockSyncRepository):
    """Przechowuje znaczniki przetworzonych operacji w zbiorze krotek."""

    def __init__(self) -> None:
        self.processed: set[tuple[str, str, str]] = set()

    async def was_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        return (marketplace, reference, operation) in self.processed

    async def mark_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        key = (marketplace, reference, operation)
        if key in self.processed:
            return False
        self.processed.add(key)
        return True

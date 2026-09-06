"""
Sobowtór klienta Anthropic (`AsyncAnthropic`) - tylko `messages.create`.

Używany przez testy asystenta Ordlaka: serwis dostaje go przez
`client_factory`, więc żaden test nie wychodzi do sieci ani nie potrzebuje
klucza API. Bloki odpowiedzi są zwykłymi dataclassami z polem `type` -
serwis czyta je przez `getattr`, dokładnie tak jak prawdziwe modele SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.shared.dto.stats_dto import HealthStatus


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    id: str = "toolu_1"
    type: str = "tool_use"


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str
    type: str = "thinking"


@dataclass
class FakeResponse:
    content: list[Any]
    stop_reason: str = "end_turn"


class _Messages:
    def __init__(self, owner: FakeAnthropic) -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> FakeResponse:
        self._owner.calls.append(kwargs)
        if self._owner.raise_error is not None:
            raise self._owner.raise_error
        # Ostatnia odpowiedź powtarza się przy dalszych wywołaniach - dzięki
        # temu test pętli narzędzi może podać jedną odpowiedź `tool_use`
        # i sprawdzić, że serwis kiedyś się poddaje.
        index = min(len(self._owner.calls) - 1, len(self._owner.responses) - 1)
        return self._owner.responses[index]


class FakeAnthropic:
    """Oddaje kolejne odpowiedzi z listy i zapamiętuje wysłane zapytania."""

    def __init__(
        self,
        responses: list[FakeResponse] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.responses = responses or [FakeResponse([TextBlock("Gotowe.")])]
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []
        self.messages = _Messages(self)


class StubHealthService:
    """
    Zastępuje `HealthService`, który do działania potrzebuje sesji bazy.

    Asystent czyta z niego wyłącznie gotowy `HealthStatus`, więc test nie
    zyskałby nic na prawdziwej implementacji.
    """

    def __init__(self, marketplace_ok: bool = True) -> None:
        self._marketplace_ok = marketplace_ok

    async def check(self) -> HealthStatus:
        return HealthStatus(
            uptime_human="2 dni",
            last_sync_human="5 minut temu",
            database_ok=True,
            marketplace_connection_ok=self._marketplace_ok,
        )

"""Testy jednostkowe IssuesService."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.entities.issue import Issue, IssueMessage
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.services.issues_service import IssuesService

_SAMPLE_ISSUE = Issue(
    external_id="ISSUE-1",
    marketplace="allegro",
    type="DISPUTE",
    status="DISPUTE_ONGOING",
    order_external_id="ORDER-1",
    buyer_login="kupujacy_testowy",
    subject="nie otrzymałem towaru",
    description=None,
    opened_at=datetime(2026, 7, 1, 10, 0, 0),
    messages_count=2,
    chat_active=True,
    last_message_at=datetime(2026, 7, 1, 12, 0, 0),
)

_SAMPLE_MESSAGE = IssueMessage(
    id="MSG-1",
    text="Proszę o wyjaśnienie problemu.",
    author_login="kupujacy_testowy",
    author_role="BUYER",
    created_at=datetime(2026, 7, 1, 10, 0, 0),
)


class TestIssuesService:
    """Testy pobierania dyskusji/reklamacji i wysyłania odpowiedzi na żądanie."""

    @pytest.mark.asyncio
    async def test_zwraca_liste_dyskusji_z_pluginu(self, fake_marketplace_plugin):
        """list_issues() powinno zwrócić dokładnie to, co da plugin."""
        fake_marketplace_plugin.issues_to_return = [_SAMPLE_ISSUE]
        service = IssuesService(fake_marketplace_plugin)

        issues = await service.list_issues()

        assert issues == [_SAMPLE_ISSUE]

    @pytest.mark.asyncio
    async def test_list_issues_tlumaczy_blad_api_na_marketplace_unavailable(
        self, fake_marketplace_plugin
    ):
        """Niedostępność marketplace powinna być jasnym MarketplaceUnavailableError."""
        fake_marketplace_plugin.should_raise_issues_api_error = True
        service = IssuesService(fake_marketplace_plugin)

        with pytest.raises(MarketplaceUnavailableError):
            await service.list_issues()

    @pytest.mark.asyncio
    async def test_zwraca_watek_wiadomosci(self, fake_marketplace_plugin):
        """get_thread() powinno zwrócić wiadomości z pluginu dla danego issue_id."""
        fake_marketplace_plugin.issue_messages_to_return = [_SAMPLE_MESSAGE]
        service = IssuesService(fake_marketplace_plugin)

        messages = await service.get_thread("ISSUE-1")

        assert messages == [_SAMPLE_MESSAGE]

    @pytest.mark.asyncio
    async def test_watek_jest_sortowany_chronologicznie(self, fake_marketplace_plugin):
        """
        Allegro oddaje czat od najnowszej wiadomości - serwis ma go
        odwrócić, żeby UI czytało się jak komunikator (najstarsza u góry).
        """
        najnowsza = IssueMessage(
            id="MSG-3",
            text="Dziękuję, sprawa zamknięta.",
            author_login="kupujacy_testowy",
            author_role="BUYER",
            created_at=datetime(2026, 7, 3, 9, 0, 0),
        )
        srodkowa = IssueMessage(
            id="MSG-2",
            text="Paczka poszła dziś rano.",
            author_login="Ty",
            author_role="SELLER",
            created_at=datetime(2026, 7, 2, 8, 0, 0),
        )
        fake_marketplace_plugin.issue_messages_to_return = [
            najnowsza,
            srodkowa,
            _SAMPLE_MESSAGE,
        ]
        service = IssuesService(fake_marketplace_plugin)

        messages = await service.get_thread("ISSUE-1")

        assert [m.id for m in messages] == ["MSG-1", "MSG-2", "MSG-3"]

    @pytest.mark.asyncio
    async def test_wysyla_odpowiedz_przez_plugin(self, fake_marketplace_plugin):
        """reply() powinno przekazać issue_id i tekst do pluginu bez zmian."""
        service = IssuesService(fake_marketplace_plugin)

        await service.reply("ISSUE-1", "Dzień dobry, już się tym zajmuję.")

        assert fake_marketplace_plugin.reply_calls == [
            ("ISSUE-1", "Dzień dobry, już się tym zajmuję.")
        ]

    @pytest.mark.asyncio
    async def test_reply_tlumaczy_blad_api_na_marketplace_unavailable(
        self, fake_marketplace_plugin
    ):
        """Błąd API przy wysyłce odpowiedzi powinien być jasnym MarketplaceUnavailableError."""
        fake_marketplace_plugin.should_raise_issues_api_error = True
        service = IssuesService(fake_marketplace_plugin)

        with pytest.raises(MarketplaceUnavailableError):
            await service.reply("ISSUE-1", "tresc")

"""Fake bota Telegram - rejestruje wywołania delete_message zamiast API."""

from __future__ import annotations


class FakeBot:
    """
    Minimalny bot testowy pokrywający tylko to, czego używa czyszczenie czatu.

    `fail_message_ids` pozwala zasymulować wiadomości, których Telegram nie
    pozwala usunąć (zbyt stare lub już usunięte) - takie wywołanie rzuca
    wyjątek, tak jak realne API.
    """

    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []
        self.fail_message_ids: set[int] = set()

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        if message_id in self.fail_message_ids:
            raise RuntimeError("Wiadomość zbyt stara, by ją usunąć")
        self.deleted.append((chat_id, message_id))

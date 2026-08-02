"""
Jednorazowy skrypt do wykonania pierwszej autoryzacji OAuth2 z Allegro.

Aplikacja (app/main.py) nigdzie nie wywołuje AllegroPlugin.authenticate()
automatycznie - z założenia, żeby restart procesu nigdy nie otwierał
niespodziewanie przeglądarki ani nie czekał na interakcję użytkownika.
Ten skrypt jest jedynym miejscem, które świadomie uruchamia pełny
przepływ Authorization Code + PKCE i zapisuje otrzymane tokeny w bazie.

Użycie:
    uv run python scripts/allegro_login.py

Wymaga, aby port z ALLEGRO_REDIRECT_URI (domyślnie 53682) był
osiągalny z przeglądarki, w której zatwierdzasz logowanie - na
headless Raspberry Pi zrób najpierw tunel SSH (patrz docs/deployment.md):

    ssh -L 53682:localhost:53682 pi@<adres-raspberry-pi>

i uruchom ten skrypt w tej samej sesji SSH.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.engine import create_engine, create_session_factory
from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.plugin import AllegroPlugin
from app.repositories.sqlite_token_store import SqliteTokenStore


async def main() -> None:
    """Uruchamia pełny przepływ autoryzacji Allegro i zapisuje tokeny."""
    settings = get_settings()
    configure_logging(settings.logging, settings.app.debug)

    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        token_store = SqliteTokenStore(session)
        plugin = AllegroPlugin(config=AllegroConfig(), token_store=token_store)

        print("Otwórz w przeglądarce podany niżej URL i zaloguj się do Allegro.")
        print("Czekam do 5 minut na zatwierdzenie autoryzacji...\n")

        await plugin.authenticate()
        await session.commit()

    await engine.dispose()
    print("\nGotowe - tokeny zapisane w bazie. Możesz teraz uruchomić aplikację.")


if __name__ == "__main__":
    asyncio.run(main())

"""
Konfiguracja środowiska Alembic dostosowana do asynchronicznego
silnika SQLAlchemy (aiosqlite).
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from app.core.config import get_settings
from app.database.base import Base

# Import calego pakietu, nie pojedynczych klas: `models/__init__.py` i tak
# sciaga wszystkie modele, a wypisana tu druga lista nazw cicho rozjezdzala
# sie z pierwsza - po usunieciu modelu `alembic upgrade` wywracal sie na
# ImportError, mimo ze sama migracja byla poprawna.
import app.database.models  # noqa: F401 - rejestruje modele w Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database.database_url)


def run_migrations_offline() -> None:
    """Uruchamia migracje w trybie 'offline' (generowanie SQL bez połączenia)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Wykonuje migracje na przekazanym połączeniu synchronicznym."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Uruchamia migracje w trybie 'online' (rzeczywiste połączenie async)."""
    connectable: AsyncEngine = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

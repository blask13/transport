from logging.config import fileConfig
import os

from sqlalchemy import create_engine
from alembic import context

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# === MODELE APLIKACJI ===
from app.models import Base

# Metadata dla autogenerate
target_metadata = Base.metadata

APP_TABLES = {
    "users",
    "routes",
    "parcels",
    "route_parcel_matches",
}

def include_object(object, name, type_, reflected, compare_to):
    # Interesują nas WYŁĄCZNIE tabele aplikacyjne
    if type_ == "table":
        return name in APP_TABLES

    # Indeksy / sekwencje tylko dla tabel aplikacyjnych
    if type_ in {"index", "sequence"}:
        if compare_to is not None:
            return compare_to.table.name in APP_TABLES
        return False

    return True


def get_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    engine = create_engine(get_database_url())

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

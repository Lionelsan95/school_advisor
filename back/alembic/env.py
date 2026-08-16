"""Alembic environment.

Used for DDL only — there are no ORM models. SQLAlchemy arrives as an Alembic
dependency and is not used at runtime by the application, which talks to
Postgres through psycopg directly.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """Read DATABASE_URL and point SQLAlchemy at psycopg 3.

    One environment variable serves the whole application. psycopg (used at
    runtime) wants a plain `postgresql://` URL, while SQLAlchemy would default
    that scheme to psycopg2, which this project does not install. The driver
    suffix is added here rather than pushing a second variable into the
    environment.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Migrations must never fall back to a "
            "hardcoded connection string."
        )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

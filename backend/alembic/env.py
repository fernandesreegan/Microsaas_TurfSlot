"""Alembic environment: uses the app's settings and full model metadata.

URL resolution order:
  1. ``alembic -x dburl=postgresql://...``
  2. ``ALEMBIC_DATABASE_URL`` environment variable
  3. ``app.config.settings.DATABASE_URL`` (reads ``DATABASE_URL`` / .env)
The URL is normalized to the psycopg (v3) driver via ``normalize_db_url``.
"""

from __future__ import annotations

import logging
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from alembic import context
from app.database import Base, normalize_db_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _resolve_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("dburl") or os.environ.get("ALEMBIC_DATABASE_URL")
    if not url:
        from app.config import settings

        url = settings.DATABASE_URL
    return normalize_db_url(url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DB connection (``alembic upgrade head --sql``)."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

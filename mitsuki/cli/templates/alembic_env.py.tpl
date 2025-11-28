import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from {{app_name}}.src.domain import *
from mitsuki.data import convert_to_async_url, get_sqlalchemy_metadata

target_metadata = get_sqlalchemy_metadata()


def get_url():
    """Get database URL from application.yml based on MITSUKI_PROFILE."""
    import yaml
    profile = os.getenv("MITSUKI_PROFILE", "")

    if profile:
        config_file = f"application-{profile}.yml"
        if not os.path.exists(config_file):
            raise FileNotFoundError(
                f"Configuration file '{config_file}' not found for MITSUKI_PROFILE='{profile}'. "
                f"Available profiles: dev, stg, prod (or unset MITSUKI_PROFILE to use application.yml)"
            )
    else:
        config_file = "application.yml"

    with open(config_file) as f:
        app_config = yaml.safe_load(f)

    url = app_config["database"]["url"]
    return convert_to_async_url(url)


def render_item(type_, obj, autogen_context):
    """Render custom types for migrations."""
    if type_ == "type":
        if obj.__class__.__name__ == "GUID":
            autogen_context.imports.add("from mitsuki.data.adapters.sqlalchemy import GUID")
            return "GUID()"
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

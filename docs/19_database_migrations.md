# Database Migrations with Alembic

Mitsuki provides optional, pre-configured support for database migrations using [Alembic](https://alembic.sqlalchemy.org/), the standard migration tool for SQLAlchemy.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Migration Workflow](#migration-workflow)
- [How It Works](#how-it-works)
- [Manual Setup](#manual-setup)

## Overview

When you enable Alembic support, Mitsuki's CLI tool automatically generates the necessary configuration files, allowing you to use standard Alembic commands to manage your database schema.

**What you get:**
- **Automatic Setup**: `mitsuki init` can create and configure Alembic for you.
- **Standard Workflow**: Use familiar commands like `alembic revision`, `alembic upgrade`, and `alembic downgrade`.
- **Pre-configured Environment**: The generated `env.py` is already set up to work with Mitsuki's configuration system and entity discovery.

## Getting Started

The easiest way to start using Alembic is to enable it when creating a new project with the `mitsuki init` command.

1.  **Run `mitsuki init`**

    ```bash
    mitsuki init
    ```

2.  **Enable Alembic**

    When prompted, answer "yes" to setting up Alembic:

    ```
    Setup Alembic for database migrations? [Y/n]: y
    ```

3.  **Generated Files**

    The CLI will generate the following files in your project's root directory:

    ```
    my_app/
    ├── alembic.ini              # Alembic configuration
    ├── alembic/                 # Migration scripts
    │   ├── env.py               # Alembic runtime environment
    │   ├── script.py.mako       # Migration template
    │   └── versions/            # Directory for migration files
    └── src/
        └── my_app/
            └── ...
    ```

4.  **Success Message**

    The CLI will confirm that Alembic has been configured:

    ```
    ✓ Alembic configured

    To create your first migration:
      cd my_app
      alembic revision --autogenerate -m "initial schema"
      alembic upgrade head
    ```

## Migration Workflow

Once your project is set up, you can use the standard Alembic workflow to manage your database schema.

### 1. Import Your Entities

Before generating a migration, you need to make sure Alembic can see your `@Entity` classes. The generated `alembic/env.py` includes a wildcard import:

```python
from my_app.src.domain import *
```

This automatically imports all entities in your `domain` package. If you place your entities in different packages, you'll need to update this import or add additional imports:

```python
# alembic/env.py

# ... (existing code)

# Import your entities so Mitsuki can discover them
from my_app.src.domain import *
from my_app.src.models import *  # If you have entities in other packages

# ... (rest of the file)
```

### 2. Generate a Migration

Whenever you create a new entity or modify an existing one, you can generate a new migration script automatically:

```bash
alembic revision --autogenerate -m "Add Post entity"
```

This will create a new file in the `alembic/versions/` directory containing the `upgrade` and `downgrade` functions for applying and reverting the schema changes.

### 3. Apply the Migration

To apply the migration to your database, run:

```bash
alembic upgrade head
```

This will execute the `upgrade` function in the latest migration script, bringing your database schema up to date.

### 4. Downgrade a Migration

To revert the last migration, you can use:

```bash
alembic downgrade -1
```

## How It Works

The integration between Mitsuki and Alembic is designed to be seamless and requires minimal configuration on your part.

-   **`alembic.ini`**: This is the main configuration file for Alembic. The generated file is pre-configured with the location of the migration scripts.

-   **`alembic/env.py`**: This is the key file for the integration. It's responsible for:
    -   Reading your `application.yml` or `application-{profile}.yml` to get the correct database URL based on the `MITSUKI_PROFILE` environment variable.
    -   Importing your entity classes so that Alembic's autogenerate feature can detect changes (via `from {{app_name}}.src.domain import *`).
    -   Getting the SQLAlchemy metadata from Mitsuki using `get_sqlalchemy_metadata()`, which contains the schema information for all your entities.

-   **`get_sqlalchemy_metadata()`**: This function from `mitsuki.data` automatically discovers all registered `@Entity` classes and builds SQLAlchemy metadata without requiring database initialization or async operations.

## Manual Setup

If you have an existing Mitsuki project and want to add Alembic support, you can follow these steps:

1.  **Install Alembic**:
    ```bash
    pip install alembic
    ```

2.  **Initialize Alembic**:
    ```bash
    alembic init alembic
    ```

3.  **Configure `alembic/env.py`**:
    Replace the contents of `alembic/env.py` with the following, making sure to update the import paths to match your project structure:
    ```python
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

    from my_app.src.domain import *
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
    ```

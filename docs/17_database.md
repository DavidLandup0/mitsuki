# Database Configuration

## Table of Contents

- [Overview](#overview)
- [Basic Configuration](#basic-configuration)
- [Connection Pooling](#connection-pooling)
- [Supported Databases](#supported-databases)
- [Environment-Specific Configuration](#environment-specific-configuration)
- [Query Logging](#query-logging)
- [Advanced Options](#advanced-options)


## Overview

Mitsuki uses SQLAlchemy as its database adapter, providing support for:
- **PostgreSQL**
- **MySQL/MariaDB**
- **SQLite**

Database configuration is specified in `application.yml` and can be overridden via environment variables.


## Basic Configuration

### SQLite

Perfect for local development and testing:

```yaml
database:
  url: sqlite:///app.db
  adapter: sqlalchemy
  echo: false
```

**Features:**
- Single file database
- No server required
- Connection pooling automatically disabled
- Great for prototyping

### PostgreSQL

Recommended for production:

```yaml
database:
  url: postgresql://username:password@localhost:5432/mydb
  adapter: sqlalchemy
  echo: false
```

**Connection string format:**
```
postgresql://[user[:password]@][host][:port][/dbname]
```

### MySQL/MariaDB

```yaml
database:
  url: mysql://username:password@localhost:3306/mydb
  adapter: sqlalchemy
  echo: false
```

**Connection string format:**
```
mysql://[user[:password]@][host][:port][/dbname]
```

## Connection Pooling

Connection pooling reuses database connections for better performance.

### Configuration

```yaml
database:
  url: postgresql://localhost/mydb
  pool:
    enabled: true       # Enable pooling (default: true)
    size: 10            # Number of connections to maintain (default: 10)
    max_overflow: 20    # Max connections beyond pool_size (default: 20)
    timeout: 30         # Seconds to wait for connection (default: 30)
    recycle: 3600       # Seconds before recycling connections (default: 3600)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `true` | Enable connection pooling (auto-disabled for SQLite) |
| `size` | `10` | Number of connections to keep open |
| `max_overflow` | `20` | Additional connections when pool is exhausted |
| `timeout` | `30` | Seconds to wait before timing out |
| `recycle` | `3600` | Seconds before recycling a connection (prevents stale connections) |

### SQLite Behavior

Connection pooling is **automatically disabled** for SQLite databases since SQLite uses file locking and doesn't benefit from pooling.

## Environment-Specific Configuration

### Using Profiles

**`application.yml` (defaults):**
```yaml
database:
  url: sqlite:///dev.db
```

**`application-development.yml`:**
```yaml
database:
  url: sqlite:///dev.db
  echo: true
```

**`application-staging.yml`:**
```yaml
database:
  url: postgresql://staging-db.internal/myapp
  pool:
    size: 5
    max_overflow: 10
```

**`application-production.yml`:**
```yaml
database:
  url: postgresql://prod-db.internal/myapp
  pool:
    size: 20
    max_overflow: 40
    recycle: 1800
```

### Environment Variables

Override any database setting:

```bash
# Database URL
export MITSUKI_DATABASE_URL=postgresql://prod-server/db

# Pool settings
export MITSUKI_DATABASE_POOL_SIZE=20
export MITSUKI_DATABASE_POOL_MAX_OVERFLOW=40
export MITSUKI_DATABASE_POOL_TIMEOUT=60
export MITSUKI_DATABASE_POOL_RECYCLE=3600

# Adapter
export MITSUKI_DATABASE_ADAPTER=sqlalchemy

# Logging
export MITSUKI_DATABASE_ECHO=true
```

**Run with environment variables:**
```bash
MITSUKI_DATABASE_URL=postgresql://prod/db python app.py
```

## Query Logging

### Enable SQL Query Logging

See all executed SQL queries in your logs:

```yaml
database:
  echo: true  # Enable SQLAlchemy query logging

logging:
  sqlalchemy: true  # Enable detailed SQLAlchemy logs
  level: DEBUG  # Show debug-level logs
```

**Output example:**
```
2024-01-01 12:00:00 - sqlalchemy.engine - INFO - BEGIN (implicit)
2024-01-01 12:00:00 - sqlalchemy.engine - INFO - SELECT users.id, users.name, users.email
FROM users WHERE users.email = ?
2024-01-01 12:00:00 - sqlalchemy.engine - INFO - ('alice@example.com',)
2024-01-01 12:00:00 - sqlalchemy.engine - INFO - COMMIT
```

### Production Logging

In production, you can disable the echo but keep structured logging:

```yaml
database:
  echo: false

logging:
  level: INFO
  sqlalchemy: false
```

### Connection Lifecycle

Mitsuki automatically manages connection lifecycle:

1. **Startup** - Pool initialized on application start
2. **Request** - Connection acquired from pool
3. **Processing** - Query execution
4. **Release** - Connection returned to pool
5. **Recycling** - Connections recycled after `recycle` timeout
6. **Shutdown** - Clean pool shutdown on application stop

## Troubleshooting

### "Database adapter not initialized"

**Cause:** Application started without database configuration.

**Fix:** Create `application.yml`:
```yaml
database:
  url: sqlite:///app.db
```

### "Too many connections"

**Cause:** Pool exhausted or database connection limit reached.

**Fix:** Increase pool size or database max_connections:
```yaml
pool:
  size: 20
  max_overflow: 40
```

### "Connection timeout"

**Cause:** Database unreachable or pool timeout too low.

**Fix:** Increase timeout or check database connectivity:
```yaml
pool:
  timeout: 60  # Increase timeout
```

### "Stale connection"

**Cause:** Connection held too long.

**Fix:** Enable connection recycling:
```yaml
pool:
  recycle: 1800  # Recycle after 30 minutes
```


## Next Steps

- [Repositories](./03_repositories.md) - Using the data layer
- [Configuration](./06_configuration.md) - General configuration guide
- [Profiles](./05_profiles.md) - Environment-specific settings
- [Database Queries](./08_database_queries.md) - Custom queries with @Query

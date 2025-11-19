# Database Queries

Mitsuki provides multiple ways to query your database, from simple method-name-based queries to complex custom SQL.

## Table of Contents
- [Query DSL (Method Names)](#query-dsl-method-names)
- [Custom Queries with @Query](#custom-queries-with-query)
- [Native SQL Queries](#native-sql-queries)
- [Modifying Queries](#modifying-queries)
- [Custom SQLAlchemy Core Queries](#custom-sqlalchemy-core-queries)
- [Query Logging](#query-logging)

## Inherited CRUD Methods

By virtue of being a `@CrudRepository` - any repository will auto-inherit basic CRUD methods for a given entity:

```python
@CrudRepository(entity=User)
class UserRepository:
    pass
```

This user repository can then run:

```python
user = User(id="uid", name="Alice", email="alice@example.com")

repo.save(user) # Saves user to the db
repo.find_by_id("uid") # Finds by ID
repo.find_all() # Finds all entities in db

# Pagination (both page and size required)
repo.find_all(page=0, size=10)  # First 10
repo.find_all(page=1, size=10)  # Next 10

# Sorting
repo.find_all(sort_by="name")  # Ascending
repo.find_all(sort_by="name", sort_desc=True)  # Descending

# Combined
repo.find_all(page=2, size=20, sort_by="created_at", sort_desc=True)

repo.delete(user) # Deletes entity from db
repo.delete_by_id("uid") # Deletes entity by ID
repo.count() # Counts number of entities in db
repo.exists_by_id("uid") # Checks existance by ID
```

## Query DSL (Method Names)

The simplest way to create custom queries is by using method naming conventions. Mitsuki automatically parses method names and generates the appropriate SQL:

```python
@CrudRepository(entity=User)
class UserRepository:
    # SELECT * FROM users WHERE email = ?
    async def find_by_email(self, email: str) -> Optional[User]: ...

    # SELECT * FROM users WHERE age > ?
    async def find_by_age_greater_than(self, age: int) -> List[User]: ...

    # SELECT * FROM users WHERE name = ? AND active = ?
    async def find_by_name_and_active(self, name: str, active: bool) -> List[User]: ...

    # SELECT COUNT(*) FROM users WHERE active = ?
    async def count_by_active(self, active: bool) -> int: ...
```

**Supported patterns:**
- `find_by_<field>` - Find by single field
- `find_by_<field>_and_<field>` - Multiple conditions with AND
- `find_by_<field>_or_<field>` - Multiple conditions with OR
- `find_by_<field>_<operator>` - With comparison operators
- `count_by_<field>` - Count matching records
- `delete_by_<field>` - Delete matching records
- `exists_by_<field>` - Check if records exist

**Supported operators:**
- `greater_than`, `greater_than_or_equal`
- `less_than`, `less_than_or_equal`
- `like`, `in`, `not_in`
- `is_null`, `is_not_null`

## Custom Queries with @Query

For complex queries beyond what DSL can express, use the `@Query` decorator with SQLAlchemy ORM syntax.

### Basic Custom Query

```python
from mitsuki import CrudRepository, Query

@CrudRepository(entity=User)
class UserRepository:
    @Query("""
        SELECT u FROM User u
        WHERE u.email = :email
    """)
    async def find_by_custom_email(self, email: str) -> Optional[User]: ...
```

### Multiple Parameters

```python
@Query("""
    SELECT u FROM User u
    WHERE u.age BETWEEN :min_age AND :max_age
    AND u.active = :active
    ORDER BY u.created_at DESC
""")
async def find_active_in_age_range(
    self,
    min_age: int,
    max_age: int,
    active: bool
) -> List[User]: ...
```

**Parameter Binding:**
- Use `:param_name` for named parameters (recommended)
- Use `?1`, `?2`, etc. for positional parameters
- Parameters automatically matched to method argument names/positions
- Parameter names must match the placeholder names in named binding

### Positional Parameters

For simpler queries, you can use positional parameters like:

```python
@Query("""
    SELECT u FROM User u
    WHERE u.age > ?1 AND u.active = ?2
""")
async def find_active_older_than(self, min_age: int, active: bool) -> List[User]: ...
```

**Note**: Positional parameters are 1-indexed (`?1`, `?2`, etc.) and mapped to method arguments in order.

### Pagination

Add `limit` and `offset` parameters to any query method for pagination:

```python
@Query("""
    SELECT u FROM User u
    WHERE u.active = :active
    ORDER BY u.created_at DESC
""")
async def find_active_paginated(
    self,
    active: bool,
    limit: int,
    offset: int
) -> List[User]: ...

# Usage
page1 = await repo.find_active_paginated(True, limit=20, offset=0)
page2 = await repo.find_active_paginated(True, limit=20, offset=20)
```

**Mitsuki automatically:**
- Detects `limit` and `offset` parameters
- Appends `LIMIT` and `OFFSET` clauses to the query
- Removes them from parameter binding

### Complex Queries with Joins

```python
@Query("""
    SELECT u FROM User u
    JOIN Order o ON u.id = o.user_id
    WHERE o.total > :min_total
    GROUP BY u.id
    HAVING COUNT(o.id) > :min_orders
    ORDER BY COUNT(o.id) DESC
""")
async def find_high_value_customers(
    self,
    min_total: float,
    min_orders: int
) -> List[User]: ...
```

### Aggregation Queries

```python
@Query("""
    SELECT COUNT(u), AVG(u.age)
    FROM User u
    WHERE u.active = :active
""")
async def get_active_user_stats(self, active: bool) -> dict: ...
```

## Native SQL Queries

For database-specific optimizations or features, use native SQL with `native=True`.

```python
@Query("""
    SELECT * FROM users u
    WHERE u.age > :min_age
    AND u.created_at > NOW() - INTERVAL '30 days'
""", native=True)
async def find_recent_adults(self, min_age: int) -> List[User]: ...
```

### PostgreSQL-Specific Features

```python
@Query("""
    SELECT * FROM users
    WHERE metadata @> :json_filter::jsonb
""", native=True)
async def find_by_json_metadata(self, json_filter: str) -> List[User]: ...
```

### Complex Native SQL with CTEs

```python
@Query("""
    WITH active_users AS (
        SELECT * FROM users WHERE active = true
    ),
    recent_orders AS (
        SELECT user_id, COUNT(*) as order_count
        FROM orders
        WHERE created_at > :since
        GROUP BY user_id
    )
    SELECT u.*
    FROM active_users u
    JOIN recent_orders ro ON u.id = ro.user_id
    WHERE ro.order_count > :min_orders
""", native=True)
async def find_active_users_with_recent_orders(
    self,
    since: datetime,
    min_orders: int
) -> List[User]: ...
```

## Modifying Queries

Use `@Modifying` for UPDATE and DELETE queries. This is added as an intent-safety mechanism, to explicitly allow `@Query` annotated methods to make potentially destructive modifications. If you attempt to update/delete from a table without `@Modifying`, an exception will be raised. 

These automatically commit and return the number of affected rows.

### Update Query

```python
from mitsuki import Query, Modifying

@Modifying
@Query("""
    UPDATE User u
    SET u.last_login = :timestamp
    WHERE u.id = :user_id
""")
async def update_last_login(self, user_id: int, timestamp: datetime) -> int: ...
```

### Bulk Update

```python
@Modifying
@Query("""
    UPDATE User u
    SET u.active = :status
    WHERE u.age > :age
""")
async def deactivate_old_users(self, age: int, status: bool) -> int: ...
```

### Delete Query

```python
@Modifying
@Query("""
    DELETE FROM User u
    WHERE u.last_login < :cutoff_date
""")
async def delete_inactive_users(self, cutoff_date: datetime) -> int: ...
```

### Native Modifying Query

```python
@Modifying
@Query("""
    UPDATE users
    SET status = 'archived',
        archived_at = CURRENT_TIMESTAMP
    WHERE last_login < :cutoff
    RETURNING id
""", native=True)
async def archive_inactive_users(self, cutoff: datetime) -> int: ...
```

## Custom SQLAlchemy Core Queries

For maximum flexibility and control, you can write custom queries using SQLAlchemy Core directly. This is ideal when:
- You need complex JOINs with aggregations
- The `@Query` decorator syntax becomes cumbersome
- You prefer SQLAlchemy's query builder API
- You need dynamic query construction

### Two Approaches to Custom Queries

**Approach 1: Use `@Query` decorator**
- Declarative, string-based SQL
- Supports ORM-style syntax and native SQL
- Automatic parameter binding and pagination
- Good for queries that don't change structure

**Approach 2: Use `get_connection()` with SQLAlchemy Core** (For advanced cases)
- Programmatic query building with SQLAlchemy Core API
- Full access to SQLAlchemy features
- Better for dynamic queries that change based on conditions
- Ideal for complex JOINs and aggregations

### Using get_connection()

Every repository provides `get_connection()` for direct SQLAlchemy Core access. It returns a context manager that automatically closes the connection when done:

```python
from sqlalchemy import select, func
from mitsuki import CrudRepository
from mitsuki.data.repository import get_database_adapter

@CrudRepository(entity=User)
class UserRepository:
    async def find_users_with_post_stats(self, min_posts: int = 0):
        """Complex query with JOINs and aggregations."""
        # Get connection using context manager (auto-closes)
        async with self.get_connection() as conn:
            adapter = get_database_adapter()

            # Get table objects
            user_table = adapter.get_table(User)
            post_table = adapter.get_table(Post)

            # Build query with SQLAlchemy Core
            query = (
                select(
                    user_table.c.id,
                    user_table.c.username,
                    func.count(post_table.c.id).label('post_count')
                )
                .select_from(user_table)
                .outerjoin(post_table, user_table.c.id == post_table.c.author_id)
                .where(user_table.c.active == True)
                .group_by(user_table.c.id, user_table.c.username)
                .having(func.count(post_table.c.id) >= min_posts)
            )

            result = await conn.execute(query)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
```

### Using text() for Raw SQL

For database-specific SQL, you can also use `text()`:

```python
from sqlalchemy import text

@CrudRepository(entity=Post)
class PostRepository:
    async def get_tag_analytics(self, post_id: int):
        """Raw SQL for complex analytics."""
        async with self.get_connection() as conn:
            query = text("""
                SELECT t.id, t.name, COUNT(pt.post_id) as usage_count
                FROM tag t
                LEFT JOIN post_tag pt ON t.id = pt.tag_id
                WHERE t.id IN (
                    SELECT tag_id FROM post_tag WHERE post_id = :post_id
                )
                GROUP BY t.id, t.name
            """)

            result = await conn.execute(query, {'post_id': post_id})
            return [dict(row._mapping) for row in result.fetchall()]
```

### Dynamic Query Building

Build queries conditionally:

```python
async def search_users(self, username=None, email=None, active=None):
    """Dynamic query based on provided filters."""
    async with self.get_connection() as conn:
        adapter = get_database_adapter()
        user_table = adapter.get_table(User)

        query = select(user_table)
        conditions = []

        if username:
            conditions.append(user_table.c.username.like(f'%{username}%'))
        if email:
            conditions.append(user_table.c.email == email)
        if active is not None:
            conditions.append(user_table.c.active == active)

        if conditions:
            from sqlalchemy import and_
            query = query.where(and_(*conditions))

        result = await conn.execute(query)
        return [User(**dict(row._mapping)) for row in result.fetchall()]
```

### Connection Management

- **Context Manager**: Use `async with self.get_connection() as conn:` for automatic cleanup, otherwise connections aren't released
- **Auto-closed**: Connections are automatically closed when exiting the context
- **Pooled**: Uses connection pooling for efficiency

## Query Logging

To see echos from the SQLAlchemy engine, particularly useful for debugging purposes, you can enable database logging and query logging.

### Configuration

In `application.yml`:

```yaml
logging:
  level: INFO
  sqlalchemy: true  # Enable SQLAlchemy query logging

database:
  echo: true  # Echo all SQL statements
```

### Example Output

When you call a repository method:

```python
user = await user_repo.find_by_email("alice@example.com")
```

Mitsuki will log:

```
SELECT
  users.id AS id,
  users.name AS name,
  users.email AS email,
  users.age AS age,
  users.active AS active,
  users.created_at AS created_at
FROM users
WHERE users.email = ?
['alice@example.com']
```

## Complete @Query Example

```python
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from mitsuki import (
    Entity, CrudRepository, Id, Column,
    Query, Modifying
)

@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True)
    age: int = 0
    active: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime = Field(update_on_create=True)

@CrudRepository(entity=User)
class UserRepository:
    # Built-in CRUD
    # async def save(self, user: User) -> User: ...
    # async def find_by_id(self, id: int) -> Optional[User]: ...
    # async def find_all(self) -> List[User]: ...
    # async def delete(self, user: User) -> bool: ...
    # async def count(self) -> int: ...

    # Query DSL
    async def find_by_email(self, email: str) -> Optional[User]: ...
    async def find_by_active(self, active: bool) -> List[User]: ...
    async def count_by_active(self, active: bool) -> int: ...

    # Custom ORM queries
    @Query("""
        SELECT u FROM User u
        WHERE u.age BETWEEN :min_age AND :max_age
        AND u.active = true
        ORDER BY u.created_at DESC
    """)
    async def find_active_in_age_range(
        self, min_age: int, max_age: int
    ) -> List[User]: ...

    # Native SQL for performance
    @Query("""
        SELECT * FROM users
        WHERE active = true
        AND last_login > :since
        ORDER BY last_login DESC
        LIMIT :limit
    """, native=True)
    async def find_recently_active(
        self, since: datetime, limit: int
    ) -> List[User]: ...

    # Modifying query
    @Modifying
    @Query("""
        UPDATE User u
        SET u.last_login = :timestamp
        WHERE u.id = :user_id
    """)
    async def update_last_login(
        self, user_id: int, timestamp: datetime
    ) -> int: ...

    # Bulk operations
    @Modifying
    @Query("""
        UPDATE User u
        SET u.active = false
        WHERE u.last_login < :cutoff
    """)
    async def deactivate_inactive_users(self, cutoff: datetime) -> int: ...

# Usage
@Service()
class UserService:
    def __init__(self, user_repo: UserRepository):
        self.repo = user_repo

    async def find_active_adults(self):
        return await self.repo.find_active_in_age_range(18, 120)

    async def cleanup_old_users(self):
        cutoff = datetime.now() - timedelta(days=365)
        count = await self.repo.deactivate_inactive_users(cutoff)
        return f"Deactivated {count} users"
```

## See Also

- [Entities and Data Layer](05_data_layer.md)
- [Repositories](06_repositories.md)
- [Configuration](03_configuration.md)

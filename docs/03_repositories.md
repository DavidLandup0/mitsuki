# Repositories & Data Layer

## Table of Contents

- [Overview](#overview)
- [Entities](#entities)
- [CRUD Repositories](#crud-repositories)
- [Query DSL](#query-dsl)
- [Built-in Methods](#built-in-methods)
- [Custom Queries](#custom-queries)
- [Advanced Features](#advanced-features)


## Overview

Mitsuki's data layer provides:
- **Entity mapping** - `@Entity` decorator for domain objects
- **Auto-implemented repositories** - `@CrudRepository` with zero boilerplate
- **Dynamic query DSL** - Parse method names to generate queries
- **Async operations** - All database operations are non-blocking
- **SQLAlchemy adapter** - Supports PostgreSQL, MySQL, SQLite

## Entities

### Basic Entity

```python
from mitsuki import Entity, Id, Column
from dataclasses import dataclass
from datetime import datetime

@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True, default="")
    age: int = 0
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
```

**Requirements:**
- Must be a `@dataclass`
- Must have `@Entity()` decorator
- Must have an `id` field with `Id()`

### Field Types

Mitsuki supports standard Python types:

```python
@Entity()
@dataclass
class Product:
    id: int = Id()
    name: str = ""                    # VARCHAR
    price: float = 0.0                # FLOAT
    quantity: int = 0                 # INTEGER
    available: bool = True            # BOOLEAN
    created_at: datetime = None       # TIMESTAMP
    metadata: dict = None             # JSON (if supported)
```

### UUID Primary Keys

Mitsuki supports UUID primary keys with multiple versions:

```python
import uuid
from mitsuki import Entity, UUID, UUIDv1, UUIDv4, UUIDv5, UUIDv7

# Default: UUID v4 (random)
@Entity()
@dataclass
class User:
    id: uuid.UUID = UUID()
    name: str = ""

# Explicit version
@Entity()
@dataclass
class Product:
    id: uuid.UUID = UUID(version=7)
    name: str = ""

# Convenience aliases
@Entity()
@dataclass
class Event:
    id: uuid.UUID = UUIDv7()  # Time-ordered

@Entity()
@dataclass
class Session:
    id: uuid.UUID = UUIDv1()  # Timestamp + MAC address

@Entity()
@dataclass
class Resource:
    id: uuid.UUID = UUIDv5(namespace=uuid.NAMESPACE_DNS)  # Deterministic
```

**Supported UUID versions:**
- **v1**: Timestamp + MAC address (legacy, privacy concerns)
- **v4**: Random UUIDs (most common, default)
- **v5**: Namespace + name hashing with SHA-1 (deterministic)
- **v7**: Time-ordered UUIDs (best for database performance and pagination)

**Features:**
- UUIDs auto-generated on entity creation
- **Database-optimized storage:**
  - PostgreSQL: Native `UUID` type (16 bytes, indexed efficiently)
  - MySQL/SQLite: `CHAR(36)` (string format)
- Automatic conversion between UUID objects and strings
- No auto-increment needed

**When to use UUIDs:**
- Distributed systems (avoid ID conflicts)
- Public-facing IDs (hide sequential patterns)
- Merging databases
- Time-ordered inserts (use v7 for better index performance)

### Field Constraints

Use `Column()` to specify constraints:

```python
from mitsuki import Column

@Entity()
@dataclass
class User:
    id: int = Id()
    # Unique constraint
    email: str = Column(unique=True, default="")
    # Not null
    name: str = Column(nullable=False, default="")
    # Max length
    bio: str = Column(max_length=500, default="")
    # Index
    username: str = Column(index=True, default="")
    # Combination
    ssn: str = Column(unique=True, nullable=False, default="")
```

**Available constraints:**
- `unique`: Creates unique constraint
- `nullable`: Allows NULL values (default: True)
- `default`: Default value
- `max_length`: Maximum length for strings
- `index`: Creates database index

## CRUD Repositories

### Creating a Repository

```python
from mitsuki import CrudRepository

@CrudRepository(entity=User)
class UserRepository:
    """All CRUD methods are auto-implemented"""
    pass
```

That's it! The repository is fully functional with all CRUD operations.

### Dependency Injection

Repositories are automatically registered as components:

```python
from mitsuki import Service

@Service()
class UserService:
    def __init__(self, user_repo: UserRepository):
        # UserRepository is injected automatically
        self.repo = user_repo

    async def get_all_users(self):
        return await self.repo.find_all()
```

## Built-in Methods

Every `@CrudRepository` automatically implements these methods:

### save()

Create or update an entity.

```python
user = User(id=0, name="Alice", email="alice@example.com")
saved_user = await repo.save(user)
print(saved_user.id)  # Auto-generated ID
```

**Behavior:**
- If `id` is 0 or None, creates new entity
- If `id` exists, updates existing entity
- Returns the saved entity with generated I

### find_by_id()

Find a single entity by ID.

```python
user = await repo.find_by_id(1)
if user:
    print(user.name)
else:
    print("Not found")
```

**Returns:**
- `Entity` if found
- `None` if not found

### find_all()

Retrieve all entities with pagination and sorting.

```python
# Get all users (returns ALL entities without pagination)
users = await repo.find_all()

# Pagination (both page and size required)
users = await repo.find_all(page=0, size=10)  # First 10
users = await repo.find_all(page=1, size=10)  # Next 10

# Sorting
users = await repo.find_all(sort_by="name")  # Ascending
users = await repo.find_all(sort_by="name", sort_desc=True)  # Descending

# Combined
users = await repo.find_all(
    page=2,
    size=20,
    sort_by="created_at",
    sort_desc=True
)
```

**Parameters:**
- `page` (int, optional): Page number (0-indexed). Required for pagination.
- `size` (int, optional): Page size. Required for pagination.
- `sort_by` (str, optional): Field name to sort by
- `sort_desc` (bool, default=False): Sort descending

**Note:** If `page` and `size` are not provided, returns all entities without pagination.

### delete()

Delete an entity.

```python
user = await repo.find_by_id(1)
await repo.delete(user)
```

### delete_by_id()

Delete by ID directly.

```python
await repo.delete_by_id(1)
```

### count()

Count all entities.

```python
total = await repo.count()
print(f"Total users: {total}")
```

### exists_by_id()

Check if entity exists.

```python
exists = await repo.exists_by_id(1)
if exists:
    print("User exists")
```

## Query DSL

The dynamic query DSL parses method names to generate database queries automatically.

### Basic Queries

#### find_by_{field}

Find entities by a single field:

```python
@CrudRepository(entity=User)
class UserRepository:
    # Find single user by email
    async def find_by_email(self, email: str) -> Optional[User]: ...

    # Find all users with given name
    async def find_by_name(self, name: str) -> List[User]: ...

    # Find by boolean field
    async def find_by_active(self, active: bool) -> List[User]: ...
```

**Usage:**
```python
user = await repo.find_by_email("alice@example.com")
active_users = await repo.find_by_active(True)
```

### Comparison Operators

#### Greater Than

```python
async def find_by_age_greater_than(self, age: int) -> List[User]: ...

users = await repo.find_by_age_greater_than(18)  # age > 18
```

#### Less Than

```python
async def find_by_age_less_than(self, age: int) -> List[User]: ...

users = await repo.find_by_age_less_than(65)  # age < 65
```

#### Greater Than or Equal

```python
async def find_by_age_greater_than_equal(self, age: int) -> List[User]: ...

users = await repo.find_by_age_greater_than_equal(21)  # age >= 21
```

#### Less Than or Equal

```python
async def find_by_age_less_than_equal(self, age: int) -> List[User]: ...

users = await repo.find_by_age_less_than_equal(100)  # age <= 100
```

### Count Queries

#### count_by_{field}

Count entities matching criteria:

```python
async def count_by_active(self, active: bool) -> int: ...

total_active = await repo.count_by_active(True)
```

#### count_by_{field}_{operator}

```python
async def count_by_age_greater_than(self, age: int) -> int: ...

adults = await repo.count_by_age_greater_than(18)
```

### Exists Queries

#### exists_by_{field}

Check if any entities match criteria:

```python
async def exists_by_email(self, email: str) -> bool: ...

if await repo.exists_by_email("test@example.com"):
    print("Email already taken")
```

### Complex Queries

#### Multiple Fields (AND)

```python
async def find_by_name_and_age(self, name: str, age: int) -> List[User]: ...

users = await repo.find_by_name_and_age("Alice", 30)
# WHERE name = 'Alice' AND age = 30
```

#### Multiple Conditions

```python
async def find_by_active_and_age_greater_than(
    self,
    active: bool,
    age: int
) -> List[User]: ...

users = await repo.find_by_active_and_age_greater_than(True, 21)
# WHERE active = true AND age > 21
```

### Supported Operators

| Operator              | DSL Syntax                 | SQL            |
|-----------------------|----------------------------|----------------|
| Equals                | `find_by_field`            | `field = ?`    |
| Greater Than          | `field_greater_than`       | `field > ?`    |
| Less Than             | `field_less_than`          | `field < ?`    |
| Greater Than or Equal | `field_greater_than_equal` | `field >= ?`   |
| Less Than or Equal    | `field_less_than_equal`    | `field <= ?`   |
| Like (Pattern)        | `field_like`               | `field LIKE ?` |
| In                    | `field_in`                 | `field IN (?)` |
| Not In                | `field_not_in`             | `field NOT IN (?)` |
| Is Null               | `field_is_null`            | `field IS NULL`|
| Is Not Null           | `field_is_not_null`        | `field IS NOT NULL` |

**Coming soon:**
- `field_not` - NOT equals (!=)
- `field_between` - Range queries
- `order_by` - Sorting in method name (use find_all(sort_by) instead)

## Custom Queries

When the query DSL doesn't support your query, you have several options:

### 1. Use @Query Decorator

For complex queries, use the `@Query` decorator with SQLAlchemy ORM syntax:

```python
from mitsuki import CrudRepository, Query

@CrudRepository(entity=User)
class UserRepository:
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

### 2. Native SQL Queries

Use `@Query(native=True)` for raw SQL:

```python
@Query("""
    SELECT * FROM users
    WHERE age > :age
    ORDER BY created_at DESC
    LIMIT :limit
""", native=True)
async def find_recent_adults(self, age: int, limit: int) -> List[User]: ...
```

### 3. SQLAlchemy Core Queries

For full control, use `get_connection()` with SQLAlchemy Core:

```python
@CrudRepository(entity=User)
class UserRepository:
    async def find_complex_query(self, params: dict) -> List[User]:
        from sqlalchemy import select
        from mitsuki.data import get_database_adapter

        adapter = get_database_adapter()
        user_table = adapter.get_table(User)

        async with self.get_connection() as conn:
            query = select(user_table).where(user_table.c.age > params['min_age'])
            result = await conn.execute(query)
            rows = result.fetchall()
            return [User(**dict(row._mapping)) for row in rows]
```

**See:** [Database Queries Guide](./08_database_queries.md) for complete documentation on `@Query`, `@Modifying`, pagination, and advanced query patterns.


## End-to-End Example

This is a complete, copy-pastable example that demonstrates entities, repositories, services, and controllers working together.

**Create `application.yml`:**
```yaml
database:
  url: sqlite:///app.db
```

**Create `app.py`:**
```python
from mitsuki import Application, Entity, Id, Column, CrudRepository, Service, RestController
from mitsuki import GetMapping, PostMapping
from dataclasses import dataclass
from typing import List, Optional

# Entity
@Entity()
@dataclass
class User:
    id: int = Id()
    name: str = ""
    email: str = Column(unique=True, default="")
    age: int = 0
    active: bool = True

# Repository with DSL queries
@CrudRepository(entity=User)
class UserRepository:
    # Basic queries
    async def find_by_email(self, email: str) -> Optional[User]: ...
    async def find_by_active(self, active: bool) -> List[User]: ...

    # Comparison queries
    async def find_by_age_greater_than(self, age: int) -> List[User]: ...

    # Count queries
    async def count_by_active(self, active: bool) -> int: ...

    # Complex queries
    async def find_by_active_and_age_greater_than(
        self,
        active: bool,
        age: int
    ) -> List[User]: ...

# Service
@Service()
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_all_users(self) -> List[User]:
        return await self.repo.find_all()

    async def get_active_adults(self) -> List[User]:
        return await self.repo.find_by_active_and_age_greater_than(True, 18)

    async def create_user(self, name: str, email: str, age: int) -> User:
        user = User(id=0, name=name, email=email, age=age)
        return await self.repo.save(user)

    async def get_statistics(self) -> dict:
        total = await self.repo.count()
        active = await self.repo.count_by_active(True)
        inactive = await self.repo.count_by_active(False)
        return {"total": total, "active": active, "inactive": inactive}

# Controller
@RestController("/api/users")
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @GetMapping("")
    async def list_users(self) -> List[dict]:
        users = await self.service.get_all_users()
        return [self._to_dict(u) for u in users]

    @GetMapping("/adults")
    async def get_adults(self) -> List[dict]:
        users = await self.service.get_active_adults()
        return [self._to_dict(u) for u in users]

    @GetMapping("/stats")
    async def get_stats(self) -> dict:
        return await self.service.get_statistics()

    @PostMapping("")
    async def create_user(self, body: dict) -> dict:
        user = await self.service.create_user(
            name=body["name"],
            email=body["email"],
            age=body["age"]
        )
        return self._to_dict(user)

    def _to_dict(self, user: User) -> dict:
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "age": user.age,
            "active": user.active
        }

@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()
```

**Run it:**
```bash
python app.py
```

**Test it:**
```bash
# Create a user
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "age": 25}'

# Get all users
curl http://localhost:8000/api/users

# Get statistics
curl http://localhost:8000/api/users/stats
```


**See also:** [Database Configuration Guide](./17_database.md) for connection pooling, environment-specific setup, and advanced options.

## Best Practices

1. **Use the DSL when sensible** - Auto-implemented queries are tested
2. **Keep entities simple** - Just data, no business logic
3. **Repository per entity** - One repository manages one entity type
4. **Services orchestrate** - Complex operations belong in services, not repositories
5. **Name methods clearly** - DSL method names are self-documenting

## Next Steps

- [Decorators](./02_decorators.md) - Complete decorator reference
- [Controllers](./04_controllers.md) - Web layer integration
- [Overview](./01_overview.md) - Architecture and design

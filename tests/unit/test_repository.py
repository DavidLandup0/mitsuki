"""
Unit tests for @CrudRepository and database operations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List

import pytest
import pytest_asyncio

from mitsuki.data import (
    CrudRepository,
    Entity,
    Field,
    Id,
    SQLAlchemyAdapter,
    UUIDv7,
    get_entity_metadata,
    set_database_adapter,
)


@pytest_asyncio.fixture
async def setup_database():
    """Setup in-memory SQLite database for tests."""
    # Create adapter - entities are registered at module load time
    adapter = SQLAlchemyAdapter()
    # SQLite automatically disables pooling in the adapter
    await adapter.connect("sqlite+aiosqlite:///:memory:")
    set_database_adapter(adapter)

    yield adapter

    # Cleanup
    await adapter.disconnect()
    set_database_adapter(None)


@Entity()
@dataclass
class User:
    """Test entity for repository tests."""

    id: int = Id()
    name: str = ""
    email: str = ""
    age: int = 0
    active: bool = True
    created_at: datetime = Field(update_on_create=True)


@Entity()
@dataclass
class Product:
    """Test entity with UUID primary key."""

    id: uuid.UUID = UUIDv7()
    name: str = ""
    price: float = 0.0
    created_at: datetime = Field(update_on_create=True)
    updated_at: datetime = Field(update_on_save=True)


@CrudRepository(entity=User)
class UserRepository:
    """
    Test repository for User.
    All CRUD methods are auto-implemented by @CrudRepository.
    """

    pass


@CrudRepository(entity=Product)
class ProductRepository:
    """
    Test repository for Product.
    All CRUD methods are auto-implemented by @CrudRepository.
    """

    pass


class TestCrudOperations:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_new_entity(self, setup_database):
        """Should save a new entity and generate ID."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()
        user = User(name="Alice", email="alice@example.com", age=25)

        saved = await repo.save(user)
        assert saved.id is not None
        assert saved.name == "Alice"
        assert saved.created_at is not None

    @pytest.mark.asyncio
    async def test_save_update_entity(self, setup_database):
        """Should update an existing entity."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create
        user = User(name="Bob", email="bob@example.com")
        saved = await repo.save(user)
        original_id = saved.id

        # Update
        saved.name = "Robert"
        updated = await repo.save(saved)

        assert updated.id == original_id
        assert updated.name == "Robert"

    @pytest.mark.asyncio
    async def test_find_by_id(self, setup_database):
        """Should find entity by ID."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        user = User(name="Charlie", email="charlie@example.com")
        saved = await repo.save(user)

        found = await repo.find_by_id(saved.id)
        assert found is not None
        assert found.name == "Charlie"
        assert found.email == "charlie@example.com"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, setup_database):
        """Should return None when entity not found."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()
        found = await repo.find_by_id(99999)
        assert found is None

    @pytest.mark.asyncio
    async def test_find_all(self, setup_database):
        """Should find all entities."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create multiple users
        await repo.save(User(name="User1", email="user1@example.com"))
        await repo.save(User(name="User2", email="user2@example.com"))
        await repo.save(User(name="User3", email="user3@example.com"))

        all_users = await repo.find_all()
        assert len(all_users) == 3

    @pytest.mark.asyncio
    async def test_find_all_with_pagination(self, setup_database):
        """Should support pagination."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        # Create 5 users
        for i in range(5):
            await repo.save(User(name=f"User{i}", email=f"user{i}@example.com"))

        # Get first page
        page1 = await repo.find_all(page=0, size=2)
        assert len(page1) == 2

        # Get second page
        page2 = await repo.find_all(page=1, size=2)
        assert len(page2) == 2

    @pytest.mark.asyncio
    async def test_delete_by_id(self, setup_database):
        """Should delete entity by ID."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        user = User(name="ToDelete", email="delete@example.com")
        saved = await repo.save(user)

        deleted = await repo.delete_by_id(saved.id)
        assert deleted is True

        found = await repo.find_by_id(saved.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_entity(self, setup_database):
        """Should delete entity instance."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        user = User(name="ToDelete", email="delete@example.com")
        saved = await repo.save(user)

        deleted = await repo.delete(saved)
        assert deleted is True

        found = await repo.find_by_id(saved.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_count(self, setup_database):
        """Should count entities."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        await repo.save(User(name="User1", email="user1@example.com"))
        await repo.save(User(name="User2", email="user2@example.com"))

        count = await repo.count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_exists_by_id(self, setup_database):
        """Should check if entity exists."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        repo = UserRepository()

        user = User(name="Exists", email="exists@example.com")
        saved = await repo.save(user)

        exists = await repo.exists_by_id(saved.id)
        assert exists is True

        not_exists = await repo.exists_by_id(99999)
        assert not_exists is False


class TestQueryDSL:
    """Tests for query DSL method parsing."""

    @pytest.mark.asyncio
    async def test_find_by_single_field(self, setup_database):
        """Should support find_by_field queries."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        @CrudRepository(entity=User)
        class UserRepo:
            async def find_by_name(self, name: str) -> List[User]:
                pass

        repo = UserRepo()

        await repo.save(User(name="Alice", email="alice@example.com"))
        await repo.save(User(name="Bob", email="bob@example.com"))

        results = await repo.find_by_name("Alice")
        assert len(results) == 1
        assert results[0].name == "Alice"

    @pytest.mark.asyncio
    async def test_find_by_multiple_fields_and(self, setup_database):
        """Should support find_by_field_and_field queries."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        @CrudRepository(entity=User)
        class UserRepo:
            async def find_by_name_and_active(
                self, name: str, active: bool
            ) -> List[User]:
                pass

        repo = UserRepo()

        await repo.save(User(name="Alice", email="alice@example.com", active=True))
        await repo.save(User(name="Alice", email="alice2@example.com", active=False))

        results = await repo.find_by_name_and_active("Alice", True)
        assert len(results) == 1
        assert results[0].active is True

    @pytest.mark.asyncio
    async def test_find_by_greater_than(self, setup_database):
        """Should support greater_than queries."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        @CrudRepository(entity=User)
        class UserRepo:
            async def find_by_age_greater_than(self, age: int) -> List[User]:
                pass

        repo = UserRepo()

        await repo.save(User(name="Young", email="young@example.com", age=20))
        await repo.save(User(name="Old", email="old@example.com", age=50))

        results = await repo.find_by_age_greater_than(30)
        assert len(results) == 1
        assert results[0].name == "Old"

    @pytest.mark.asyncio
    async def test_find_by_less_than(self, setup_database):
        """Should support less_than queries."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        @CrudRepository(entity=User)
        class UserRepo:
            async def find_by_age_less_than(self, age: int) -> List[User]:
                pass

        repo = UserRepo()

        await repo.save(User(name="Young", email="young@example.com", age=20))
        await repo.save(User(name="Old", email="old@example.com", age=50))

        results = await repo.find_by_age_less_than(30)
        assert len(results) == 1
        assert results[0].name == "Young"

    @pytest.mark.asyncio
    async def test_count_by_field(self, setup_database):
        """Should support count_by_field queries."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(User))

        @CrudRepository(entity=User)
        class UserRepo:
            async def count_by_active(self, active: bool) -> int:
                pass

        repo = UserRepo()

        await repo.save(User(name="User1", email="user1@example.com", active=True))
        await repo.save(User(name="User2", email="user2@example.com", active=True))
        await repo.save(User(name="User3", email="user3@example.com", active=False))

        count = await repo.count_by_active(True)
        assert count == 2


class TestUUIDRepository:
    """Tests for repositories with UUID primary keys."""

    @pytest.mark.asyncio
    async def test_save_with_uuid(self, setup_database):
        """Should save entity with UUID primary key."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(Product))

        repo = ProductRepository()

        product = Product(name="Widget", price=19.99)
        saved = await repo.save(product)

        assert saved.id is not None
        assert isinstance(saved.id, uuid.UUID)
        assert saved.name == "Widget"

    @pytest.mark.asyncio
    async def test_find_by_uuid(self, setup_database):
        """Should find entity by UUID."""
        adapter = setup_database
        await adapter.create_table_if_not_exists(get_entity_metadata(Product))

        repo = ProductRepository()

        product = Product(name="Gadget", price=29.99)
        saved = await repo.save(product)

        found = await repo.find_by_id(saved.id)
        assert found is not None
        assert found.name == "Gadget"
        assert found.id == saved.id

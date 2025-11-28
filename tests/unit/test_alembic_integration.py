"""
Unit tests for Alembic integration features.

Tests cover:
- Entity metadata attribute exposure
- SQLAlchemy metadata retrieval
- Async URL conversion
- Profile-based configuration resolution
"""

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from sqlalchemy import MetaData

import mitsuki.data.repository as repo_module
from mitsuki.data import Entity, convert_to_async_url, get_sqlalchemy_metadata
from mitsuki.data.adapters.sqlalchemy import SQLAlchemyAdapter
from mitsuki.data.entity import (
    _entity_registry,
    clear_entity_registry,
    get_all_entities,
)
from mitsuki.data.repository import set_database_adapter
from mitsuki.data.types import UUIDv7


@pytest.fixture(autouse=True)
def preserve_entity_registry():
    """Preserve entity registry across tests that clear it."""
    saved_registry = get_all_entities()
    saved_adapter = repo_module._database_adapter
    yield
    _entity_registry.clear()
    _entity_registry.update(saved_registry)
    repo_module._database_adapter = saved_adapter


class TestConvertToAsyncUrl:
    """Test convert_to_async_url() helper function."""

    def test_postgresql_conversion(self):
        """Test PostgreSQL URL is converted to asyncpg."""
        url = "postgresql://user:pass@localhost/mydb"
        result = convert_to_async_url(url)
        assert result == "postgresql+asyncpg://user:pass@localhost/mydb"

    def test_mysql_conversion(self):
        """Test MySQL URL is converted to aiomysql."""
        url = "mysql://user:pass@localhost/mydb"
        result = convert_to_async_url(url)
        assert result == "mysql+aiomysql://user:pass@localhost/mydb"

    def test_sqlite_conversion(self):
        """Test SQLite URL is converted to aiosqlite."""
        url = "sqlite:///mydb.db"
        result = convert_to_async_url(url)
        assert result == "sqlite+aiosqlite:///mydb.db"

    def test_sqlite_memory_conversion(self):
        """Test SQLite :memory: URL is converted."""
        url = "sqlite:///:memory:"
        result = convert_to_async_url(url)
        assert result == "sqlite+aiosqlite:///:memory:"

    def test_already_async_postgresql(self):
        """Test already-async PostgreSQL URL is not modified."""
        url = "postgresql+asyncpg://user:pass@localhost/mydb"
        result = convert_to_async_url(url)
        assert result == "postgresql+asyncpg://user:pass@localhost/mydb"

    def test_already_async_mysql(self):
        """Test already-async MySQL URL is not modified."""
        url = "mysql+aiomysql://user:pass@localhost/mydb"
        result = convert_to_async_url(url)
        assert result == "mysql+aiomysql://user:pass@localhost/mydb"

    def test_already_async_sqlite(self):
        """Test already-async SQLite URL is not modified."""
        url = "sqlite+aiosqlite:///mydb.db"
        result = convert_to_async_url(url)
        assert result == "sqlite+aiosqlite:///mydb.db"

    def test_unknown_dialect_unchanged(self):
        """Test unknown dialect is returned unchanged."""
        url = "oracle://user:pass@localhost/mydb"
        result = convert_to_async_url(url)
        assert result == "oracle://user:pass@localhost/mydb"

    def test_empty_string(self):
        """Test empty string is returned unchanged."""
        result = convert_to_async_url("")
        assert result == ""

    def test_postgresql_with_port(self):
        """Test PostgreSQL URL with port is converted correctly."""
        url = "postgresql://user:pass@localhost:5432/mydb"
        result = convert_to_async_url(url)
        assert result == "postgresql+asyncpg://user:pass@localhost:5432/mydb"

    def test_mysql_with_charset(self):
        """Test MySQL URL with query parameters is converted."""
        url = "mysql://user:pass@localhost/mydb?charset=utf8mb4"
        result = convert_to_async_url(url)
        assert result == "mysql+aiomysql://user:pass@localhost/mydb?charset=utf8mb4"

    def test_sqlite_relative_path(self):
        """Test SQLite with relative path is converted."""
        url = "sqlite:///./data/mydb.db"
        result = convert_to_async_url(url)
        assert result == "sqlite+aiosqlite:///./data/mydb.db"


class TestEntityMetadataAttribute:
    """Test that @Entity classes get .metadata attribute for Alembic."""

    def test_metadata_attribute_set_on_table_creation(self):
        """Test that .metadata is set when table is created."""

        @Entity()
        @dataclass
        class TestModel:
            id: int

        adapter = SQLAlchemyAdapter()
        adapter.metadata = MetaData()

        from mitsuki.data.entity import get_entity_metadata

        entity_meta = get_entity_metadata(TestModel)

        # Create table, which should attach metadata
        adapter._get_or_create_table(entity_meta)

        # Verify metadata attribute was attached
        assert hasattr(TestModel, "metadata")
        assert isinstance(TestModel.metadata, MetaData)
        assert TestModel.metadata is adapter.metadata

    def test_metadata_shared_across_entities(self):
        """Test that all entities share the same MetaData object."""

        @Entity()
        @dataclass
        class Model1:
            id: int

        @Entity()
        @dataclass
        class Model2:
            id: int

        adapter = SQLAlchemyAdapter()
        adapter.metadata = MetaData()

        from mitsuki.data.entity import get_entity_metadata

        adapter._get_or_create_table(get_entity_metadata(Model1))
        adapter._get_or_create_table(get_entity_metadata(Model2))

        # Both should have metadata attribute
        assert hasattr(Model1, "metadata")
        assert hasattr(Model2, "metadata")

        # Should be the same MetaData instance
        assert Model1.metadata is Model2.metadata
        assert Model1.metadata is adapter.metadata


class TestGetSQLAlchemyMetadata:
    """Test get_sqlalchemy_metadata() helper function."""

    def test_returns_adapter_metadata(self):
        """Test that function returns the adapter's MetaData."""
        adapter = SQLAlchemyAdapter()
        set_database_adapter(adapter)

        result = get_sqlalchemy_metadata()

        assert isinstance(result, MetaData)
        assert result is adapter.metadata

    def test_fails_with_wrong_adapter_type(self):
        """Test that function fails if adapter is not SQLAlchemy."""
        mock_adapter = MagicMock()
        mock_adapter.__class__.__name__ = "OtherAdapter"
        set_database_adapter(mock_adapter)

        with pytest.raises(ValueError) as exc_info:
            get_sqlalchemy_metadata()

        assert "not SQLAlchemy" in str(exc_info.value)
        assert "OtherAdapter" in str(exc_info.value)

    def test_auto_initializes_without_adapter(self):
        """Test that function auto-initializes if no adapter set."""
        clear_entity_registry()
        repo_module._database_adapter = None

        @Entity()
        @dataclass
        class AutoInitModel:
            id: int

        metadata = get_sqlalchemy_metadata()

        assert isinstance(metadata, MetaData)
        assert len(metadata.tables) == 1

        clear_entity_registry()
        repo_module._database_adapter = None


class TestAlembicProfileResolution:
    """Test profile-based configuration resolution for Alembic."""

    def test_profile_validation_fails_on_missing_file(self, tmp_path):
        """Test that missing profile config file raises helpful error."""
        import yaml

        # Create only base config
        base_config = tmp_path / "application.yml"
        base_config.write_text(yaml.dump({"database": {"url": "sqlite:///app.db"}}))

        # Simulate the get_url() function from env.py template
        def get_url():
            profile = "nonexistent"
            if profile:
                config_file = tmp_path / f"application-{profile}.yml"
                if not config_file.exists():
                    raise FileNotFoundError(
                        f"Configuration file '{config_file.name}' not found for MITSUKI_PROFILE='{profile}'. "
                        f"Available profiles: dev, stg, prod (or unset MITSUKI_PROFILE to use application.yml)"
                    )
            else:
                config_file = base_config

            with open(config_file) as f:
                app_config = yaml.safe_load(f)
            return app_config["database"]["url"]

        with pytest.raises(FileNotFoundError) as exc_info:
            get_url()

        error_msg = str(exc_info.value)
        assert "application-nonexistent.yml" in error_msg
        assert "MITSUKI_PROFILE='nonexistent'" in error_msg
        assert "Available profiles" in error_msg

    def test_profile_resolution_with_valid_profile(self, tmp_path):
        """Test that valid profile loads correct config file."""
        import yaml

        # Create base and dev configs
        base_config = tmp_path / "application.yml"
        base_config.write_text(yaml.dump({"database": {"url": "sqlite:///app.db"}}))

        dev_config = tmp_path / "application-dev.yml"
        dev_config.write_text(yaml.dump({"database": {"url": "sqlite:///dev.db"}}))

        # Simulate get_url() with dev profile
        def get_url(profile=""):
            if profile:
                config_file = tmp_path / f"application-{profile}.yml"
                if not config_file.exists():
                    raise FileNotFoundError(f"Config not found")
            else:
                config_file = base_config

            with open(config_file) as f:
                app_config = yaml.safe_load(f)
            return app_config["database"]["url"]

        # Test base config
        assert get_url() == "sqlite:///app.db"

        # Test dev profile
        assert get_url("dev") == "sqlite:///dev.db"

    def test_profile_resolution_fallback_to_base(self, tmp_path):
        """Test that empty profile uses base config."""
        import yaml

        base_config = tmp_path / "application.yml"
        base_config.write_text(yaml.dump({"database": {"url": "sqlite:///app.db"}}))

        def get_url(profile=""):
            if profile:
                config_file = tmp_path / f"application-{profile}.yml"
            else:
                config_file = base_config

            with open(config_file) as f:
                app_config = yaml.safe_load(f)
            return app_config["database"]["url"]

        # Empty profile should use base
        assert get_url("") == "sqlite:///app.db"
        assert get_url() == "sqlite:///app.db"


class TestAlembicMetadataGeneration:
    """Test that metadata generation works correctly for Alembic autogenerate."""

    def test_uuid_field_creates_guid_type(self):
        """Test that UUID fields use GUID type in metadata."""
        import uuid

        @Entity()
        @dataclass
        class UUIDModel:
            id: uuid.UUID = UUIDv7()

        adapter = SQLAlchemyAdapter()
        adapter.metadata = MetaData()

        from mitsuki.data.entity import get_entity_metadata

        entity_meta = get_entity_metadata(UUIDModel)

        table = adapter._get_or_create_table(entity_meta)

        # Check that id column uses GUID type
        id_column = table.c.id
        assert id_column.type.__class__.__name__ == "GUID"

    def test_metadata_contains_table_definitions(self):
        """Test that MetaData contains table definitions after creation."""

        @Entity()
        @dataclass
        class TableModel:
            id: int

        adapter = SQLAlchemyAdapter()
        adapter.metadata = MetaData()

        from mitsuki.data.entity import get_entity_metadata

        entity_meta = get_entity_metadata(TableModel)

        # Initially no tables
        assert len(adapter.metadata.tables) == 0

        # Create table
        adapter._get_or_create_table(entity_meta)

        # Now should have table
        assert len(adapter.metadata.tables) == 1
        assert "table_models" in adapter.metadata.tables

    def test_multiple_entities_in_same_metadata(self):
        """Test that multiple entities are tracked in the same MetaData."""

        @Entity()
        @dataclass
        class Entity1:
            id: int

        @Entity()
        @dataclass
        class Entity2:
            id: int

        adapter = SQLAlchemyAdapter()
        adapter.metadata = MetaData()

        from mitsuki.data.entity import get_entity_metadata

        adapter._get_or_create_table(get_entity_metadata(Entity1))
        adapter._get_or_create_table(get_entity_metadata(Entity2))

        # Both tables should be in metadata
        assert len(adapter.metadata.tables) == 2
        table_names = list(adapter.metadata.tables.keys())
        assert "entity1s" in table_names  # pluralized
        assert "entity2s" in table_names  # pluralized

    def test_get_sqlalchemy_metadata_without_app_initialization(self):
        """Test that get_sqlalchemy_metadata() works without running the app."""
        clear_entity_registry()
        repo_module._database_adapter = None

        @Entity()
        @dataclass
        class StandaloneModel:
            id: uuid.UUID = UUIDv7()

        metadata = get_sqlalchemy_metadata()

        assert isinstance(metadata, MetaData)
        assert len(metadata.tables) == 1
        assert "standalone_models" in metadata.tables

        table = metadata.tables["standalone_models"]
        assert table.c.id.type.__class__.__name__ == "GUID"

        clear_entity_registry()
        repo_module._database_adapter = None

    def test_get_sqlalchemy_metadata_with_multiple_entities(self):
        """Test that get_sqlalchemy_metadata() populates all entities."""
        clear_entity_registry()
        repo_module._database_adapter = None

        @Entity()
        @dataclass
        class User:
            id: uuid.UUID = UUIDv7()

        @Entity()
        @dataclass
        class Post:
            id: uuid.UUID = UUIDv7()

        @Entity()
        @dataclass
        class Comment:
            id: uuid.UUID = UUIDv7()

        metadata = get_sqlalchemy_metadata()

        assert len(metadata.tables) == 3
        assert "users" in metadata.tables
        assert "posts" in metadata.tables
        assert "comments" in metadata.tables

        clear_entity_registry()
        repo_module._database_adapter = None

    def test_get_sqlalchemy_metadata_idempotent(self):
        """Test that calling get_sqlalchemy_metadata() multiple times is safe."""
        clear_entity_registry()
        repo_module._database_adapter = None

        @Entity()
        @dataclass
        class IdempotentModel:
            id: uuid.UUID = UUIDv7()

        metadata1 = get_sqlalchemy_metadata()
        metadata2 = get_sqlalchemy_metadata()

        assert metadata1 is metadata2
        assert len(metadata1.tables) == 1

        clear_entity_registry()
        repo_module._database_adapter = None


class TestAlembicURLValidation:
    """Test URL validation and error handling."""

    def test_convert_url_handles_none(self):
        """Test that convert_to_async_url handles edge cases safely."""
        # Should not crash on various inputs
        assert convert_to_async_url("") == ""

    def test_url_conversion_preserves_credentials(self):
        """Test that URL conversion doesn't break credentials."""
        url = "postgresql://user:p@ss:word@localhost:5432/db"
        result = convert_to_async_url(url)
        assert result == "postgresql+asyncpg://user:p@ss:word@localhost:5432/db"
        assert "user:p@ss:word" in result

    def test_url_conversion_preserves_special_characters(self):
        """Test that special characters in URLs are preserved."""
        url = "postgresql://user%40host:pass%23word@localhost/my-db_123"
        result = convert_to_async_url(url)
        assert "user%40host" in result
        assert "pass%23word" in result
        assert "my-db_123" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time

import pytest

from mitsuki import UUID, Column, Entity, Field, Id, UUIDv1, UUIDv4, UUIDv5, UUIDv7
from mitsuki.data.entity import (
    _entity_registry,
    clear_entity_registry,
    get_all_entities,
    get_entity_metadata,
    is_entity,
)
from mitsuki.exceptions import EntityException, UUIDGenerationException


class TestEntityBasics:
    """Test basic @Entity functionality"""

    def setup_method(self):
        """Clear entity registry before each test"""
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()
        _entity_registry.update(self._saved_registry)

    def test_entity_decorator_registers_entity(self):
        """Test that @Entity registers the entity in the registry"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""

        assert is_entity(User)
        meta = get_entity_metadata(User)
        assert meta.entity_class == User

    def test_entity_requires_dataclass(self):
        """Test that @Entity requires the class to be a dataclass"""
        with pytest.raises(EntityException, match="not a dataclass"):

            @Entity()
            class NotADataclass:
                id: int = Id()

    def test_entity_table_name_auto_generated(self):
        """Test that table name is auto-generated from class name"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()

        meta = get_entity_metadata(User)
        assert meta.table_name == "users"  # Pluralized and snake_cased

    def test_entity_table_name_custom(self):
        """Test custom table name"""

        @Entity(table="custom_users")
        @dataclass
        class User:
            id: int = Id()

        meta = get_entity_metadata(User)
        assert meta.table_name == "custom_users"

    def test_entity_table_name_snake_case(self):
        """Test that CamelCase is converted to snake_case"""

        @Entity()
        @dataclass
        class UserProfile:
            id: int = Id()

        meta = get_entity_metadata(UserProfile)
        assert meta.table_name == "user_profiles"

    def test_entity_requires_primary_key(self):
        """Test that entity must have a primary key"""
        with pytest.raises(EntityException, match="must have a primary key"):

            @Entity()
            @dataclass
            class NoPrimaryKey:
                name: str = ""


class TestFieldTypes:
    """Test all supported field types"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_integer_field(self):
        """Test integer field type"""

        @Entity()
        @dataclass
        class Product:
            id: int = Id()
            quantity: int = 0

        meta = get_entity_metadata(Product)
        assert meta.fields["quantity"].python_type == int
        assert meta.fields["quantity"].db_type == "INTEGER"

    def test_string_field(self):
        """Test string field type"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""

        meta = get_entity_metadata(User)
        assert meta.fields["name"].python_type == str
        assert meta.fields["name"].db_type == "VARCHAR(255)"

    def test_float_field(self):
        """Test float field type"""

        @Entity()
        @dataclass
        class Product:
            id: int = Id()
            price: float = 0.0

        meta = get_entity_metadata(Product)
        assert meta.fields["price"].python_type == float
        assert meta.fields["price"].db_type == "FLOAT"

    def test_boolean_field(self):
        """Test boolean field type"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            active: bool = True

        meta = get_entity_metadata(User)
        assert meta.fields["active"].python_type == bool
        assert meta.fields["active"].db_type == "BOOLEAN"

    def test_datetime_field(self):
        """Test datetime field type"""

        @Entity()
        @dataclass
        class Event:
            id: int = Id()
            created_at: datetime = None

        meta = get_entity_metadata(Event)
        assert meta.fields["created_at"].python_type == datetime
        assert meta.fields["created_at"].db_type == "TIMESTAMP"

    def test_date_field(self):
        """Test date field type"""

        @Entity()
        @dataclass
        class Event:
            id: int = Id()
            event_date: date = None

        meta = get_entity_metadata(Event)
        assert meta.fields["event_date"].python_type == date
        assert meta.fields["event_date"].db_type == "DATE"

    def test_time_field(self):
        """Test time field type"""

        @Entity()
        @dataclass
        class Schedule:
            id: int = Id()
            start_time: time = None

        meta = get_entity_metadata(Schedule)
        assert meta.fields["start_time"].python_type == time
        assert meta.fields["start_time"].db_type == "TIME"

    def test_bytes_field(self):
        """Test bytes field type"""

        @Entity()
        @dataclass
        class File:
            id: int = Id()
            content: bytes = b""

        meta = get_entity_metadata(File)
        assert meta.fields["content"].python_type == bytes
        assert meta.fields["content"].db_type == "BLOB"


class TestPrimaryKeyField:
    """Test Id() primary key field"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_id_marker_creates_primary_key(self):
        """Test that Id() marks field as primary key"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""

        meta = get_entity_metadata(User)
        assert meta.primary_key_field == "id"
        pk = meta.get_primary_key()
        assert pk.primary_key is True
        assert pk.auto_increment is True
        assert pk.nullable is False

    def test_id_auto_increment_disabled(self):
        """Test Id() with auto_increment=False"""

        @Entity()
        @dataclass
        class User:
            id: int = Id(auto_increment=False)

        meta = get_entity_metadata(User)
        pk = meta.get_primary_key()
        assert pk.auto_increment is False

    def test_implicit_id_field(self):
        """Test that 'id' field without Id() marker is auto-detected"""

        @Entity()
        @dataclass
        class User:
            id: int = 0
            name: str = ""

        meta = get_entity_metadata(User)
        assert meta.primary_key_field == "id"
        pk = meta.get_primary_key()
        assert pk.primary_key is True


class TestColumnConstraints:
    """Test Column() field constraints"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_unique_constraint(self):
        """Test unique constraint"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            email: str = Column(unique=True, default="")

        meta = get_entity_metadata(User)
        assert meta.fields["email"].unique is True

    def test_nullable_constraint(self):
        """Test nullable constraint"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = Column(nullable=False, default="")

        meta = get_entity_metadata(User)
        assert meta.fields["name"].nullable is False

    def test_default_value(self):
        """Test default value"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            status: str = Column(default="active")

        meta = get_entity_metadata(User)
        assert meta.fields["status"].default == "active"

    def test_custom_db_type(self):
        """Test custom database type"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            bio: str = Column(db_type="TEXT", default="")

        meta = get_entity_metadata(User)
        assert meta.fields["bio"].db_type == "TEXT"

    def test_multiple_constraints(self):
        """Test multiple constraints on single field"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            email: str = Column(unique=True, nullable=False, default="")

        meta = get_entity_metadata(User)
        field = meta.fields["email"]
        assert field.unique is True
        assert field.nullable is False

    def test_index_constraint(self):
        """Test index constraint"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            username: str = Column(index=True, default="")

        meta = get_entity_metadata(User)
        assert meta.fields["username"].index is True

    def test_max_length_constraint(self):
        """Test max_length constraint"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            username: str = Column(max_length=50, default="")

        meta = get_entity_metadata(User)
        assert meta.fields["username"].max_length == 50


class TestUUIDFields:
    """Test UUID field support"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_uuid_default_version(self):
        """Test UUID() with default version (v4)"""

        @Entity()
        @dataclass
        class User:
            id: uuid.UUID = UUID()

        meta = get_entity_metadata(User)
        pk = meta.get_primary_key()
        assert pk.primary_key is True
        assert pk.auto_increment is False
        assert pk.uuid_version == 4
        assert pk.db_type == "UUID"

    def test_uuid_explicit_version(self):
        """Test UUID() with explicit version"""

        @Entity()
        @dataclass
        class Event:
            id: uuid.UUID = UUID(version=7)

        meta = get_entity_metadata(Event)
        pk = meta.get_primary_key()
        assert pk.uuid_version == 7

    def test_uuidv1_alias(self):
        """Test UUIDv1() alias"""

        @Entity()
        @dataclass
        class Event:
            id: uuid.UUID = UUIDv1()

        meta = get_entity_metadata(Event)
        pk = meta.get_primary_key()
        assert pk.uuid_version == 1
        assert pk.primary_key is True
        assert pk.auto_increment is False

    def test_uuidv4_alias(self):
        """Test UUIDv4() alias"""

        @Entity()
        @dataclass
        class User:
            id: uuid.UUID = UUIDv4()

        meta = get_entity_metadata(User)
        pk = meta.get_primary_key()
        assert pk.uuid_version == 4

    def test_uuidv5_alias_with_namespace(self):
        """Test UUIDv5() alias with namespace"""

        @Entity()
        @dataclass
        class Resource:
            id: uuid.UUID = UUIDv5(namespace=uuid.NAMESPACE_DNS)

        meta = get_entity_metadata(Resource)
        pk = meta.get_primary_key()
        assert pk.uuid_version == 5
        assert pk.uuid_namespace == uuid.NAMESPACE_DNS

    def test_uuidv7_alias(self):
        """Test UUIDv7() alias"""

        @Entity()
        @dataclass
        class Event:
            id: uuid.UUID = UUIDv7()

        meta = get_entity_metadata(Event)
        pk = meta.get_primary_key()
        assert pk.uuid_version == 7

    def test_uuid_invalid_version(self):
        """Test that invalid UUID version raises error"""
        with pytest.raises(UUIDGenerationException, match="not supported"):
            UUID(version=2)

        with pytest.raises(UUIDGenerationException, match="not supported"):
            UUID(version=6)

        with pytest.raises(UUIDGenerationException, match="not supported"):
            UUID(version=8)

    def test_uuid_v5_requires_namespace(self):
        """Test that UUIDv5 requires namespace"""
        with pytest.raises(UUIDGenerationException, match="namespace"):
            UUID(version=5)

    def test_uuid_all_namespaces(self):
        """Test all standard UUID namespaces"""
        namespaces = [
            uuid.NAMESPACE_DNS,
            uuid.NAMESPACE_URL,
            uuid.NAMESPACE_OID,
            uuid.NAMESPACE_X500,
        ]

        for ns in namespaces:

            @Entity()
            @dataclass
            class TestEntity:
                id: uuid.UUID = UUIDv5(namespace=ns)

            meta = get_entity_metadata(TestEntity)
            assert meta.get_primary_key().uuid_namespace == ns
            clear_entity_registry()


class TestAutoTimestampFields:
    """Test Field() with auto timestamp support"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_update_on_create(self):
        """Test update_on_create for creation timestamp"""

        @Entity()
        @dataclass
        class Post:
            id: int = Id()
            created_at: datetime = Field(update_on_create=True)

        meta = get_entity_metadata(Post)
        field = meta.fields["created_at"]
        assert field.update_on_create is True
        assert field.update_on_save is False

    def test_update_on_save(self):
        """Test update_on_save for update timestamp"""

        @Entity()
        @dataclass
        class Post:
            id: int = Id()
            updated_at: datetime = Field(update_on_save=True)

        meta = get_entity_metadata(Post)
        field = meta.fields["updated_at"]
        assert field.update_on_save is True
        assert field.update_on_create is False

    def test_both_timestamps(self):
        """Test entity with both created and updated timestamps"""

        @Entity()
        @dataclass
        class Post:
            id: int = Id()
            created_at: datetime = Field(update_on_create=True)
            updated_at: datetime = Field(update_on_save=True)

        meta = get_entity_metadata(Post)
        assert meta.fields["created_at"].update_on_create is True
        assert meta.fields["updated_at"].update_on_save is True


class TestEntityMetadataHelpers:
    """Test EntityMetadata helper methods"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_get_primary_key(self):
        """Test get_primary_key() helper"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()

        meta = get_entity_metadata(User)
        pk = meta.get_primary_key()
        assert pk.name == "id"
        assert pk.primary_key is True

    def test_get_field(self):
        """Test get_field() helper"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""

        meta = get_entity_metadata(User)
        name_field = meta.get_field("name")
        assert name_field.name == "name"
        assert name_field.python_type == str

    def test_get_field_not_found(self):
        """Test get_field() with non-existent field"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()

        meta = get_entity_metadata(User)
        with pytest.raises(UUIDGenerationException, match="not found"):
            meta.get_field("nonexistent")

    def test_get_insertable_fields(self):
        """Test get_insertable_fields() excludes auto-increment primary key"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""
            email: str = ""

        meta = get_entity_metadata(User)
        insertable = meta.get_insertable_fields()

        # Should not include auto-increment primary key
        assert "id" not in insertable
        assert "name" in insertable
        assert "email" in insertable

    def test_get_insertable_fields_with_uuid(self):
        """Test get_insertable_fields() includes UUID primary key"""

        @Entity()
        @dataclass
        class User:
            id: uuid.UUID = UUIDv4()
            name: str = ""

        meta = get_entity_metadata(User)
        insertable = meta.get_insertable_fields()

        assert "id" in insertable
        assert "name" in insertable

    def test_get_updatable_fields(self):
        """Test get_updatable_fields() excludes primary key"""

        @Entity()
        @dataclass
        class User:
            id: int = Id()
            name: str = ""
            email: str = ""

        meta = get_entity_metadata(User)
        updatable = meta.get_updatable_fields()

        # Should not include primary key
        assert "id" not in updatable
        assert "name" in updatable
        assert "email" in updatable


class TestComplexEntity:
    """Test complex entity with multiple field types and constraints"""

    def setup_method(self):
        self._saved_registry = get_all_entities()
        clear_entity_registry()

    def teardown_method(self):
        """Restore entity registry after each test"""
        clear_entity_registry()

        _entity_registry.update(self._saved_registry)

    def test_complex_entity_all_features(self):
        """Test entity with all field types and features"""

        @Entity()
        @dataclass
        class Article:
            id: uuid.UUID = UUIDv7()
            title: str = Column(nullable=False, default="")
            slug: str = Column(unique=True, default="")
            content: str = Column(db_type="TEXT", default="")
            view_count: int = 0
            rating: float = 0.0
            published: bool = False
            published_at: datetime = None
            created_at: datetime = Field(update_on_create=True)
            updated_at: datetime = Field(update_on_save=True)

        meta = get_entity_metadata(Article)

        # Check table name
        assert meta.table_name == "articles"

        # Check primary key
        pk = meta.get_primary_key()
        assert pk.name == "id"
        assert pk.uuid_version == 7

        # Check constraints
        assert meta.fields["title"].nullable is False
        assert meta.fields["slug"].unique is True
        assert meta.fields["content"].db_type == "TEXT"

        # Check types
        assert meta.fields["view_count"].python_type == int
        assert meta.fields["rating"].python_type == float
        assert meta.fields["published"].python_type == bool

        # Check timestamps
        assert meta.fields["created_at"].update_on_create is True
        assert meta.fields["updated_at"].update_on_save is True

        # Check field count
        assert len(meta.fields) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

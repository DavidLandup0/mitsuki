"""
Tests for public methods that no framework code path calls.
"""

import io
from dataclasses import dataclass

import pytest

from mitsuki.data import (
    ComparisonOperator,
    Entity,
    Id,
    QueryCondition,
    QueryObject,
    SQLAlchemyAdapter,
    get_entity_metadata,
)
from mitsuki.data.query import LogicalOperator, QueryOperation
from mitsuki.exceptions import DatabaseNotConnectedException
from mitsuki.web.upload import UploadFile


@Entity()
@dataclass
class Gadget:
    id: int = Id()
    name: str = ""


class TestTableExists:
    @pytest.mark.asyncio
    async def test_reports_created_and_missing_tables(self):
        adapter = SQLAlchemyAdapter()
        await adapter.connect("sqlite+aiosqlite:///:memory:")
        table_name = get_entity_metadata(Gadget).table_name
        try:
            assert await adapter.table_exists(table_name) is False

            await adapter.create_table_if_not_exists(get_entity_metadata(Gadget))

            assert await adapter.table_exists(table_name) is True
            assert await adapter.table_exists("no_such_table") is False
        finally:
            await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_requires_a_connection(self):
        with pytest.raises(DatabaseNotConnectedException):
            await SQLAlchemyAdapter().table_exists("gadgets")


class TestQueryRepr:
    def test_condition_with_value(self):
        condition = QueryCondition("name", ComparisonOperator.EQUALS, "Alice")

        assert repr(condition) == "name = 'Alice'"

    def test_null_check_condition_omits_value(self):
        condition = QueryCondition("name", ComparisonOperator.IS_NULL)

        assert repr(condition) == "name IS NULL"

    def test_bare_query(self):
        assert repr(QueryObject(entity_type=Gadget)) == "Query(select from Gadget)"

    def test_full_query(self):
        query = (
            QueryObject(
                entity_type=Gadget,
                operation=QueryOperation.COUNT,
                logical_operator=LogicalOperator.OR,
            )
            .add_condition("id", ComparisonOperator.GREATER_THAN, 3)
            .add_condition("name", ComparisonOperator.IS_NOT_NULL)
            .with_order("name", descending=True)
            .with_pagination(limit=10, offset=20)
        )

        assert repr(query) == (
            "Query(count from Gadget) WHERE id > 3 OR name IS NOT NULL "
            "ORDER BY name DESC LIMIT 10 OFFSET 20"
        )


class TestUploadFile:
    def test_size_is_measured_when_not_given(self):
        buffer = io.BytesIO(b"hello")
        buffer.seek(2)
        upload = UploadFile(filename="a.txt", file=buffer)

        assert upload.size == 5
        assert buffer.tell() == 2

    @pytest.mark.asyncio
    async def test_seek_moves_the_read_position(self):
        upload = UploadFile(filename="a.txt", file=io.BytesIO(b"hello"))

        assert await upload.seek(2) == 2
        assert await upload.read() == b"llo"

    def test_close_closes_the_underlying_file(self):
        upload = UploadFile(filename="a.txt", file=io.BytesIO(b"hello"))

        upload.close()

        assert upload.file.closed

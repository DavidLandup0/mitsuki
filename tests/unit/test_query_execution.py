"""
Tests for SQLAlchemyAdapter.execute_query translating Query objects into SQL.
"""

from dataclasses import dataclass
from typing import Optional

import pytest
import pytest_asyncio

from mitsuki.data import (
    ComparisonOperator,
    Entity,
    Id,
    QueryObject,
    SQLAlchemyAdapter,
    get_entity_metadata,
)
from mitsuki.data.query import LogicalOperator


@Entity()
@dataclass
class ScoredRow:
    id: int = Id()
    name: str = ""
    score: int = 0
    note: Optional[str] = None


ROWS = [
    {"name": "alpha", "score": 10, "note": "first"},
    {"name": "bravo", "score": 20, "note": None},
    {"name": "charlie", "score": 30, "note": "third"},
    {"name": "delta", "score": 40, "note": None},
]


@pytest_asyncio.fixture
async def adapter():
    adapter = SQLAlchemyAdapter()
    await adapter.connect("sqlite+aiosqlite:///:memory:")
    await adapter.create_table_if_not_exists(get_entity_metadata(ScoredRow))
    table = get_entity_metadata(ScoredRow).table_name
    for row in ROWS:
        await adapter.execute_insert(table, row)

    yield adapter

    await adapter.disconnect()


async def _names(adapter, query) -> list:
    return [row["name"] for row in await adapter.execute_query(query)]


def _query(*conditions, logical_operator=LogicalOperator.AND):
    query = QueryObject(entity_type=ScoredRow, logical_operator=logical_operator)
    for field_name, operator, value in conditions:
        query.add_condition(field_name, operator, value)
    return query.with_order("id")


class TestComparisonOperators:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("operator", "value", "expected"),
        [
            (ComparisonOperator.EQUALS, 20, ["bravo"]),
            (ComparisonOperator.NOT_EQUALS, 20, ["alpha", "charlie", "delta"]),
            (ComparisonOperator.GREATER_THAN, 20, ["charlie", "delta"]),
            (
                ComparisonOperator.GREATER_THAN_OR_EQUAL,
                20,
                ["bravo", "charlie", "delta"],
            ),
            (ComparisonOperator.LESS_THAN, 20, ["alpha"]),
            (ComparisonOperator.LESS_THAN_OR_EQUAL, 20, ["alpha", "bravo"]),
            (ComparisonOperator.IN, [10, 40], ["alpha", "delta"]),
            (ComparisonOperator.NOT_IN, [10, 40], ["bravo", "charlie"]),
        ],
        ids=lambda value: value.name if isinstance(value, ComparisonOperator) else "",
    )
    async def test_score_comparison(self, adapter, operator, value, expected):
        query = _query(("score", operator, value))

        assert await _names(adapter, query) == expected

    @pytest.mark.asyncio
    async def test_like(self, adapter):
        query = _query(("name", ComparisonOperator.LIKE, "%a"))

        assert await _names(adapter, query) == ["alpha", "delta"]

    @pytest.mark.asyncio
    async def test_is_null(self, adapter):
        query = _query(("note", ComparisonOperator.IS_NULL, None))

        assert await _names(adapter, query) == ["bravo", "delta"]

    @pytest.mark.asyncio
    async def test_is_not_null(self, adapter):
        query = _query(("note", ComparisonOperator.IS_NOT_NULL, None))

        assert await _names(adapter, query) == ["alpha", "charlie"]


class TestLogicalOperators:
    @pytest.mark.asyncio
    async def test_and_requires_every_condition(self, adapter):
        query = _query(
            ("score", ComparisonOperator.GREATER_THAN, 10),
            ("note", ComparisonOperator.IS_NULL, None),
        )

        assert await _names(adapter, query) == ["bravo", "delta"]

    @pytest.mark.asyncio
    async def test_or_requires_any_condition(self, adapter):
        query = _query(
            ("score", ComparisonOperator.EQUALS, 10),
            ("name", ComparisonOperator.EQUALS, "delta"),
            logical_operator=LogicalOperator.OR,
        )

        assert await _names(adapter, query) == ["alpha", "delta"]

    @pytest.mark.asyncio
    async def test_no_conditions_selects_every_row(self, adapter):
        assert await _names(adapter, _query()) == ["alpha", "bravo", "charlie", "delta"]


class TestOrderingAndPagination:
    @pytest.mark.asyncio
    async def test_with_order_ascending(self, adapter):
        query = QueryObject(entity_type=ScoredRow).with_order("score")

        assert await _names(adapter, query) == ["alpha", "bravo", "charlie", "delta"]

    @pytest.mark.asyncio
    async def test_with_order_descending(self, adapter):
        query = QueryObject(entity_type=ScoredRow).with_order("score", descending=True)

        assert await _names(adapter, query) == ["delta", "charlie", "bravo", "alpha"]

    @pytest.mark.asyncio
    async def test_with_pagination_limits_and_offsets(self, adapter):
        query = (
            QueryObject(entity_type=ScoredRow)
            .with_order("score")
            .with_pagination(limit=2, offset=1)
        )

        assert await _names(adapter, query) == ["bravo", "charlie"]

    @pytest.mark.asyncio
    async def test_with_pagination_defaults_to_first_page(self, adapter):
        query = (
            QueryObject(entity_type=ScoredRow).with_order("score").with_pagination(2)
        )

        assert await _names(adapter, query) == ["alpha", "bravo"]

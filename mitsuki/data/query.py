from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Type


# TODO: Should probably consolidate the enums with
# other enums in Mitsuki, but these are more internal.
class QueryOperation(Enum):
    """Type of query operation"""

    SELECT = "select"
    COUNT = "count"
    DELETE = "delete"
    EXISTS = "exists"


class ComparisonOperator(Enum):
    """Comparison operators for query conditions"""

    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    LIKE = "LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class LogicalOperator(Enum):
    """Logical operators for combining conditions"""

    AND = "AND"
    OR = "OR"


@dataclass
class QueryCondition:
    """
    Represents a single condition in a query.
    e.g., age > 18, name = 'Alice', email LIKE '%@example.com'
    """

    field: str
    operator: ComparisonOperator
    value: Any = None  # None for IS NULL / IS NOT NULL

    def __repr__(self) -> str:
        if self.value is None and self.operator in (
            ComparisonOperator.IS_NULL,
            ComparisonOperator.IS_NOT_NULL,
        ):
            return f"{self.field} {self.operator.value}"
        return f"{self.field} {self.operator.value} {self.value!r}"


@dataclass
class Query:
    """
    Represents a parsed query with conditions, ordering, and pagination.
    Internal representation used before translating to actual SQL.
    """

    entity_type: Type
    operation: QueryOperation = QueryOperation.SELECT
    conditions: List[QueryCondition] = field(default_factory=list)
    logical_operator: LogicalOperator = LogicalOperator.AND
    order_by: Optional[str] = None
    order_desc: bool = False
    limit: Optional[int] = None
    offset: Optional[int] = None

    def add_condition(
        self, field_name: str, operator: ComparisonOperator, value: Any = None
    ) -> "Query":
        """Add a condition to the query (builder pattern)"""
        self.conditions.append(QueryCondition(field_name, operator, value))
        return self

    def with_order(self, field_name: str, descending: bool = False) -> "Query":
        """Add ordering to the query"""
        self.order_by = field_name
        self.order_desc = descending
        return self

    def with_pagination(self, limit: int, offset: int = 0) -> "Query":
        """Add pagination to the query"""
        self.limit = limit
        self.offset = offset
        return self

    def __repr__(self) -> str:
        parts = [f"Query({self.operation.value} from {self.entity_type.__name__})"]
        if self.conditions:
            conditions_str = f" {self.logical_operator.value} ".join(
                str(c) for c in self.conditions
            )
            parts.append(f"WHERE {conditions_str}")
        if self.order_by:
            order = "DESC" if self.order_desc else "ASC"
            parts.append(f"ORDER BY {self.order_by} {order}")
        if self.limit:
            parts.append(f"LIMIT {self.limit}")
        if self.offset:
            parts.append(f"OFFSET {self.offset}")
        return " ".join(parts)

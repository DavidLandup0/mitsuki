from typing import Any, List, Tuple, Type

from mitsuki.data.query import (
    ComparisonOperator,
    LogicalOperator,
    Query,
    QueryCondition,
    QueryOperation,
)
from mitsuki.exceptions import QueryException


class QueryParser:
    """
    Parses repository method names into Query objects.

    Supported patterns:
    - find_by_<field>
    - find_by_<field>_<operator>
    - find_by_<field>_and_<field>
    - find_by_<field>_or_<field>
    - count_by_<field>
    - delete_by_<field>
    - exists_by_<field>
    """

    # Operator keywords that modify the comparison
    OPERATOR_KEYWORDS = {
        "greater_than": ComparisonOperator.GREATER_THAN,
        "greater_than_or_equal": ComparisonOperator.GREATER_THAN_OR_EQUAL,
        "less_than": ComparisonOperator.LESS_THAN,
        "less_than_or_equal": ComparisonOperator.LESS_THAN_OR_EQUAL,
        "like": ComparisonOperator.LIKE,
        "in": ComparisonOperator.IN,
        "not_in": ComparisonOperator.NOT_IN,
        "is_null": ComparisonOperator.IS_NULL,
        "is_not_null": ComparisonOperator.IS_NOT_NULL,
    }

    # Operation prefixes
    OPERATION_PREFIXES = {
        "find_by": QueryOperation.SELECT,
        "count_by": QueryOperation.COUNT,
        "delete_by": QueryOperation.DELETE,
        "exists_by": QueryOperation.EXISTS,
    }

    @staticmethod
    def parse_method_name(method_name: str, entity_type: Type) -> Query:
        """
        Parse a repository method name into a Query object.

        Args:
            method_name: The method name to parse (e.g., "find_by_email_and_active")
            entity_type: The entity type this query is for

        Returns:
            Query object representing the parsed method

        Raises:
            QueryParseError: If the method name cannot be parsed
        """
        # Determine operation
        operation = None
        remaining = method_name

        for prefix, op in QueryParser.OPERATION_PREFIXES.items():
            if method_name.startswith(prefix + "_"):
                operation = op
                remaining = method_name[len(prefix) + 1 :]  # +1 for the underscore
                break

        if not operation:
            raise QueryException(
                f"Method '{method_name}' does not start with a valid operation prefix: "
                f"{', '.join(QueryParser.OPERATION_PREFIXES.keys())}"
            )

        # Parse conditions from remaining string
        # Split by _and_ or _or_ to get logical operators
        logical_operator = LogicalOperator.AND
        condition_parts: List[str] = []

        if "_or_" in remaining:
            condition_parts = remaining.split("_or_")
            logical_operator = LogicalOperator.OR
        elif "_and_" in remaining:
            condition_parts = remaining.split("_and_")
            logical_operator = LogicalOperator.AND
        else:
            condition_parts = [remaining]

        # Parse each condition part
        conditions: List[QueryCondition] = []
        for part in condition_parts:
            condition = QueryParser._parse_condition(part)
            conditions.append(condition)

        # Build and return query
        query = Query(
            entity_type=entity_type,
            operation=operation,
            conditions=conditions,
            logical_operator=logical_operator,
        )

        return query

    @staticmethod
    def _parse_condition(condition_str: str) -> QueryCondition:
        """
        Parse a single condition string into a QueryCondition.

        Examples:
            "email" -> QueryCondition("email", EQUALS)
            "age_greater_than" -> QueryCondition("age", GREATER_THAN)
            "name_like" -> QueryCondition("name", LIKE)

        Args:
            condition_str: The condition string to parse

        Returns:
            QueryCondition object

        Raises:
            QueryParseError: If the condition cannot be parsed
        """
        # Check for operator keywords at the end
        operator = ComparisonOperator.EQUALS  # Default
        field_name = condition_str

        # Try to match operator keywords (check longest first)
        sorted_operators = sorted(
            QueryParser.OPERATOR_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True
        )

        for keyword, op in sorted_operators:
            if condition_str.endswith("_" + keyword):
                operator = op
                field_name = condition_str[: -(len(keyword) + 1)]  # +1 for underscore
                break

        if not field_name:
            raise QueryException(f"Invalid condition string: '{condition_str}'")

        return QueryCondition(field=field_name, operator=operator)

    @staticmethod
    def extract_parameter_values(
        query: Query, args: Tuple[Any, ...], kwargs: dict
    ) -> Query:
        """
        Fill in the query condition values from method arguments.

        Args:
            query: Query object with conditions (values may be None)
            args: Positional arguments from method call
            kwargs: Keyword arguments from method call

        Returns:
            Query object with condition values filled in

        Raises:
            QueryParseError: If argument count doesn't match condition count
        """
        # Count how many arguments we need (exclude IS_NULL and IS_NOT_NULL)
        conditions_needing_values = [
            c
            for c in query.conditions
            if c.operator
            not in (ComparisonOperator.IS_NULL, ComparisonOperator.IS_NOT_NULL)
        ]

        if len(args) != len(conditions_needing_values):
            raise QueryException(
                f"Expected {len(conditions_needing_values)} arguments, got {len(args)}"
            )

        # Fill in values
        for i, condition in enumerate(conditions_needing_values):
            condition.value = args[i]

        return query


# Convenience function for parsing
def parse_query_method(
    method_name: str, entity_type: Type, args: Tuple[Any, ...]
) -> Query:
    """
    Parse a query method name and fill in parameter values.

    Args:
        method_name: Repository method name
        entity_type: Entity type
        args: Method arguments

    Returns:
        Complete Query object ready for execution
    """
    query = QueryParser.parse_method_name(method_name, entity_type)
    query = QueryParser.extract_parameter_values(query, args, {})
    return query

"""
Tests for the MitsukiEnum helpers inherited by every exported enum.
"""

import json
import logging

import pytest

from mitsuki.core.enums import (
    ASGIMessageType,
    ASGIScopeType,
    DatabaseAdapter,
    DatabaseDialect,
    HttpMethod,
    LogLevel,
    MediaType,
    MetricType,
    MitsukiEnum,
    ParameterKind,
    ScheduleType,
    Scope,
    ServerType,
    StereotypeType,
    TaskStatus,
    UIType,
)

ALL_ENUMS = [
    ServerType,
    DatabaseAdapter,
    DatabaseDialect,
    ASGIMessageType,
    ASGIScopeType,
    ParameterKind,
    Scope,
    StereotypeType,
    HttpMethod,
    MediaType,
    LogLevel,
    MetricType,
    ScheduleType,
    TaskStatus,
    UIType,
]

MEMBERS = [member for enum_cls in ALL_ENUMS for member in enum_cls]


def _member_id(member: MitsukiEnum) -> str:
    return f"{type(member).__name__}.{member.name}"


class TestFromString:
    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_value_resolves_to_member(self, member):
        assert type(member).from_string(member.value) is member

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_lookup_is_case_insensitive(self, member):
        assert type(member).from_string(member.value.upper()) is member

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_member_is_returned_unchanged(self, member):
        assert type(member).from_string(member) is member

    def test_unknown_value_raises_listing_valid_values(self):
        with pytest.raises(ValueError, match="Invalid ServerType: 'uvicornn'") as info:
            ServerType.from_string("uvicornn")

        assert "'uvicorn', 'granian', 'socketify'" in str(info.value)

    @pytest.mark.parametrize("value", [None, 1, 1.5, ["uvicorn"]])
    def test_non_string_raises(self, value):
        with pytest.raises(ValueError, match="must be a string or ServerType enum"):
            ServerType.from_string(value)


class TestIsValid:
    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_value_is_valid(self, member):
        assert type(member).is_valid(member.value)

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_member_is_valid(self, member):
        assert type(member).is_valid(member)

    def test_value_is_valid_case_insensitively(self):
        assert ServerType.is_valid("GRANIAN")

    def test_unknown_value_is_invalid(self):
        assert not ServerType.is_valid("uvicornn")

    def test_member_of_another_enum_with_unknown_value_is_invalid(self):
        assert not ServerType.is_valid(Scope.SINGLETON)

    @pytest.mark.parametrize("value", [None, 1, 1.5, ["uvicorn"]])
    def test_non_string_is_invalid(self, value):
        assert not ServerType.is_valid(value)


class TestStringComparison:
    def test_member_equals_its_value(self):
        assert ParameterKind.BODY == "body"
        assert ASGIScopeType.HTTP == "http"


class TestInterpolation:
    """Members must render as their value so they can be used in strings directly."""

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_str_is_the_value(self, member):
        assert str(member) == member.value

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_f_string_is_the_value(self, member):
        assert f"{member}" == member.value

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_concatenation_is_the_value(self, member):
        assert member + "; charset=utf-8" == member.value + "; charset=utf-8"

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_json_serializes_as_the_value(self, member):
        assert json.dumps({"k": member}) == f'{{"k": "{member.value}"}}'

    def test_uppercase_valued_enums_resolve_from_lowercase_input(self):
        assert HttpMethod.from_string("get") is HttpMethod.GET
        assert LogLevel.from_string("debug") is LogLevel.DEBUG

    @pytest.mark.parametrize("member", MEMBERS, ids=_member_id)
    def test_surrounding_whitespace_is_ignored(self, member):
        assert type(member).from_string(f"  {member.value}  ") is member

    @pytest.mark.parametrize(
        ("level", "number"),
        [
            (LogLevel.DEBUG, logging.DEBUG),
            (LogLevel.INFO, logging.INFO),
            (LogLevel.WARNING, logging.WARNING),
            (LogLevel.ERROR, logging.ERROR),
            (LogLevel.CRITICAL, logging.CRITICAL),
        ],
    )
    def test_log_level_exposes_its_numeric_severity(self, level, number):
        assert level.numeric == number

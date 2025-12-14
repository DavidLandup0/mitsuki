from enum import Enum
from typing import Union


class MitsukiEnum(str, Enum):
    """Base enum with helper methods for all Mitsuki enums."""

    @classmethod
    def from_string(cls, value: Union[str, "MitsukiEnum"]) -> "MitsukiEnum":
        """
        Convert string to enum, case-insensitive.

        Args:
            value: String value or enum instance

        Returns:
            Enum value

        Raises:
            ValueError: If value is not valid for this enum

        Examples:
            >>> ServerType.from_string("uvicorn")
            ServerType.UVICORN
            >>> ServerType.from_string("GRANIAN")
            ServerType.GRANIAN
        """
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise ValueError(
                f"{cls.__name__} must be a string or {cls.__name__} enum, got {type(value).__name__}"
            )

        try:
            return cls(value.lower())
        except ValueError:
            valid_values = ", ".join([f"'{v.value}'" for v in cls])
            raise ValueError(
                f"Invalid {cls.__name__}: '{value}'. Must be one of: {valid_values}"
            )

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Check if value is valid for this enum.

        Args:
            value: String value to check

        Returns:
            True if value is valid, False otherwise

        Examples:
            >>> ServerType.is_valid("uvicorn")
            True
            >>> ServerType.is_valid("invalid")
            False
        """
        if isinstance(value, cls):
            return True

        if not isinstance(value, str):
            return False

        try:
            cls.from_string(value)
            return True
        except ValueError:
            return False


class ServerType(MitsukiEnum):
    """Server implementation types."""

    UVICORN = "uvicorn"
    GRANIAN = "granian"
    SOCKETIFY = "socketify"


class DatabaseAdapter(MitsukiEnum):
    """Database adapter types."""

    SQLALCHEMY = "sqlalchemy"


class DatabaseDialect(MitsukiEnum):
    """Database dialect types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class SQLOperation(MitsukiEnum):
    """SQL operation types."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ASGIMessageType(MitsukiEnum):
    """ASGI message types."""

    HTTP_REQUEST = "http.request"
    HTTP_DISCONNECT = "http.disconnect"
    LIFESPAN_STARTUP = "lifespan.startup"
    LIFESPAN_SHUTDOWN = "lifespan.shutdown"


class ASGIScopeType(MitsukiEnum):
    """ASGI scope types."""

    HTTP = "http"
    LIFESPAN = "lifespan"


class ParameterKind(MitsukiEnum):
    """Parameter injection kinds."""

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    BODY = "body"
    FILE = "file"
    FORM = "form"
    AUTO = "auto"
    REQUEST = "request"


class Scope(MitsukiEnum):
    """Dependency injection scopes."""

    SINGLETON = "singleton"
    PROTOTYPE = "prototype"

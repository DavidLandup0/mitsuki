import logging
from enum import Enum
from typing import Union


class MitsukiEnum(str, Enum):
    """Base enum with helper methods for all Mitsuki enums."""

    # Interpolating a member into a string yields its value, not "Class.MEMBER",
    # so these enums can be used directly in messages and headers.
    __str__ = str.__str__

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
            >>> HttpMethod.from_string("get")
            HttpMethod.GET
        """
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise ValueError(
                f"{cls.__name__} must be a string or {cls.__name__} enum, got {type(value).__name__}"
            )

        needle = value.strip().lower()
        for member in cls:
            if member.value.lower() == needle:
                return member

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
    HTTP_RESPONSE_START = "http.response.start"
    HTTP_RESPONSE_BODY = "http.response.body"
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


class Propagation(MitsukiEnum):
    """How a transactional block relates to a transaction already in progress."""

    REQUIRED = "required"
    REQUIRES_NEW = "requires_new"
    NESTED = "nested"


class Isolation(MitsukiEnum):
    """Transaction isolation levels, valued as SQLAlchemy names them."""

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class Scope(MitsukiEnum):
    """Dependency injection scopes."""

    SINGLETON = "singleton"
    PROTOTYPE = "prototype"


class StereotypeType(MitsukiEnum):
    """Flags for components"""

    COMPONENT = "component"
    SERVICE = "service"
    REPOSITORY = "repository"
    CONTROLLER = "controller"
    PROVIDER = "provider"
    CONFIGURATION = "configuration"


class HttpMethod(MitsukiEnum):
    """HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class UIType(MitsukiEnum):
    """OpenAPI documentation UI types."""

    SWAGGER = "swagger"
    REDOC = "redoc"
    SCALAR = "scalar"


_LOG_LEVEL_NUMBERS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class LogLevel(MitsukiEnum):
    """Log levels, ordered from most to least verbose."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """`logging` module severity for this level."""
        return _LOG_LEVEL_NUMBERS[self.value]


class TaskStatus(MitsukiEnum):
    """Lifecycle state of a scheduled task."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ScheduleType(MitsukiEnum):
    """How a scheduled task determines its next run."""

    FIXED_RATE = "fixed_rate"
    FIXED_DELAY = "fixed_delay"
    CRON = "cron"


class MetricType(MitsukiEnum):
    """Prometheus metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MediaType(MitsukiEnum):
    """Common media types."""

    APPLICATION_JSON = "application/json"
    APPLICATION_OCTET_STREAM = "application/octet-stream"
    APPLICATION_FORM_URLENCODED = "application/x-www-form-urlencoded"
    MULTIPART_FORM_DATA = "multipart/form-data"
    TEXT_PLAIN = "text/plain"
    TEXT_HTML = "text/html"
    TEXT_CSS = "text/css"
    TEXT_XML = "text/xml"
    APPLICATION_XML = "application/xml"
    APPLICATION_PDF = "application/pdf"
    IMAGE_PNG = "image/png"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_GIF = "image/gif"
    IMAGE_SVG_XML = "image/svg+xml"

class MitsukiException(Exception):
    pass


class ConfigurationException(MitsukiException):
    """Configuration-related errors."""

    pass


class PropertyParseException(ConfigurationException):
    """Failed to parse property value to expected type."""

    pass


class PropertyNotFoundException(ConfigurationException):
    """Required configuration property not found."""

    pass


class DependencyInjectionException(MitsukiException):
    """Dependency injection container errors."""

    pass


class ComponentNotFoundException(DependencyInjectionException):
    """Component not registered in container."""

    pass


class CircularDependencyException(DependencyInjectionException):
    """Circular dependency detected during resolution."""

    pass


class DataException(MitsukiException):
    """Database and data access errors."""

    pass


class DatabaseNotConnectedException(DataException):
    """Database connection not established."""

    pass


class QueryException(DataException):
    """Query execution or parsing errors."""

    pass


class EntityException(DataException):
    """Entity definition or metadata errors."""

    pass


class UUIDGenerationException(DataException):
    """UUID generation errors (e.g., missing namespace for v5)."""

    pass


class WebException(MitsukiException):
    """Web/HTTP request handling errors."""

    pass


class RequestValidationException(WebException):
    """Request parameter validation failed."""

    pass


class RouteNotFoundException(WebException):
    """No route matches the request."""

    pass


class InvalidContentTypeException(WebException):
    """Content-Type header invalid or missing."""

    pass


class FileTooLargeException(WebException):
    """Uploaded file exceeds maximum size."""

    pass


class RequestTooLargeException(WebException):
    """Request size exceeds maximum allowed size."""

    pass


class InvalidFileTypeException(WebException):
    """Uploaded file type not allowed."""

    pass


class MultipartParseException(WebException):
    """Error parsing multipart/form-data request."""

    pass

class ConfigurationError(Exception):
    """Base exception for configuration errors."""

    pass


class PropertyParseError(ConfigurationError):
    """Raised when a property value cannot be parsed to the expected type."""

    pass


class PropertyNotFoundError(ConfigurationError):
    """Raised when a required property is not found."""

    pass

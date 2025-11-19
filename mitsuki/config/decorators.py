from typing import Any, Callable, Type, Union

from mitsuki.config.properties import TRUTHY_VALUES, get_config
from mitsuki.core.utils import get_active_profile


class ValueDescriptor:
    """
    Descriptor for @Value-injected properties.
    Resolves configuration values at runtime.
    """

    def __init__(self, expression: str, default: Any = None):
        self.expression = expression
        self.default = default
        self.config_key = None
        self.field_type = None
        self.attr_name = None
        self._parse_expression()

    def __set_name__(self, owner, name):
        """Called when descriptor is assigned to class attribute"""
        self.attr_name = name
        # Get type hint if available
        if hasattr(owner, "__annotations__") and name in owner.__annotations__:
            self.field_type = owner.__annotations__[name]

    def _parse_expression(self):
        """
        Parse ${key:default} expression.
        Examples:
            ${server.port} -> key="server.port", default=None
            ${server.port:8000} -> key="server.port", default=8000
        """
        expr = self.expression.strip()

        # Check for ${...} syntax
        if expr.startswith("${") and expr.endswith("}"):
            expr = expr[2:-1]  # Remove ${ and }

            # Check for :default syntax
            if ":" in expr:
                key, default_str = expr.split(":", 1)
                self.config_key = key.strip()
                # Store raw default string, will parse with type info later
                self._default_str = default_str.strip()
            else:
                self.config_key = expr.strip()
                self._default_str = None
        else:
            # Direct key without ${}
            self.config_key = expr
            self._default_str = None

    def _parse_typed_value(self, value: str, target_type: type) -> Any:
        """Parse value string to target type"""
        if target_type == bool:
            return value.lower() in TRUTHY_VALUES
        elif target_type == str:
            return value
        else:
            return target_type(value)

    def __get__(self, instance, owner):
        """Get configuration value when property is accessed"""
        if instance is None:
            return self

        config = get_config()

        # Get default value, parsing it if needed
        default = self.default
        if (
            default is None
            and self._default_str is not None
            and self.field_type is not None
        ):
            default = self._parse_typed_value(self._default_str, self.field_type)
        elif default is None and self._default_str is not None:
            # No type hint, use old defensive parsing
            default = self._default_str

        value = config.get(self.config_key, default)
        return value

    def __set__(self, instance, value):
        """Prevent setting @Value properties"""
        raise AttributeError(f"Cannot set @Value property '{self.config_key}'")


def Value(expression: str, default: Any = None):
    """
    Inject configuration value into a class property.

    Usage:
        @Configuration
        class AppConfig:
            @Value("${server.port:8000}")
            port: int

            @Value("${app.name}")
            name: str

    Expression formats:
        - "${key}" - Get value for key, None if not found
        - "${key:default}" - Get value for key, use default if not found
        - "key" - Plain key without ${} syntax

    Args:
        expression: Configuration key expression
        default: Default value if key not found (overridden by :default in expression)

    Returns:
        Property descriptor that resolves configuration value
    """
    return ValueDescriptor(expression, default)


def Profile(*profiles: str):
    """
    Conditional registration based on active profile.
    Only registers the component if one of the specified profiles is active.

    Usage:
        @Configuration
        @Profile("production")
        class ProductionConfig:
            @Provider
            def database_url(self) -> str:
                return "postgresql://prod-server/db"

        @Configuration
        @Profile("development", "test")
        class DevConfig:
            @Provider
            def database_url(self) -> str:
                return "sqlite:///dev.db"

    Args:
        *profiles: One or more profile names (component is active if any match)

    Returns:
        Decorator that conditionally registers the component
    """

    def decorator(cls_or_func: Union[Type, Callable]) -> Union[Type, Callable]:
        # Get active profile
        active_profile = get_active_profile()
        is_active = active_profile in profiles

        # Store profile metadata - DI container will skip if __mitsuki_profile_active__ is False
        cls_or_func.__mitsuki_profiles__ = profiles
        cls_or_func.__mitsuki_profile_active__ = is_active

        return cls_or_func

    return decorator

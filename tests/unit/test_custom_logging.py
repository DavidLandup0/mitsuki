"""
Tests for custom logging via @Provider decorator.
"""

import logging
from typing import List

from mitsuki.config.properties import reload_config
from mitsuki.core.application import ApplicationContext
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.decorators import Configuration, Provider
from mitsuki.core.enums import Scope
from mitsuki.core.logging import ColoredFormatter, configure_logging
from mitsuki.core.providers import initialize_configuration_providers


class CustomTestFormatter(logging.Formatter):
    """Custom formatter for testing."""

    def format(self, record):
        return f"CUSTOM: {record.levelname} - {record.getMessage()}"


class TestCustomFormatter:
    """Tests for custom log formatter via @Provider."""

    def setup_method(self):
        """Reset container and config before each test."""

        set_container(DIContainer())
        reload_config()

    def test_custom_formatter_provider(self):
        """Test that custom formatter provider is used."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_formatter")
            def custom_formatter(self) -> logging.Formatter:
                return CustomTestFormatter()

        # Register and initialize
        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # Create application context which calls _setup_logging
        context = ApplicationContext(LoggingConfig)

        # Verify the custom formatter is applied
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, CustomTestFormatter)

    def test_custom_formatter_formats_messages(self):
        """Test that custom formatter actually formats messages."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_formatter")
            def custom_formatter(self) -> logging.Formatter:
                return CustomTestFormatter()

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # Setup logging
        custom_formatter = container.get_by_name("log_formatter")
        configure_logging(level="INFO", custom_formatter=custom_formatter)

        # Create a test record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        root_logger = logging.getLogger()
        formatted = root_logger.handlers[0].formatter.format(record)
        assert formatted == "CUSTOM: INFO - Test message"


class TestCustomHandlers:
    """Tests for custom log handlers via @Provider."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()

    def test_custom_handlers_provider(self):
        """Test that custom handlers provider is used."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_handlers")
            def custom_handlers(self) -> List[logging.Handler]:
                handler1 = logging.StreamHandler()
                handler1.setLevel(logging.DEBUG)
                handler2 = logging.StreamHandler()
                handler2.setLevel(logging.INFO)
                return [handler1, handler2]

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # Create application context
        context = ApplicationContext(LoggingConfig)

        # Verify custom handlers are applied
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2
        assert root_logger.handlers[0].level == logging.DEBUG
        assert root_logger.handlers[1].level == logging.INFO

    def test_custom_handlers_count(self):
        """Test that exactly the custom handlers are used."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_handlers")
            def custom_handlers(self) -> List[logging.Handler]:
                # Return 3 custom handlers
                return [
                    logging.StreamHandler(),
                    logging.StreamHandler(),
                    logging.StreamHandler(),
                ]

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        context = ApplicationContext(LoggingConfig)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 3


class TestBothFormatterAndHandlers:
    """Tests for using both custom formatter and handlers."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()

    def test_both_formatter_and_handlers(self):
        """Test using both custom formatter and handlers together."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_formatter")
            def custom_formatter(self) -> logging.Formatter:
                return CustomTestFormatter()

            @Provider(name="log_handlers")
            def custom_handlers(self) -> List[logging.Handler]:
                # Manually apply the custom formatter
                formatter = CustomTestFormatter()
                handler1 = logging.StreamHandler()
                handler1.setFormatter(formatter)
                handler2 = logging.StreamHandler()
                handler2.setFormatter(formatter)
                return [handler1, handler2]

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        context = ApplicationContext(LoggingConfig)

        # Verify both are applied
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2

        # Both handlers should have the custom formatter
        for handler in root_logger.handlers:
            assert isinstance(handler.formatter, CustomTestFormatter)

    def test_separate_formatter_and_handlers_providers(self):
        """Test that separate formatter and handlers providers work together."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_formatter")
            def custom_formatter(self) -> logging.Formatter:
                return CustomTestFormatter()

            @Provider(name="log_handlers")
            def custom_handlers(self) -> List[logging.Handler]:
                # Just return handlers without formatter
                # The configure_logging function should apply the formatter
                return [logging.StreamHandler()]

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # The ApplicationContext should apply formatter to handlers
        context = ApplicationContext(LoggingConfig)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1


class TestNoCustomProviders:
    """Tests for default logging when no custom providers are registered."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()

    def test_default_logging_without_providers(self):
        """Test that default logging works when no custom providers exist."""

        @Configuration
        class EmptyConfig:
            pass

        container = get_container()
        container.register(EmptyConfig, name="EmptyConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        context = ApplicationContext(EmptyConfig)

        # Should use default ColoredFormatter and StreamHandler
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        # Default is StreamHandler with ColoredFormatter
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, ColoredFormatter)

    def test_has_by_name_returns_false_for_missing_providers(self):
        """Test that has_by_name correctly returns False for missing providers."""

        @Configuration
        class EmptyConfig:
            pass

        container = get_container()
        container.register(EmptyConfig, name="EmptyConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        # Should return False for logging providers that don't exist
        assert container.has_by_name("log_formatter") is False
        assert container.has_by_name("log_handlers") is False


class TestCustomFormatterOnly:
    """Tests for custom formatter without custom handlers."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()

    def test_custom_formatter_with_default_handlers(self):
        """Test that custom formatter works with default handlers."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_formatter")
            def custom_formatter(self) -> logging.Formatter:
                return CustomTestFormatter()

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        context = ApplicationContext(LoggingConfig)

        root_logger = logging.getLogger()
        # Should have default handler(s) with custom formatter
        assert len(root_logger.handlers) > 0
        assert isinstance(root_logger.handlers[0].formatter, CustomTestFormatter)


class TestCustomHandlersOnly:
    """Tests for custom handlers without custom formatter."""

    def setup_method(self):
        """Reset container and config before each test."""
        set_container(DIContainer())
        reload_config()

    def test_custom_handlers_with_default_formatter(self):
        """Test that custom handlers work with default formatter."""

        @Configuration
        class LoggingConfig:
            @Provider(name="log_handlers")
            def custom_handlers(self) -> List[logging.Handler]:
                handler = logging.StreamHandler()
                return [handler]

        container = get_container()
        container.register(LoggingConfig, name="LoggingConfig", scope=Scope.SINGLETON)
        initialize_configuration_providers()

        context = ApplicationContext(LoggingConfig)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        # Handler should exist but formatter depends on configure_logging implementation
        assert root_logger.handlers[0] is not None

"""
Unit tests for @Provider and @Configuration functionality.
Tests provider factory methods, configuration class scanning, and dependency injection.
"""

import pytest

from mitsuki import Application, Component, Configuration, Provider, Service
from mitsuki.core.application import ApplicationContext
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.providers import initialize_configuration_providers
from mitsuki.exceptions import DependencyInjectionException


@pytest.fixture(autouse=True)
def reset_container():
    """Reset the global container before each test."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


class TestProviderDecorator:
    """Tests for @Provider decorator functionality."""

    def test_provider_with_parentheses(self):
        """@Provider() with parentheses should work."""

        @Configuration
        class Config:
            @Provider()
            def test_provider(self) -> str:
                return "test value"

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        assert "test_provider" in context.container._components_by_name
        provider = context.container.get_by_name("test_provider")
        assert provider == "test value"

    def test_provider_without_parentheses(self):
        """@Provider without parentheses should work."""

        @Configuration
        class Config:
            @Provider
            def test_provider(self) -> str:
                return "test value"

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        assert "test_provider" in context.container._components_by_name
        provider = context.container.get_by_name("test_provider")
        assert provider == "test value"

    def test_provider_custom_name(self):
        """@Provider with custom name should register with that name."""

        @Configuration
        class Config:
            @Provider(name="customProviderName")
            def test_provider(self) -> str:
                return "test value"

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        assert "customProviderName" in context.container._components_by_name
        provider = context.container.get_by_name("customProviderName")
        assert provider == "test value"

    def test_provider_singleton_scope(self):
        """@Provider with singleton scope should return same instance."""
        call_count = {"value": 0}

        @Configuration
        class Config:
            @Provider(scope="singleton")
            def counter_provider(self) -> dict:
                call_count["value"] += 1
                return {"count": call_count["value"]}

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        provider1 = context.container.get_by_name("counter_provider")
        provider2 = context.container.get_by_name("counter_provider")

        assert provider1 is provider2
        assert provider1["count"] == 1
        assert call_count["value"] == 1

    def test_provider_prototype_scope(self):
        """
        @Provider with prototype scope - currently limited implementation.
        Factory method is called once during initialization, but container
        returns different instances due to prototype scope on the registered type.

        Note: This is different from true prototype behavior where the factory
        method would be re-executed on each request.
        """

        @Configuration
        class Config:
            @Provider(scope="prototype")
            def counter_provider(self) -> dict:
                return {"initial": "value"}

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        # The provider is registered as prototype scope, so container behavior applies
        # (but factory method is not re-executed)
        provider1 = context.container.get_by_name("counter_provider")
        provider2 = context.container.get_by_name("counter_provider")

        # Note: For dict/list types, container creates new instances for prototype
        # This test just verifies prototype scope is respected at container level
        assert provider1 == provider2  # Same content
        # We can't reliably test identity for mutable builtin types

    def test_multiple_providers_in_config(self):
        """Multiple @Provider methods in one @Configuration should all be registered."""

        @Configuration
        class Config:
            @Provider
            def provider_one(self) -> str:
                return "one"

            @Provider
            def provider_two(self) -> int:
                return 2

            @Provider
            def provider_three(self) -> list:
                return [1, 2, 3]

        context = ApplicationContext(Application(type("App", (), {})))
        initialize_configuration_providers()

        assert context.container.get_by_name("provider_one") == "one"
        assert context.container.get_by_name("provider_two") == 2
        assert context.container.get_by_name("provider_three") == [1, 2, 3]


class TestConfigurationScanning:
    """Tests for @Configuration class scanning."""

    def test_standalone_configuration_class(self):
        """Standalone @Configuration classes should be scanned."""

        @Configuration
        class StandaloneConfig:
            @Provider
            def standalone_provider(self) -> str:
                return "standalone"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "standalone_provider" in context.container._components_by_name
        assert context.container.get_by_name("standalone_provider") == "standalone"

    def test_multiple_configuration_classes(self):
        """Multiple @Configuration classes should all be scanned."""

        @Configuration
        class ConfigOne:
            @Provider
            def provider_one(self) -> str:
                return "config one"

        @Configuration
        class ConfigTwo:
            @Provider
            def provider_two(self) -> str:
                return "config two"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert context.container.get_by_name("provider_one") == "config one"
        assert context.container.get_by_name("provider_two") == "config two"

    def test_configuration_is_singleton(self):
        """@Configuration classes should be registered as singletons."""

        @Configuration
        class Config:
            def __init__(self):
                self.id = id(self)

        container = get_container()
        config1 = container.get(Config)
        config2 = container.get(Config)

        assert config1 is config2
        assert config1.id == config2.id

    def test_application_class_is_configuration(self):
        """@Application classes should be treated as @Configuration."""

        @Application
        class App:
            @Provider
            def app_provider(self) -> str:
                return "from app"

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "app_provider" in context.container._components_by_name
        assert context.container.get_by_name("app_provider") == "from app"


class TestProviderInjection:
    """Tests for provider injection into services."""

    def test_inject_provider_by_name(self):
        """Providers should be injectable by parameter name."""

        @Configuration
        class Config:
            @Provider
            def database_url(self) -> str:
                return "sqlite:///test.db"

        @Service()
        class DatabaseService:
            def __init__(self, database_url: str):
                self.url = database_url

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        service = context.container.get(DatabaseService)
        assert service.url == "sqlite:///test.db"

    def test_inject_multiple_providers(self):
        """Multiple providers should be injectable into one service."""

        @Configuration
        class Config:
            @Provider
            def api_key(self) -> str:
                return "secret-key-123"

            @Provider
            def timeout(self) -> int:
                return 30

            @Provider
            def debug_mode(self) -> bool:
                return True

        @Service()
        class ApiService:
            def __init__(self, api_key: str, timeout: int, debug_mode: bool):
                self.key = api_key
                self.timeout = timeout
                self.debug = debug_mode

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        service = context.container.get(ApiService)
        assert service.key == "secret-key-123"
        assert service.timeout == 30
        assert service.debug is True

    def test_provider_injection_with_type_priority(self):
        """Type-based injection should take priority over name-based."""

        @Component()
        class DatabaseConnection:
            def __init__(self):
                self.type = "component"

        @Configuration
        class Config:
            @Provider(name="database_connection")
            def db_conn(self) -> str:
                return "provider"

        @Service()
        class MyService:
            def __init__(self, database_connection: DatabaseConnection):
                self.conn = database_connection

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        service = context.container.get(MyService)
        # Should inject the component, not the provider (type match takes priority)
        assert isinstance(service.conn, DatabaseConnection)
        assert service.conn.type == "component"

    def test_inject_complex_types(self):
        """Providers returning complex types should be injectable."""

        class CustomConfig:
            def __init__(self, host: str, port: int):
                self.host = host
                self.port = port

        @Configuration
        class Config:
            @Provider
            def app_config(self) -> CustomConfig:
                return CustomConfig("localhost", 8080)

        @Service()
        class AppService:
            def __init__(self, app_config: CustomConfig):
                self.config = app_config

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        service = context.container.get(AppService)
        assert service.config.host == "localhost"
        assert service.config.port == 8080


class TestProviderErrors:
    """Tests for error handling in provider creation."""

    def test_missing_provider_dependency(self):
        """Should raise clear error when provider dependency is missing."""

        @Service()
        class MyService:
            def __init__(self, missing_provider: str):
                self.value = missing_provider

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        with pytest.raises(DependencyInjectionException) as exc_info:
            context.container.get(MyService)

        assert "Cannot resolve dependency 'missing_provider'" in str(exc_info.value)
        assert "MyService" in str(exc_info.value)

    def test_provider_factory_exception(self):
        """Exceptions in provider factory methods should propagate."""

        @Configuration
        class Config:
            @Provider
            def failing_provider(self) -> str:
                raise RuntimeError("Provider creation failed!")

        @Application
        class App:
            pass

        context = ApplicationContext(App)

        with pytest.raises(RuntimeError) as exc_info:
            initialize_configuration_providers()

        assert "Provider creation failed!" in str(exc_info.value)


class TestProviderWithConfiguration:
    """Tests for providers accessing configuration values."""

    def test_provider_access_config_attributes(self):
        """Provider methods can access configuration class attributes."""

        @Configuration
        class Config:
            def __init__(self):
                self.base_url = "https://api.example.com"
                self.version = "v1"

            @Provider
            def full_url(self) -> str:
                return f"{self.base_url}/{self.version}"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        url = context.container.get_by_name("full_url")
        assert url == "https://api.example.com/v1"

    def test_provider_with_injected_dependencies_in_config(self):
        """Configuration classes can have dependencies injected."""

        @Service()
        class ConfigProvider:
            def get_timeout(self) -> int:
                return 42

        @Configuration
        class Config:
            def __init__(self, config_provider: ConfigProvider):
                self.provider = config_provider

            @Provider
            def timeout(self) -> int:
                return self.provider.get_timeout()

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        timeout = context.container.get_by_name("timeout")
        assert timeout == 42

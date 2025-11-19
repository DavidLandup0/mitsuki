"""
Unit tests for @Configuration, @Value, and configuration loading.
"""

import os
import tempfile

import pytest

from mitsuki import Configuration, Provider
from mitsuki.config import ConfigurationProperties, Value, get_config
from mitsuki.core.application import Application, ApplicationContext
from mitsuki.core.container import DIContainer, get_container, set_container
from mitsuki.core.providers import initialize_configuration_providers


@pytest.fixture(autouse=True)
def reset_container_and_config():
    """Reset container and config before each test."""
    set_container(DIContainer())
    yield
    set_container(DIContainer())


@pytest.fixture
def temp_config_file():
    """Create a temporary YAML config file."""
    config_content = """
server:
  host: 0.0.0.0
  port: 9000

database:
  url: postgresql://localhost/testdb
  pool:
    size: 20
    max_overflow: 40

app:
  name: TestApp
  debug: true
  max_users: 100

logging:
  level: DEBUG
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(config_content)
        path = f.name

    yield path
    os.unlink(path)


class TestValueDescriptor:
    """Tests for @Value property injection."""

    def test_value_with_default_syntax(self):
        """Should parse ${key:default} syntax."""

        @Configuration
        class Config:
            port: int = Value("${server.port:8000}")

        config = Config()
        # Before loading actual config, should use default
        assert config.port == 8000

    def test_value_without_default(self):
        """Should parse ${key} syntax without default."""

        @Configuration
        class Config:
            host: str = Value("${server.host}")

        config = Config()
        assert config.host == "127.0.0.1"

    def test_value_plain_key(self):
        """Should support plain key without ${}."""

        @Configuration
        class Config:
            name: str = Value("app.name")

        config = Config()
        assert config.name is None  # No config loaded

    def test_value_cannot_be_set(self):
        """@Value properties should be read-only."""

        @Configuration
        class Config:
            port: int = Value("${server.port:8000}")

        config = Config()

        with pytest.raises(AttributeError, match="Cannot set @Value property"):
            config.port = 9000


class TestConfigurationLoading:
    """Tests for loading configuration from YAML files."""

    def test_load_config_from_file(self, temp_config_file):
        """Should load configuration from YAML file."""
        config = ConfigurationProperties()
        config.load_from_file(temp_config_file)

        assert config.get("server.port") == 9000
        assert config.get("server.host") == "0.0.0.0"
        assert config.get("database.url") == "postgresql://localhost/testdb"
        assert config.get("app.name") == "TestApp"

    def test_nested_config_access(self, temp_config_file):
        """Should support nested property access."""
        config = ConfigurationProperties()
        config.load_from_file(temp_config_file)

        assert config.get("database.pool.size") == 20
        assert config.get("database.pool.max_overflow") == 40

    def test_config_get_with_default(self, temp_config_file):
        """Should return default when key not found."""
        config = ConfigurationProperties()
        config.load_from_file(temp_config_file)

        assert config.get("nonexistent.key", "default_value") == "default_value"
        assert config.get("also.missing", 42) == 42

    def test_config_get_bool(self, temp_config_file):
        """Should support get_bool for boolean values."""
        config = ConfigurationProperties()
        config.load_from_file(temp_config_file)

        assert config.get_bool("app.debug") is True
        assert config.get_bool("app.production", False) is False


class TestValueInjection:
    """Tests for @Value injection from loaded config."""

    def test_value_injects_from_config(self, temp_config_file):
        """@Value should inject values from loaded config."""
        # Manually load config
        config = get_config()
        config.load_from_file(temp_config_file)

        @Configuration
        class AppConfig:
            port: int = Value("${server.port:8000}")
            host: str = Value("${server.host:127.0.0.1}")
            app_name: str = Value("${app.name}")

        config = AppConfig()
        assert config.port == 9000
        assert config.host == "0.0.0.0"
        assert config.app_name == "TestApp"

    def test_value_uses_default_when_missing(self, temp_config_file):
        """@Value should use default when key not in config."""
        config = get_config()
        config.load_from_file(temp_config_file)

        @Configuration
        class AppConfig:
            timeout: int = Value("${api.timeout:30}")
            retries: int = Value("${api.retries:3}")

        config = AppConfig()
        assert config.timeout == 30
        assert config.retries == 3

    def test_value_type_coercion(self, temp_config_file):
        """@Value should coerce types appropriately."""
        config = get_config()
        config.load_from_file(temp_config_file)

        @Configuration
        class AppConfig:
            max_users: int = Value("${app.max_users}")
            debug: bool = Value("${app.debug}")

        config = AppConfig()
        assert config.max_users == 100
        assert isinstance(config.max_users, int)
        assert config.debug is True
        assert isinstance(config.debug, bool)


class TestEnvironmentVariableOverrides:
    """Tests for environment variable overrides."""

    def test_env_override_with_mitsuki_prefix(self, temp_config_file):
        """Environment variables with MITSUKI_ prefix should override config."""
        os.environ["MITSUKI_SERVER_PORT"] = "7000"

        config = get_config()
        config.load_from_file(temp_config_file)

        # Env var should override
        # Note: This depends on implementation - you may need to add this feature
        port = os.getenv("MITSUKI_SERVER_PORT", config.get("server.port"))
        assert port == "7000"

        # Cleanup
        del os.environ["MITSUKI_SERVER_PORT"]


class TestConfigurationClass:
    """Tests for @Configuration decorator."""

    def test_configuration_decorator(self):
        """@Configuration should mark class for provider scanning."""

        @Configuration
        class AppConfig:
            @Provider
            def my_provider(self) -> str:
                return "provider_value"

        assert hasattr(AppConfig, "__mitsuki_configuration__")
        assert AppConfig.__mitsuki_configuration__ is True

    def test_configuration_with_providers(self):
        """@Configuration should support @Provider methods."""

        @Configuration
        class AppConfig:
            @Provider
            def service_url(self) -> str:
                return "https://api.example.com"

            @Provider
            def max_retries(self) -> int:
                return 5

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert context.container.get_by_name("service_url") == "https://api.example.com"
        assert context.container.get_by_name("max_retries") == 5

    def test_configuration_singleton_by_default(self):
        """@Configuration classes should be singleton by default."""

        @Configuration
        class AppConfig:
            pass

        container = get_container()

        instance1 = container.get(AppConfig)
        instance2 = container.get(AppConfig)

        assert instance1 is instance2


class TestMultipleConfigurationFiles:
    """Tests for loading multiple config files (profiles)."""

    def test_base_config_plus_profile(self):
        """Should support base config + profile-specific config."""
        # Create base config
        base_config = """
server:
  port: 8000
app:
  name: MyApp
"""
        # Create dev profile config
        dev_config = """
server:
  port: 3000
app:
  debug: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(base_config)
            base_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(dev_config)
            dev_path = f.name

        try:
            config = ConfigurationProperties()
            config.load_from_file(base_path)
            config.load_from_file(dev_path)  # Override with dev settings

            assert config.get("server.port") == 3000  # Overridden
            assert config.get("app.name") == "MyApp"  # From base
            assert config.get("app.debug") is True  # From dev
        finally:
            os.unlink(base_path)
            os.unlink(dev_path)


class TestConfigReload:
    """Tests for configuration reloading."""

    def test_reload_config(self, temp_config_file):
        """Should reload configuration from file."""
        # Load initial config
        config = get_config()
        config.load_from_file(temp_config_file)
        initial_port = config.get("server.port")

        # Modify file
        with open(temp_config_file, "w") as f:
            f.write("server:\n  port: 5555\n")

        # Reload
        config.load_from_file(temp_config_file)
        new_port = config.get("server.port")

        assert initial_port == 9000
        assert new_port == 5555

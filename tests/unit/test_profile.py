"""
Unit tests for @Profile functionality.
Tests profile-based conditional provider registration and environment switching.
"""

import os

import pytest

from mitsuki import Application, Configuration, Profile, Provider, Service
from mitsuki.core.application import ApplicationContext
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.providers import initialize_configuration_providers


@pytest.fixture(autouse=True)
def reset_container_and_env():
    """Reset the global container and environment before each test."""
    # Save original profile
    original_profile = os.environ.get("MITSUKI_PROFILE")

    # Reset container
    set_container(DIContainer())

    yield

    # Restore original profile
    if original_profile is not None:
        os.environ["MITSUKI_PROFILE"] = original_profile
    elif "MITSUKI_PROFILE" in os.environ:
        del os.environ["MITSUKI_PROFILE"]

    # Reset container again
    set_container(DIContainer())


class TestProfileActivation:
    """Tests for profile activation and detection."""

    def test_profile_single_match(self):
        """Configuration should be active when profile matches."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def test_provider(self) -> str:
                return "dev"

        assert DevConfig.__mitsuki_profile_active__ is True

    def test_profile_no_match(self):
        """Configuration should be inactive when profile doesn't match."""
        os.environ["MITSUKI_PROFILE"] = "production"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def test_provider(self) -> str:
                return "dev"

        assert DevConfig.__mitsuki_profile_active__ is False

    def test_profile_multiple_options(self):
        """Configuration should be active if any profile matches."""
        os.environ["MITSUKI_PROFILE"] = "test"

        @Configuration
        @Profile("development", "test", "staging")
        class NonProdConfig:
            @Provider
            def test_provider(self) -> str:
                return "non-prod"

        assert NonProdConfig.__mitsuki_profile_active__ is True

    def test_profile_default_when_not_set(self):
        """Profile should default to 'default' when not set."""
        if "MITSUKI_PROFILE" in os.environ:
            del os.environ["MITSUKI_PROFILE"]

        @Configuration
        @Profile("default")
        class DefaultConfig:
            @Provider
            def test_provider(self) -> str:
                return "default"

        assert DefaultConfig.__mitsuki_profile_active__ is True


class TestProfileProviderRegistration:
    """Tests for profile-based provider registration."""

    def test_active_profile_providers_registered(self):
        """Providers from active profile should be registered."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def dev_provider(self) -> str:
                return "dev value"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "dev_provider" in context.container._components_by_name
        assert context.container.get_by_name("dev_provider") == "dev value"

    def test_inactive_profile_providers_not_registered(self):
        """Providers from inactive profile should NOT be registered."""
        os.environ["MITSUKI_PROFILE"] = "production"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def dev_provider(self) -> str:
                return "dev value"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "dev_provider" not in context.container._components_by_name

    def test_profile_provider_switching(self):
        """Different profiles should register different providers with same name."""

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def database_url(self) -> str:
                return "sqlite:///dev.db"

        @Configuration
        @Profile("production")
        class ProdConfig:
            @Provider
            def database_url(self) -> str:
                return "postgresql://prod-server/db"

        # Test development profile
        os.environ["MITSUKI_PROFILE"] = "development"

        set_container(DIContainer())

        @Configuration
        @Profile("development")
        class DevConfig2:
            @Provider
            def database_url(self) -> str:
                return "sqlite:///dev.db"

        @Configuration
        @Profile("production")
        class ProdConfig2:
            @Provider
            def database_url(self) -> str:
                return "postgresql://prod-server/db"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        dev_url = context.container.get_by_name("database_url")
        assert dev_url == "sqlite:///dev.db"

    def test_multiple_profiles_multiple_providers(self):
        """Multiple profile-specific configs should each register their providers."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def dev_setting(self) -> str:
                return "dev"

        @Configuration
        @Profile("test")
        class TestConfig:
            @Provider
            def test_setting(self) -> str:
                return "test"

        @Configuration
        @Profile("development", "test")
        class SharedConfig:
            @Provider
            def shared_setting(self) -> str:
                return "shared"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        # Dev providers should be registered
        assert "dev_setting" in context.container._components_by_name
        assert context.container.get_by_name("dev_setting") == "dev"

        # Test providers should NOT be registered
        assert "test_setting" not in context.container._components_by_name

        # Shared providers should be registered (matches dev)
        assert "shared_setting" in context.container._components_by_name
        assert context.container.get_by_name("shared_setting") == "shared"


class TestProfileOnProviderMethods:
    """Tests for @Profile decorator on individual @Provider methods."""

    def test_active_profile_provider_method_registered(self):
        """@Provider methods with active @Profile should be registered."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        class Config:
            @Provider
            @Profile("development")
            def dev_provider(self) -> str:
                return "dev value"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "dev_provider" in context.container._components_by_name
        assert context.container.get_by_name("dev_provider") == "dev value"

    def test_inactive_profile_provider_method_not_registered(self):
        """@Provider methods with inactive @Profile should NOT be registered."""
        os.environ["MITSUKI_PROFILE"] = "production"

        @Configuration
        class Config:
            @Provider
            @Profile("development")
            def dev_provider(self) -> str:
                return "dev value"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "dev_provider" not in context.container._components_by_name

    def test_multiple_providers_with_different_profiles(self):
        """Multiple @Provider methods with different @Profile decorators."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        class Config:
            @Provider
            @Profile("development")
            def dev_database(self) -> str:
                return "sqlite:///dev.db"

            @Provider
            @Profile("production")
            def prod_database(self) -> str:
                return "postgresql://prod"

            @Provider
            def shared_setting(self) -> str:
                return "shared"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        # Dev provider should be registered
        assert "dev_database" in context.container._components_by_name
        assert context.container.get_by_name("dev_database") == "sqlite:///dev.db"

        # Prod provider should NOT be registered
        assert "prod_database" not in context.container._components_by_name

        # Shared provider should be registered (no profile = always active)
        assert "shared_setting" in context.container._components_by_name
        assert context.container.get_by_name("shared_setting") == "shared"


class TestProfileWithInjection:
    """Tests for profile-based providers being injected into services."""

    def test_inject_profile_specific_provider(self):
        """Profile-specific providers should be injectable into services."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def api_timeout(self) -> int:
                return 5

        @Configuration
        @Profile("production")
        class ProdConfig:
            @Provider
            def api_timeout(self) -> int:
                return 60

        @Service()
        class ApiService:
            def __init__(self, api_timeout: int):
                self.timeout = api_timeout

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        service = context.container.get(ApiService)
        assert service.timeout == 5  # Dev timeout

    def test_profile_switch_changes_injection(self):
        """Switching profiles should inject different provider values."""
        # Test with development profile
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig1:
            @Provider
            def message(self) -> str:
                return "DEV"

        @Service()
        class MessageService1:
            def __init__(self, message: str):
                self.msg = message

        @Application
        class App1:
            pass

        context1 = ApplicationContext(App1)
        initialize_configuration_providers()
        service1 = context1.container.get(MessageService1)

        assert service1.msg == "DEV"

        # Reset and test with production profile
        os.environ["MITSUKI_PROFILE"] = "production"
        set_container(DIContainer())

        @Configuration
        @Profile("production")
        class ProdConfig2:
            @Provider
            def message(self) -> str:
                return "PROD"

        @Service()
        class MessageService2:
            def __init__(self, message: str):
                self.msg = message

        @Application
        class App2:
            pass

        context2 = ApplicationContext(App2)
        initialize_configuration_providers()
        service2 = context2.container.get(MessageService2)

        assert service2.msg == "PROD"


class TestProfileConfiguration:
    """Tests for @Configuration classes with @Profile."""

    def test_configuration_without_profile(self):
        """@Configuration without @Profile should always be active."""
        os.environ["MITSUKI_PROFILE"] = "any-profile"

        @Configuration
        class AlwaysActiveConfig:
            @Provider
            def always_available(self) -> str:
                return "available"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        assert "always_available" in context.container._components_by_name
        assert context.container.get_by_name("always_available") == "available"

    def test_profile_metadata_on_configuration(self):
        """@Profile should set correct metadata on @Configuration classes."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile("development")
        class DevConfig:
            pass

        assert hasattr(DevConfig, "__mitsuki_profiles__")
        assert DevConfig.__mitsuki_profiles__ == ("development",)
        assert hasattr(DevConfig, "__mitsuki_profile_active__")
        assert DevConfig.__mitsuki_profile_active__ is True

    def test_profile_with_multiple_configurations(self):
        """Multiple @Configuration classes can have different profiles."""
        os.environ["MITSUKI_PROFILE"] = "staging"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def env_name(self) -> str:
                return "dev"

        @Configuration
        @Profile("staging")
        class StagingConfig:
            @Provider
            def env_name(self) -> str:
                return "staging"

        @Configuration
        @Profile("production")
        class ProdConfig:
            @Provider
            def env_name(self) -> str:
                return "prod"

        @Application
        class App:
            pass

        context = ApplicationContext(App)

        # Check which configs are active
        configs = context.container.get_all_configurations()
        active_configs = [
            c.name
            for c in configs
            if hasattr(c.cls, "__mitsuki_profile_active__")
            and c.cls.__mitsuki_profile_active__
        ]

        assert "StagingConfig" in active_configs
        assert "DevConfig" not in active_configs
        assert "ProdConfig" not in active_configs

        initialize_configuration_providers()

        # Only staging provider should be registered
        assert context.container.get_by_name("env_name") == "staging"


class TestProfileEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_profile_decorator(self):
        """@Profile() with no profiles should never be active."""
        os.environ["MITSUKI_PROFILE"] = "development"

        @Configuration
        @Profile()
        class NeverActiveConfig:
            @Provider
            def never_available(self) -> str:
                return "never"

        assert hasattr(NeverActiveConfig, "__mitsuki_profile_active__")
        assert NeverActiveConfig.__mitsuki_profile_active__ is False

    def test_profile_case_sensitivity(self):
        """Profile matching should be case-sensitive."""
        os.environ["MITSUKI_PROFILE"] = "Development"  # Capital D

        @Configuration
        @Profile("development")  # Lowercase
        class DevConfig:
            @Provider
            def test_provider(self) -> str:
                return "test"

        # Should NOT match (case-sensitive)
        assert DevConfig.__mitsuki_profile_active__ is False

    def test_profile_with_special_characters(self):
        """Profiles can contain special characters."""
        os.environ["MITSUKI_PROFILE"] = "dev-local-2024"

        @Configuration
        @Profile("dev-local-2024")
        class SpecialConfig:
            @Provider
            def test_provider(self) -> str:
                return "special"

        assert SpecialConfig.__mitsuki_profile_active__ is True

    def test_same_provider_name_different_profiles(self):
        """Same provider name in different profiles - last one wins in active profile."""
        os.environ["MITSUKI_PROFILE"] = "production"

        @Configuration
        @Profile("development")
        class DevConfig:
            @Provider
            def shared_provider(self) -> str:
                return "dev-value"

        @Configuration
        @Profile("production")
        class ProdConfig:
            @Provider
            def shared_provider(self) -> str:
                return "prod-value"

        @Application
        class App:
            pass

        context = ApplicationContext(App)
        initialize_configuration_providers()

        # Should get production value since that profile is active
        assert context.container.get_by_name("shared_provider") == "prod-value"

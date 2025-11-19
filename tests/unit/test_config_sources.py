"""
Tests for configuration source tracking and logging.
"""

import os
import tempfile
from pathlib import Path

from mitsuki.config.properties import (
    ConfigurationProperties,
    log_config_sources,
    reload_config,
)


class TestConfigSourceTracking:
    """Tests for tracking configuration sources."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear any environment variables
        for key in list(os.environ.keys()):
            if key.startswith("MITSUKI_"):
                del os.environ[key]

    def teardown_method(self):
        """Clean up after tests."""
        for key in list(os.environ.keys()):
            if key.startswith("MITSUKI_"):
                del os.environ[key]
        reload_config()

    def test_tracks_default_configuration(self):
        """Test that default configuration sources are tracked."""
        config = ConfigurationProperties()
        sources = config.get_config_sources()

        # Should have sources from defaults.yml
        assert "server.type" in sources
        assert sources["server.type"] == "default configuration"
        assert "logging.level" in sources
        assert sources["logging.level"] == "default configuration"

    def test_tracks_application_yml_overrides(self):
        """Test that application.yml overrides are tracked."""
        # Create temporary application.yml
        with tempfile.TemporaryDirectory() as tmpdir:
            app_config = Path(tmpdir) / "application.yml"
            app_config.write_text(
                """
server:
  type: uvicorn
  workers: 4
custom:
  value: test
"""
            )

            # Change to temp directory
            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = ConfigurationProperties()
                sources = config.get_config_sources()

                # Check that application.yml values are tracked
                assert "server.type" in sources
                assert sources["server.type"] == "application.yml"
                assert "server.workers" in sources
                assert sources["server.workers"] == "application.yml"
                assert "custom.value" in sources
                assert sources["custom.value"] == "application.yml"

                # Default values should still be tracked
                assert "logging.format" in sources
                assert sources["logging.format"] == "default configuration"
            finally:
                os.chdir(original_dir)

    def test_tracks_environment_variable_fallbacks(self):
        """Test that environment variables work as fallbacks when key not in config."""
        # Set env vars for keys that don't exist in defaults.yml
        os.environ["MITSUKI_CUSTOM_API_KEY"] = "test-key"
        os.environ["MITSUKI_CUSTOM_TIMEOUT"] = "30"

        config = ConfigurationProperties()

        # Access the config values to trigger env var tracking
        config.get("custom.api_key")
        config.get("custom.timeout")

        sources = config.get_config_sources()

        # Environment variables should be tracked as fallbacks
        assert "custom.api_key" in sources
        assert (
            sources["custom.api_key"] == "environment variable (MITSUKI_CUSTOM_API_KEY)"
        )
        assert "custom.timeout" in sources
        assert (
            sources["custom.timeout"] == "environment variable (MITSUKI_CUSTOM_TIMEOUT)"
        )

    def test_config_files_override_environment_variables(self):
        """Test that config files take precedence over environment variables."""
        # Set env var that conflicts with defaults.yml
        os.environ["MITSUKI_SERVER_TYPE"] = "uvicorn"

        config = ConfigurationProperties()

        # server.type exists in defaults.yml as "granian"
        value = config.get("server.type")
        assert value == "granian"  # Config file wins, not env var

        sources = config.get_config_sources()
        # Should show it came from default config, not env var
        assert sources["server.type"] == "default configuration"

    def test_tracks_profile_specific_configuration(self):
        """Test that profile-specific configuration is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create application.yml
            app_config = Path(tmpdir) / "application.yml"
            app_config.write_text(
                """
server:
  type: uvicorn
"""
            )

            # Create application-dev.yml
            dev_config = Path(tmpdir) / "application-dev.yml"
            dev_config.write_text(
                """
server:
  workers: 2
logging:
  level: DEBUG
"""
            )

            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = ConfigurationProperties(profile="dev")
                sources = config.get_config_sources()

                # Base config should be tracked
                assert "server.type" in sources
                assert sources["server.type"] == "application.yml"

                # Profile config should override
                assert "server.workers" in sources
                assert sources["server.workers"] == "application-dev.yml"
                assert "logging.level" in sources
                assert sources["logging.level"] == "application-dev.yml"
            finally:
                os.chdir(original_dir)

    def test_get_config_sources_returns_sorted_dict(self):
        """Test that get_config_sources returns sorted dictionary."""
        config = ConfigurationProperties()
        sources = config.get_config_sources()

        # Should be a dict
        assert isinstance(sources, dict)

        # Should be sorted by key
        keys = list(sources.keys())
        assert keys == sorted(keys)


class MockLogger:
    """Mock logger for testing log output."""

    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)


class TestLogConfigSources:
    """Tests for log_config_sources function."""

    def setup_method(self):
        """Set up test fixtures."""
        for key in list(os.environ.keys()):
            if key.startswith("MITSUKI_"):
                del os.environ[key]

    def teardown_method(self):
        """Clean up after tests."""
        for key in list(os.environ.keys()):
            if key.startswith("MITSUKI_"):
                del os.environ[key]
        reload_config()

    def test_log_config_sources_groups_by_source(self):
        """Test that log_config_sources groups configs by source."""
        config = ConfigurationProperties()
        logger = MockLogger()

        log_config_sources(config, logger, max_cols=2)

        # Should have logged messages
        assert len(logger.messages) > 0

        # Should have "Configuration sources:" header
        assert any("Configuration sources:" in msg for msg in logger.messages)

        # Should have source group headers
        assert any("[default configuration]" in msg for msg in logger.messages)

    def test_log_config_sources_creates_table(self):
        """Test that log_config_sources creates table output."""
        config = ConfigurationProperties()
        logger = MockLogger()

        log_config_sources(config, logger, max_cols=3)

        # Should have table borders
        assert any("┌" in msg and "┐" in msg for msg in logger.messages)
        assert any("└" in msg and "┘" in msg for msg in logger.messages)
        assert any("│" in msg for msg in logger.messages)

    def test_log_config_sources_with_mixed_sources(self):
        """Test log_config_sources with multiple source types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app_config = Path(tmpdir) / "application.yml"
            app_config.write_text(
                """
server:
  type: granian
"""
            )

            # Set env var for key that doesn't exist in config files
            os.environ["MITSUKI_CUSTOM_SETTING"] = "test-value"

            original_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                config = ConfigurationProperties()
                config.get("custom.setting")  # Trigger env var tracking

                logger = MockLogger()
                log_config_sources(config, logger, max_cols=2)

                # Should have all three source types
                assert any("[default configuration]" in msg for msg in logger.messages)
                assert any("[application.yml]" in msg for msg in logger.messages)
                assert any("environment variable" in msg for msg in logger.messages)
            finally:
                os.chdir(original_dir)

    def test_log_config_sources_max_cols_parameter(self):
        """Test that max_cols parameter controls column count."""
        config = ConfigurationProperties()
        logger = MockLogger()

        log_config_sources(config, logger, max_cols=1)

        # With max_cols=1, each config should be on its own line
        table_lines = [msg for msg in logger.messages if "│" in msg and "─" not in msg]

        # Each line should have only one config key (plus borders)
        for line in table_lines:
            # Count the number of spaces between borders to verify single column
            content = line.strip("│").strip()
            # Single column should not have excessive spacing patterns
            assert line.count("│") == 2  # Start and end borders only

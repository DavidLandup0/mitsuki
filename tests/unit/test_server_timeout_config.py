"""
Tests for server timeout configuration.
"""

from unittest.mock import MagicMock, Mock, patch

from mitsuki.core.server import _start_granian, _start_uvicorn


def test_uvicorn_uses_timeout_from_config():
    """Test that uvicorn receives timeout from config."""
    with (
        patch("mitsuki.core.server.uvicorn") as mock_uvicorn,
        patch("mitsuki.core.server.get_config") as mock_get_config,
    ):
        # Mock config with timeout
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "logging.format": "%(message)s",
            "server.timeout": 120,
        }.get(key, default)
        mock_get_config.return_value = mock_config

        # Create a mock server
        server = Mock()

        _start_uvicorn(server, "0.0.0.0", 8000, "info", True)

        # Verify uvicorn.run was called with timeout_keep_alive
        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs["timeout_keep_alive"] == 120


def test_uvicorn_no_timeout_when_not_configured():
    """Test that uvicorn doesn't receive timeout when not configured."""
    with (
        patch("mitsuki.core.server.uvicorn") as mock_uvicorn,
        patch("mitsuki.core.server.get_config") as mock_get_config,
    ):
        # Mock config without timeout
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "logging.format": "%(message)s",
        }.get(key, default)
        mock_get_config.return_value = mock_config

        server = Mock()

        _start_uvicorn(server, "0.0.0.0", 8000, "info", True)

        # Verify uvicorn.run was called without timeout_keep_alive
        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert "timeout_keep_alive" not in call_kwargs


def test_granian_uses_timeout_from_config():
    """Test that granian receives timeout from config."""
    with (
        patch("mitsuki.core.server.Granian") as mock_granian_class,
        patch("mitsuki.core.server.get_config") as mock_get_config,
        patch("mitsuki.core.server.get_granian_log_config") as mock_log_config,
        patch("mitsuki.web.route_builder.inspect.getmodule") as mock_getmodule,
    ):
        # Mock config with timeout
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "logging.format": "%(message)s",
            "server.timeout": 90,
        }.get(key, default)
        mock_get_config.return_value = mock_config
        mock_log_config.return_value = {}

        # Mock module
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"
        mock_getmodule.return_value = mock_module

        # Mock granian instance
        mock_granian_instance = MagicMock()
        mock_granian_class.return_value = mock_granian_instance

        # Mock application class
        app_class = type("TestApp", (), {"__mitsuki_app__": Mock()})

        _start_granian(app_class, "0.0.0.0", 8000, 1, "info", True)

        # Verify Granian was called with http1_keep_alive
        mock_granian_class.assert_called_once()
        call_kwargs = mock_granian_class.call_args[1]
        assert call_kwargs["http1_keep_alive"] == 90


def test_granian_no_timeout_when_not_configured():
    """Test that granian doesn't receive timeout when not configured."""
    with (
        patch("mitsuki.core.server.Granian") as mock_granian_class,
        patch("mitsuki.core.server.get_config") as mock_get_config,
        patch("mitsuki.core.server.get_granian_log_config") as mock_log_config,
        patch("mitsuki.web.route_builder.inspect.getmodule") as mock_getmodule,
    ):
        # Mock config without timeout
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "logging.format": "%(message)s",
        }.get(key, default)
        mock_get_config.return_value = mock_config
        mock_log_config.return_value = {}

        # Mock module
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"
        mock_getmodule.return_value = mock_module

        # Mock granian instance
        mock_granian_instance = MagicMock()
        mock_granian_class.return_value = mock_granian_instance

        # Mock application class
        app_class = type("TestApp", (), {"__mitsuki_app__": Mock()})

        _start_granian(app_class, "0.0.0.0", 8000, 1, "info", True)

        # Verify Granian was called without http1_keep_alive
        mock_granian_class.assert_called_once()
        call_kwargs = mock_granian_class.call_args[1]
        assert "http1_keep_alive" not in call_kwargs

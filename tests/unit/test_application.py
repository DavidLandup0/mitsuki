"""
Tests for @Application decorator and application startup.
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from mitsuki import Application
from mitsuki.core.application import ApplicationContext
from mitsuki.core.enums import StereotypeType
from mitsuki.core.server import _start_granian, _start_uvicorn


class TestApplicationStartup:
    """Tests for application startup functionality."""

    def test_start_uvicorn_signature(self):
        """Verify _start_uvicorn has correct signature."""
        sig = inspect.signature(_start_uvicorn)
        params = list(sig.parameters.keys())

        # Should have: server, host, port, log_level, access_log
        assert len(params) == 5
        assert params[0] == "server"
        assert params[1] == "host"
        assert params[2] == "port"
        assert params[3] == "log_level"
        assert params[4] == "access_log"

    def test_start_granian_signature(self):
        """Verify _start_granian has correct signature."""
        sig = inspect.signature(_start_granian)
        params = list(sig.parameters.keys())

        # Should have: application_class, host, port, workers, log_level, access_log
        assert len(params) == 6
        assert params[0] == "application_class"
        assert params[1] == "host"
        assert params[2] == "port"
        assert params[3] == "workers"
        assert params[4] == "log_level"
        assert params[5] == "access_log"

    def test_application_decorator_marks_class(self):
        """@Application should mark class with metadata."""

        @Application
        class TestApp:
            pass

        assert hasattr(TestApp, "__mitsuki_application__")
        assert TestApp.__mitsuki_application__ is True
        assert TestApp._stereotype_subtype == StereotypeType.CONFIGURATION

    def test_application_creates_run_method(self):
        """@Application should add run() class method."""

        @Application
        class TestApp:
            pass

        assert hasattr(TestApp, "run")
        assert callable(TestApp.run)


class TestApplicationScanPackages:
    """Tests for @Application scan_packages parameter."""

    def test_application_with_scan_packages_parameter(self):
        """@Application should accept scan_packages parameter."""

        @Application(scan_packages=["app.controllers", "app.services"])
        class TestApp:
            pass

        assert hasattr(TestApp, "__mitsuki_application__")
        assert TestApp.__mitsuki_application__ is True
        assert hasattr(TestApp, "__mitsuki_scan_packages__")
        assert TestApp.__mitsuki_scan_packages__ == ["app.controllers", "app.services"]

    def test_application_without_scan_packages(self):
        """@Application without scan_packages should set it to None."""

        @Application
        class TestApp:
            pass

        assert hasattr(TestApp, "__mitsuki_scan_packages__")
        assert TestApp.__mitsuki_scan_packages__ is None

    def test_application_with_empty_scan_packages(self):
        """@Application with empty list should store empty list."""

        @Application(scan_packages=[])
        class TestApp:
            pass

        assert TestApp.__mitsuki_scan_packages__ == []

    def test_application_with_single_package(self):
        """@Application with single package should work."""

        @Application(scan_packages=["app"])
        class TestApp:
            pass

        assert TestApp.__mitsuki_scan_packages__ == ["app"]


BOOT_STEPS = [
    "scan_components",
    "initialize_configuration_providers",
    "initialize_database",
    "initialize_metrics",
    "get_all_controllers",
    "register_openapi_endpoints",
    "create_server",
    "_start_uvicorn",
    "_start_granian",
    "_start_socketify",
]


def _config(**overrides):
    values = {
        "logging.level": "INFO",
        "logging.format": "%(message)s",
        "server.type": "uvicorn",
        "server.workers": 2,
        "server.host": "config-host",
        "server.port": 9000,
    }
    values.update(overrides)
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    config.get_bool.return_value = False
    return config


@pytest.fixture
def boot(isolated_container):
    """Replace every boot step with a mock recording calls on one manager."""
    manager = Mock()
    manager.attach_mock(AsyncMock(), "initialize_database")
    manager.get_all_controllers.return_value = ["controller"]
    manager.create_server.return_value = "server"
    manager.config = _config()

    with (
        patch("mitsuki.core.application.configure_logging"),
        patch(
            "mitsuki.core.application.get_config",
            side_effect=lambda: manager.config,
        ),
        patch.object(
            ApplicationContext, "initialize_metrics", manager.initialize_metrics
        ),
    ):
        patches = [
            patch(f"mitsuki.core.application.{step}", getattr(manager, step))
            for step in BOOT_STEPS
            if step != "initialize_metrics"
        ]
        for step_patch in patches:
            step_patch.start()
        try:
            yield manager
        finally:
            for step_patch in patches:
                step_patch.stop()


def _steps(manager):
    return [name for name, _, _ in manager.mock_calls if name in BOOT_STEPS]


class TestContextStart:
    """Tests for ApplicationContext.start."""

    def test_steps_run_in_order(self, boot):
        @Application
        class App:
            pass

        ApplicationContext(App).start(host="h", port=1)

        assert _steps(boot) == [
            "initialize_database",
            "initialize_metrics",
            "get_all_controllers",
            "register_openapi_endpoints",
            "create_server",
            "_start_uvicorn",
        ]

    def test_controllers_and_server_are_kept_on_the_context(self, boot):
        @Application
        class App:
            pass

        context = ApplicationContext(App)
        context.start(host="h", port=1)

        assert context.controllers == ["controller"]
        assert context._server == "server"
        boot.register_openapi_endpoints.assert_called_once_with(context, boot.config)
        boot.create_server.assert_called_once_with(context)

    def test_uvicorn_receives_server_and_settings(self, boot):
        @Application
        class App:
            pass

        ApplicationContext(App).start(host="h", port=1)

        boot._start_uvicorn.assert_called_once_with("server", "h", 1, "info", False)

    def test_granian_receives_application_class_and_workers(self, boot):
        boot.config = _config(**{"server.type": "GRANIAN"})

        @Application
        class App:
            pass

        ApplicationContext(App).start(host="h", port=1)

        boot._start_granian.assert_called_once_with(App, "h", 1, 2, "info", False)
        boot._start_uvicorn.assert_not_called()

    def test_socketify_receives_server_and_workers(self, boot):
        boot.config = _config(**{"server.type": "socketify"})

        @Application
        class App:
            pass

        ApplicationContext(App).start(host="h", port=1)

        boot._start_socketify.assert_called_once_with(
            "server", "h", 1, 2, "info", False
        )
        boot._start_uvicorn.assert_not_called()


class TestApplicationRun:
    """Tests for the run() classmethod attached by @Application."""

    def test_steps_run_in_order(self, boot):
        @Application(scan_packages=["pkg"])
        class App:
            pass

        App.run(host="h", port=1)

        assert _steps(boot) == [
            "scan_components",
            "initialize_configuration_providers",
            "initialize_database",
            "initialize_metrics",
            "get_all_controllers",
            "register_openapi_endpoints",
            "create_server",
            "_start_uvicorn",
        ]
        boot.scan_components.assert_called_once_with(App, scan_packages=["pkg"])

    def test_host_and_port_default_to_config(self, boot):
        @Application
        class App:
            pass

        App.run()

        boot._start_uvicorn.assert_called_once_with(
            "server", "config-host", 9000, "info", False
        )

    def test_class_attributes_override_config(self, boot):
        @Application
        class App:
            host = "class-host"
            port = 7000

        App.run()

        boot._start_uvicorn.assert_called_once_with(
            "server", "class-host", 7000, "info", False
        )

    def test_arguments_override_class_attributes(self, boot):
        @Application
        class App:
            host = "class-host"
            port = 7000

        App.run(host="arg-host", port=6000)

        boot._start_uvicorn.assert_called_once_with(
            "server", "arg-host", 6000, "info", False
        )


class TestAsyncAppFactory:
    """Tests for the ASGI factory used by Granian workers."""

    def test_steps_run_in_order(self, boot):
        @Application(scan_packages=["pkg"])
        class App:
            pass

        app = asyncio.run(App.__mitsuki_create_app__())

        assert app == "server"
        assert _steps(boot) == [
            "scan_components",
            "initialize_configuration_providers",
            "initialize_database",
            "initialize_metrics",
            "get_all_controllers",
            "register_openapi_endpoints",
            "create_server",
        ]
        boot.scan_components.assert_called_once_with(App, scan_packages=["pkg"])

    def test_app_is_created_once(self, boot):
        @Application
        class App:
            pass

        async def create_twice():
            return (
                await App.__mitsuki_create_app__(),
                await App.__mitsuki_create_app__(),
            )

        first, second = asyncio.run(create_twice())

        assert first is second
        boot.create_server.assert_called_once()

    def test_asgi_entry_point_delegates_to_created_app(self, boot):
        server = AsyncMock()
        boot.create_server.return_value = server

        @Application
        class App:
            pass

        async def serve_twice():
            await App.__mitsuki_app__("scope-1", "receive", "send")
            await App.__mitsuki_app__("scope-2", "receive", "send")

        asyncio.run(serve_twice())

        assert server.await_args_list == [
            call("scope-1", "receive", "send"),
            call("scope-2", "receive", "send"),
        ]
        boot.create_server.assert_called_once()

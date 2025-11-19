"""
Tests for @Application decorator and application startup.
"""

import inspect

from mitsuki import Application
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
        assert hasattr(TestApp, "__mitsuki_configuration__")
        assert TestApp.__mitsuki_configuration__ is True

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

"""
Tests for scan_components discovering and importing application modules.
"""

import importlib
import logging
import sys
import textwrap
import uuid

import pytest

from mitsuki.core.scanner import scan_components

APP_MODULE = """
from mitsuki import Application


@Application
class App:
    pass
"""

GREETER_MODULE = """
from mitsuki import Service


@Service()
class Greeter:
    pass
"""

CLOCK_MODULE = """
from mitsuki import Component


@Component()
class Clock:
    pass
"""


def _write(path, source=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source))


@pytest.fixture
def app_package(tmp_path, monkeypatch, isolated_container):
    """An importable application package with components in nested modules."""
    name = f"scanapp_{uuid.uuid4().hex}"
    root = tmp_path / name

    _write(root / "__init__.py")
    _write(root / "app.py", APP_MODULE)
    _write(root / "services" / "__init__.py")
    _write(root / "services" / "greeter.py", GREETER_MODULE)
    _write(root / "clock.py", CLOCK_MODULE)

    monkeypatch.syspath_prepend(str(tmp_path))
    yield name, root

    for module_name in [m for m in sys.modules if m.split(".")[0] == name]:
        del sys.modules[module_name]


def _app_class(package_name):
    return importlib.import_module(f"{package_name}.app").App


class TestRecursiveScan:
    def test_components_in_nested_modules_are_registered(
        self, app_package, isolated_container
    ):
        name, _ = app_package

        scan_components(_app_class(name))

        assert isolated_container.has_by_name("Greeter")
        assert isolated_container.has_by_name("Clock")

    def test_modules_are_imported_under_the_application_package(self, app_package):
        name, _ = app_package

        scan_components(_app_class(name))

        assert f"{name}.services.greeter" in sys.modules
        assert f"{name}.clock" in sys.modules

    @pytest.mark.parametrize(
        "relative_path",
        [
            "_private.py",
            "test_things.py",
            "things_test.py",
            "tests/helpers.py",
            "migrations/versions.py",
            "venv/site.py",
        ],
    )
    def test_excluded_files_are_not_imported(self, app_package, relative_path):
        name, root = app_package
        _write(root / relative_path, "raise RuntimeError('must not be imported')\n")

        scan_components(_app_class(name))

        module_name = relative_path.removesuffix(".py").replace("/", ".")
        assert f"{name}.{module_name}" not in sys.modules

    def test_explicit_base_path_limits_the_scan(self, app_package, isolated_container):
        name, root = app_package

        scan_components(_app_class(name), base_path=root / "services")

        assert isolated_container.has_by_name("Greeter")
        assert not isolated_container.has_by_name("Clock")

    def test_already_imported_module_is_not_reexecuted(
        self, app_package, isolated_container
    ):
        name, _ = app_package
        greeter_module = importlib.import_module(f"{name}.services.greeter")

        scan_components(_app_class(name))

        assert sys.modules[f"{name}.services.greeter"] is greeter_module

    def test_failing_module_is_logged_and_scan_continues(
        self, app_package, isolated_container, caplog
    ):
        name, root = app_package
        _write(root / "broken.py", "raise RuntimeError('boom')\n")

        with caplog.at_level(logging.WARNING):
            scan_components(_app_class(name))

        assert "Failed to import broken.py: boom" in caplog.text
        assert isolated_container.has_by_name("Greeter")
        assert isolated_container.has_by_name("Clock")


class TestScanPackages:
    def test_only_listed_packages_are_imported(self, app_package, isolated_container):
        name, _ = app_package

        scan_components(_app_class(name), scan_packages=[f"{name}.services.greeter"])

        assert isolated_container.has_by_name("Greeter")
        assert not isolated_container.has_by_name("Clock")

    def test_empty_list_imports_nothing(self, app_package, isolated_container):
        name, _ = app_package

        scan_components(_app_class(name), scan_packages=[])

        assert not isolated_container.has_by_name("Greeter")
        assert not isolated_container.has_by_name("Clock")

    def test_missing_package_is_logged_and_scan_continues(
        self, app_package, isolated_container, caplog
    ):
        name, _ = app_package

        with caplog.at_level(logging.WARNING):
            scan_components(
                _app_class(name),
                scan_packages=[f"{name}.missing", f"{name}.services.greeter"],
            )

        assert f"Failed to scan package {name}.missing" in caplog.text
        assert isolated_container.has_by_name("Greeter")

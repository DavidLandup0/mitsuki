import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Optional, Type

EXCLUDED_DIRS = {
    "tests",
    "test",
    "migrations",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
}


def scan_components(
    application_class: Type,
    base_path: Optional[Path] = None,
    scan_packages: Optional[list[str]] = None,
):
    """
    Scan for components in the application module and submodules.
    Automatically discovers and imports Python modules to trigger decorator registration.

    Args:
        application_class: The application class to scan from
        base_path: Optional base path to scan, defaults to application module directory
        scan_packages: Optional list of package names to scan (e.g., ["app.controllers", "app.services"])
                      If provided, only these packages are scanned. Otherwise, scans recursively.
    """
    # If scan_packages is specified (even if empty), scan only those packages
    if scan_packages is not None:
        for package_name in scan_packages:
            try:
                # Import the package to trigger decorator registration
                logging.debug(f"Scanning package: {package_name}")
                importlib.import_module(package_name)
            except Exception as e:
                logging.warning(f"Failed to scan package {package_name}: {e}")
        return

    # Default: scan the application directory recursively
    if base_path is None:
        # Get the module where the application class is defined
        module = inspect.getmodule(application_class)
        if module and hasattr(module, "__file__") and module.__file__:
            base_path = Path(module.__file__).parent
        else:
            base_path = Path.cwd()

    # Get the package name from the application module
    app_module = inspect.getmodule(application_class)
    if app_module and hasattr(app_module, "__package__") and app_module.__package__:
        package_name = app_module.__package__
    elif app_module and hasattr(app_module, "__name__"):
        # For __main__ module, use the directory name
        package_name = base_path.name
    else:
        package_name = base_path.name

    # Find all Python files in the base path (recursive)
    python_files = list(base_path.glob("**/*.py"))
    logging.debug(
        f"Component scan: found {len(python_files)} Python files in {base_path} (recursive)"
    )

    # Import each module to trigger decorator registration
    for py_file in python_files:
        # Skip files starting with underscore, test files or excluded
        if py_file.name.startswith("_"):
            continue

        if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
            continue

        if any(excluded_dir in py_file.parts for excluded_dir in EXCLUDED_DIRS):
            continue

        # Calculate relative path from base_path to build proper module name
        try:
            relative_path = py_file.relative_to(base_path)
        except ValueError:
            continue  # Skip files outside base_path

        # Convert path to module name (e.g., "controllers/user.py" -> "controllers.user")
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        module_name = ".".join(module_parts)

        # Build full module name with package prefix
        full_module_name = (
            f"{package_name}.{module_name}"
            if package_name != "__main__"
            else module_name
        )

        if full_module_name in sys.modules:
            logging.debug(
                f"Skipping {module_name} - already imported as {full_module_name}"
            )
            continue

        try:
            # Import the module to trigger decorator registration
            logging.debug(f"Importing {py_file.name} as {full_module_name}")
            spec = importlib.util.spec_from_file_location(full_module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[full_module_name] = module
                spec.loader.exec_module(module)
            logging.debug(f"Successfully imported {module_name}")
        except Exception as e:
            logging.warning(f"Failed to import {py_file.name}: {e}")

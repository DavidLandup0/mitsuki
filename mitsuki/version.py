from pathlib import Path

import tomli as tomllib


def get_version() -> str:
    """
    Get the Mitsuki framework version from pyproject.toml.

    Returns:
        Version string, or "unknown" if not found
    """
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        return "unknown"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
        return pyproject.get("project", {}).get("version", "unknown")

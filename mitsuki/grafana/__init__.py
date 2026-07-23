from importlib import resources
from pathlib import Path

DASHBOARD_FILENAME = "dashboard.json"

def dashboard_json() -> str:
    """Return the bundled Grafana dashboard as a JSON string."""
    return (
        resources.files(__name__).joinpath(DASHBOARD_FILENAME).read_text(encoding="utf-8")
    )


def write_dashboard(destination: Path) -> Path:
    """
    Write the bundled Grafana dashboard to destination.

    A directory destination writes dashboard.json inside it; any other path is
    treated as the target file. Parent directories are created as needed.
    """
    destination = Path(destination)

    if destination.is_dir() or destination.suffix == "":
        destination = destination / DASHBOARD_FILENAME

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dashboard_json(), encoding="utf-8")

    return destination

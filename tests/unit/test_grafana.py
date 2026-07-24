import json

from click.testing import CliRunner

from mitsuki.cli.bootstrap import cli
from mitsuki.grafana import DASHBOARD_FILENAME, dashboard_json, write_dashboard


class TestDashboardAsset:
    """The bundled dashboard is valid, self-consistent Grafana JSON."""

    def test_dashboard_json_is_valid(self):
        dashboard = json.loads(dashboard_json())

        assert dashboard["title"]
        assert isinstance(dashboard["panels"], list)
        assert dashboard["panels"]

    def test_panel_ids_are_unique(self):
        panels = json.loads(dashboard_json())["panels"]
        ids = [panel["id"] for panel in panels]

        assert len(ids) == len(set(ids))

    def test_write_to_directory(self, tmp_path):
        written = write_dashboard(tmp_path)

        assert written == tmp_path / DASHBOARD_FILENAME
        assert json.loads(written.read_text()) == json.loads(dashboard_json())

    def test_write_to_file_path(self, tmp_path):
        target = tmp_path / "custom.json"
        written = write_dashboard(target)

        assert written == target
        assert json.loads(written.read_text())

    def test_write_creates_missing_parent(self, tmp_path):
        written = write_dashboard(tmp_path / "nested" / "dir")

        assert written.exists()


class TestGrafanaDashboardCommand:
    """The CLI writes the dashboard to the requested location."""

    def test_writes_dashboard_to_output_dir(self, tmp_path):
        result = CliRunner().invoke(
            cli, ["grafana-dashboard", "-o", str(tmp_path)]
        )

        assert result.exit_code == 0
        written = tmp_path / DASHBOARD_FILENAME
        assert written.exists()
        assert json.loads(written.read_text())["panels"]

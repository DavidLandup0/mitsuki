import json
import re

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
        result = CliRunner().invoke(cli, ["grafana-dashboard", "-o", str(tmp_path)])

        assert result.exit_code == 0
        written = tmp_path / DASHBOARD_FILENAME
        assert written.exists()
        assert json.loads(written.read_text())["panels"]


class TestFrameworkDashboardIsGeneric:
    """The shipped dashboard must only query metrics Mitsuki itself emits."""

    # Metric names emitted by the framework (instrumentation + scheduler + system).
    FRAMEWORK_PREFIXES = (
        "http_requests_total",
        "http_request_duration_seconds",
        "component_calls_total",
        "component_duration_seconds",
        "scheduler_task_executions_total",
        "scheduler_task_duration_seconds",
        "scheduler_tasks_running",
        "system_memory_bytes",
        "system_cpu_percent",
        "system_traced_memory_bytes",
    )

    def _metric_names(self, expr):
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
        # A metric name is a token that looks like one of ours by suffix.
        return {
            t
            for t in tokens
            if t.endswith(("_total", "_seconds", "_bytes", "_percent", "_running"))
        }

    def test_dashboard_references_only_framework_metrics(self):
        dashboard = json.loads(dashboard_json())

        referenced = set()
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                referenced |= self._metric_names(target.get("expr", ""))

        foreign = {m for m in referenced if not m.startswith(self.FRAMEWORK_PREFIXES)}
        assert foreign == set(), (
            f"framework dashboard references non-framework metrics: {sorted(foreign)}"
        )

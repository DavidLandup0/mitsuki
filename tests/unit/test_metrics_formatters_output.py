import json
from pathlib import Path

from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_json, format_prometheus

EXPECTED_OUTPUT = Path(__file__).parent / "expected_output"


def populated_storage() -> MetricsStorage:
    """Every metric shape the formatters handle, with deterministic values."""
    storage = MetricsStorage()
    storage.enable()

    executions = storage.counter("scheduler_task_executions_total", "Task runs")
    durations = storage.histogram("scheduler_task_duration_seconds", "Task duration")
    running = storage.gauge("scheduler_tasks_running", "Running tasks")
    executions.inc({"task": "Reports.nightly", "status": "success"}, 3)
    executions.inc({"task": "Reports.nightly", "status": "failure"})
    for value in (0.02, 0.03, 0.04):
        durations.observe(value, {"task": "Reports.nightly"})
    executions.inc({"task": "Cache.flush", "status": "failure"}, 2)
    executions.inc({"task": "Audit.noop", "status": "success"})
    durations.observe(0.0, {"task": "Audit.noop"})
    running.set(1, {"task": "Reports.nightly"})
    running.set(0, {"task": "Audit.noop"})

    memory = storage.gauge("system_memory_bytes", "Process memory")
    memory.set(52428800, {"type": "rss"})
    memory.set(181608448, {"type": "vms"})
    storage.gauge("system_cpu_percent", "Process CPU").set(12.345)
    traced = storage.gauge("system_traced_memory_bytes", "Traced memory")
    traced.set(1048576, {"type": "current"})
    traced.set(2097152, {"type": "peak"})

    requests = storage.counter("http_requests_total", "HTTP requests")
    latency = storage.histogram("http_request_duration_seconds", "HTTP latency")
    requests.inc({"method": "GET", "path": "/api/users", "status": "200"}, 5)
    requests.inc({"method": "GET", "path": "/api/users/{user_id}", "status": "404"}, 2)
    requests.inc({"method": "POST", "path": "/api/users", "status": "201"}, 3)
    for value in (0.004, 0.006, 0.2, 12.0):
        latency.observe(value, {"method": "GET", "path": "/api/users"})
    latency.observe(0.05, {"method": "POST", "path": "/api/users"})

    calls = storage.counter("component_calls_total", "Component calls")
    call_durations = storage.histogram("component_duration_seconds", "Component time")
    calls.inc(
        {"component": "UserService", "method": "get_user", "status": "success"}, 4
    )
    calls.inc({"component": "UserService", "method": "get_user", "status": "failure"})
    calls.inc(
        {"component": "UserService", "method": "create_user", "status": "success"}, 2
    )
    calls.inc(
        {"component": "OrderRepository", "method": "save", "status": "success"}, 3
    )
    calls.inc(
        {"component": "OrderRepository", "method": "find_all", "status": "success"}
    )
    for value in (0.01, 0.02, 0.03, 0.04, 0.05):
        call_durations.observe(
            value, {"component": "UserService", "method": "get_user"}
        )
    call_durations.observe(0.1, {"component": "UserService", "method": "create_user"})
    call_durations.observe(0.1, {"component": "UserService", "method": "create_user"})
    for value in (0.001, 0.002, 0.003):
        call_durations.observe(
            value, {"component": "OrderRepository", "method": "save"}
        )

    storage.counter("orders_created_total", "Orders").inc(
        {"region": 'us-"east"', "product_type": "digital"}, 2
    )
    storage.counter("registered_but_unused_total", "Never recorded")

    return storage


class TestFormatterOutputIsStable:
    """
    Both formats, for every metric shape, match the recorded output exactly:
    values, key order, sample order and text layout.
    """

    def test_json_output(self):
        result = format_json(populated_storage())
        result.pop("timestamp")

        expected = json.loads((EXPECTED_OUTPUT / "metrics_formatters.json").read_text())
        assert json.dumps(result, indent=4) == json.dumps(expected, indent=4)

    def test_prometheus_output(self):
        expected = (EXPECTED_OUTPUT / "metrics_formatters.prom").read_text()

        assert format_prometheus(populated_storage()) == expected

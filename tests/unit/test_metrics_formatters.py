import re

import pytest

from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_mitsuki, format_prometheus


class TestPrometheusFormatter:
    """Test Prometheus format output."""

    def test_format_disabled_registry(self):
        """Test formatting disabled metrics registry."""
        storage = MetricsStorage()
        output = format_prometheus(storage)

        assert output == "# Metrics disabled\n"

    def test_format_empty_registry(self):
        """Test formatting empty enabled metrics registry."""
        storage = MetricsStorage()
        storage.enable()
        output = format_prometheus(storage)

        assert output == "\n"

    def test_format_counter(self):
        """Test formatting counter metric."""
        storage = MetricsStorage()
        storage.enable()
        counter = storage.counter("http_requests_total", "Total HTTP requests")

        counter.inc({"method": "GET", "status": "200"})
        counter.inc({"method": "POST", "status": "201"})

        output = format_prometheus(storage)

        assert "# HELP http_requests_total Total HTTP requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET",status="200"} 1.0' in output
        assert 'http_requests_total{method="POST",status="201"} 1.0' in output

    def test_format_counter_no_labels(self):
        """Test formatting counter without labels."""
        storage = MetricsStorage()
        storage.enable()
        counter = storage.counter("errors_total")

        counter.inc()

        output = format_prometheus(storage)

        assert "# TYPE errors_total counter" in output
        assert "errors_total 1.0" in output

    def test_format_gauge(self):
        """Test formatting gauge metric."""
        storage = MetricsStorage()
        storage.enable()
        gauge = storage.gauge("memory_bytes", "Memory usage in bytes")

        gauge.set(1024.0, {"type": "rss"})
        gauge.set(2048.0, {"type": "vms"})

        output = format_prometheus(storage)

        assert "# HELP memory_bytes Memory usage in bytes" in output
        assert "# TYPE memory_bytes gauge" in output
        assert 'memory_bytes{type="rss"} 1024.0' in output
        assert 'memory_bytes{type="vms"} 2048.0' in output

    def test_format_histogram(self):
        """Test formatting histogram metric."""
        storage = MetricsStorage()
        storage.enable()
        histogram = storage.histogram(
            "request_duration_seconds", "Request duration", buckets=[0.1, 0.5, 1.0]
        )

        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.7)

        output = format_prometheus(storage)

        assert "# HELP request_duration_seconds Request duration" in output
        assert "# TYPE request_duration_seconds histogram" in output
        assert 'request_duration_seconds_bucket{le="0.1"} 1' in output
        assert 'request_duration_seconds_bucket{le="0.5"} 2' in output
        assert 'request_duration_seconds_bucket{le="1.0"} 3' in output
        assert 'request_duration_seconds_bucket{le="+Inf"} 3' in output

        sum_match = re.search(r"request_duration_seconds_sum ([\d.]+)", output)
        assert sum_match is not None
        sum_value = float(sum_match.group(1))
        assert sum_value == pytest.approx(1.05)

        assert "request_duration_seconds_count 3" in output

    def test_format_multiple_metrics(self):
        """Test formatting multiple metric types."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("requests_total")
        gauge = storage.gauge("active_connections")
        histogram = storage.histogram("response_time_seconds", buckets=[0.1])

        counter.inc()
        gauge.set(5.0)
        histogram.observe(0.05)

        output = format_prometheus(storage)

        assert "# TYPE requests_total counter" in output
        assert "# TYPE active_connections gauge" in output
        assert "# TYPE response_time_seconds histogram" in output


class TestMitsukiFormatter:
    """Test Mitsuki JSON format output."""

    def test_format_disabled_registry(self):
        """Test formatting disabled metrics registry."""
        storage = MetricsStorage()
        result = format_mitsuki(storage)

        assert result["enabled"] is False
        assert "timestamp" in result

    def test_format_empty_registry(self):
        """Test formatting empty enabled metrics registry."""
        storage = MetricsStorage()
        storage.enable()
        result = format_mitsuki(storage)

        assert result["enabled"] is True
        assert "timestamp" in result

    def test_format_http_metrics(self):
        """Test formatting HTTP metrics."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("http_requests_total")
        histogram = storage.histogram("http_request_duration_seconds")

        counter.inc({"method": "GET", "path": "/api/users", "status": "200"})
        counter.inc({"method": "GET", "path": "/api/users", "status": "200"})
        histogram.observe(0.1, {"method": "GET", "path": "/api/users"})
        histogram.observe(0.2, {"method": "GET", "path": "/api/users"})

        result = format_mitsuki(storage)

        assert "instrumentation" in result
        assert "http" in result["instrumentation"]
        http_data = result["instrumentation"]["http"]
        assert http_data["total_requests"] == 2
        assert "GET" in http_data["requests_by_method"]

    def test_format_system_metrics(self):
        """Test formatting system metrics."""
        storage = MetricsStorage()
        storage.enable()

        memory_gauge = storage.gauge("system_memory_bytes")
        cpu_gauge = storage.gauge("system_cpu_percent")

        memory_gauge.set(1048576.0, {"type": "rss"})
        memory_gauge.set(2097152.0, {"type": "vms"})
        cpu_gauge.set(25.5)

        result = format_mitsuki(storage)

        assert "instrumentation" in result
        assert "system" in result["instrumentation"]
        system_data = result["instrumentation"]["system"]
        assert system_data["memory"]["rss_bytes"] == 1048576
        assert system_data["cpu"]["percent"] == 25.5

    def test_format_component_metrics(self):
        """Test formatting component metrics."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("component_calls_total")
        histogram = storage.histogram("component_duration_seconds")

        counter.inc({"component": "UserService", "status": "success"})
        counter.inc({"component": "UserService", "status": "success"})
        histogram.observe(0.05, {"component": "UserService"})

        result = format_mitsuki(storage)

        assert "instrumentation" in result
        assert "components" in result["instrumentation"]
        components = result["instrumentation"]["components"]
        assert "UserService" in components
        assert components["UserService"]["calls"] == 2

    def test_format_scheduler_metrics(self):
        """Test formatting scheduler metrics."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("scheduler_task_executions_total")
        histogram = storage.histogram("scheduler_task_duration_seconds")

        counter.inc({"task": "CleanupTask", "status": "success"})
        histogram.observe(0.1, {"task": "CleanupTask"})

        result = format_mitsuki(storage)

        assert "scheduler" in result
        scheduler_data = result["scheduler"]
        assert scheduler_data["total_tasks"] == 1
        assert len(scheduler_data["tasks"]) == 1
        assert scheduler_data["tasks"][0]["name"] == "CleanupTask"


class TestFormatterIntegration:
    """Integration tests for formatters."""

    def test_prometheus_and_mitsuki_consistency(self):
        """Test that both formatters handle the same data."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("http_requests_total")
        counter.inc({"method": "GET", "path": "/api", "status": "200"})
        counter.inc({"method": "GET", "path": "/api", "status": "200"})
        counter.inc({"method": "POST", "path": "/api", "status": "404"})

        prom_output = format_prometheus(storage)
        mitsuki_output = format_mitsuki(storage)

        assert (
            'http_requests_total{method="GET",path="/api",status="200"} 2.0'
            in prom_output
        )
        assert (
            'http_requests_total{method="POST",path="/api",status="404"} 1.0'
            in prom_output
        )

        assert mitsuki_output["instrumentation"]["http"]["total_requests"] == 3

    def test_real_world_metrics_scenario(self):
        """Test realistic metrics collection and formatting."""
        storage = MetricsStorage()
        storage.enable()

        requests_counter = storage.counter("http_requests_total")
        duration_histogram = storage.histogram("http_request_duration_seconds")

        requests_counter.inc({"method": "GET", "path": "/api/users", "status": "200"})
        duration_histogram.observe(0.15, {"method": "GET", "path": "/api/users"})

        requests_counter.inc({"method": "POST", "path": "/api/users", "status": "201"})
        duration_histogram.observe(0.25, {"method": "POST", "path": "/api/users"})

        prom_output = format_prometheus(storage)
        mitsuki_output = format_mitsuki(storage)

        assert prom_output
        assert "instrumentation" in mitsuki_output
        assert "http" in mitsuki_output["instrumentation"]

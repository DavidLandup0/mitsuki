from datetime import datetime
from typing import Any, Dict

from mitsuki.core.metrics_core import MetricsStorage


def format_json(registry: MetricsStorage) -> Dict[str, Any]:
    """
    Format metrics in Mitsuki's nested JSON format.

    Returns computed aggregations for human readability:
    - Averages from histograms
    - Nested structure by category
    - Timestamps
    """
    if not registry.enabled:
        return {"enabled": False, "timestamp": datetime.utcnow().isoformat()}

    result = {
        "enabled": True,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Scheduler metrics (if any exist)
    scheduler_metrics = _extract_scheduler_metrics(registry)
    if scheduler_metrics:
        result["scheduler"] = scheduler_metrics

    # Instrumentation metrics (if any exist)
    instrumentation_metrics = _extract_instrumentation_metrics(registry)
    if instrumentation_metrics:
        result["instrumentation"] = instrumentation_metrics

    return result


def _extract_scheduler_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    """Extract scheduler metrics in nested format."""
    # Check if scheduler metrics exist
    if "scheduler_task_executions_total" not in registry.counters:
        return {}

    tasks_data = []
    task_names = set()

    # Collect unique task names from counter labels
    executions_counter = registry.counters.get("scheduler_task_executions_total")
    if executions_counter:
        for sample in executions_counter.samples():
            task_name = sample.labels.get("task")
            if task_name:
                task_names.add(task_name)

    # Build task statistics
    for task_name in sorted(task_names):
        task_labels = {"task": task_name}

        # Get executions (success + failure)
        success_count = executions_counter.get({"task": task_name, "status": "success"})
        failure_count = executions_counter.get({"task": task_name, "status": "failure"})
        total_executions = success_count + failure_count

        # Get duration stats
        duration_hist = registry.histograms.get("scheduler_task_duration_seconds")
        duration_sum = 0.0
        duration_count = 0
        if duration_hist:
            duration_sum = duration_hist.get_sum(task_labels)
            duration_count = duration_hist.get_count(task_labels)

        avg_duration_ms = (
            (duration_sum / duration_count * 1000) if duration_count > 0 else None
        )

        # Get running status
        running_gauge = registry.gauges.get("scheduler_tasks_running")
        is_running = running_gauge.get(task_labels) > 0 if running_gauge else False

        tasks_data.append(
            {
                "name": task_name,
                "executions": int(total_executions),
                "failures": int(failure_count),
                "average_duration_ms": round(avg_duration_ms, 2)
                if avg_duration_ms
                else None,
                "status": "running" if is_running else "idle",
            }
        )

    return {
        "tasks": tasks_data,
        "total_tasks": len(tasks_data),
        "running_tasks": sum(1 for t in tasks_data if t["status"] == "running"),
    }


def _extract_instrumentation_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    """Extract instrumentation metrics in nested format."""
    result = {}

    # System metrics
    system_metrics = _extract_system_metrics(registry)
    if system_metrics:
        result["system"] = system_metrics

    # HTTP metrics
    http_metrics = _extract_http_metrics(registry)
    if http_metrics:
        result["http"] = http_metrics

    # Component metrics
    component_metrics = _extract_component_metrics(registry)
    if component_metrics:
        result["components"] = component_metrics

    return result


def _extract_system_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    """Extract system metrics."""
    if "system_memory_bytes" not in registry.gauges:
        return {}

    memory_gauge = registry.gauges["system_memory_bytes"]
    cpu_gauge = registry.gauges.get("system_cpu_percent")

    memory_rss = memory_gauge.get({"type": "rss"})
    memory_vms = memory_gauge.get({"type": "vms"})

    return {
        "memory": {
            "rss_bytes": int(memory_rss),
            "rss_mb": round(memory_rss / (1024 * 1024), 2),
            "vms_bytes": int(memory_vms),
            "vms_mb": round(memory_vms / (1024 * 1024), 2),
        },
        "cpu": {"percent": round(cpu_gauge.get(), 2) if cpu_gauge else 0.0},
    }


def _extract_http_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    """Extract HTTP metrics with aggregations."""
    if "http_requests_total" not in registry.counters:
        return {}

    requests_counter = registry.counters["http_requests_total"]
    duration_hist = registry.histograms.get("http_request_duration_seconds")

    # Aggregate by method
    by_method = {}
    for sample in requests_counter.samples():
        method = sample.labels.get("method", "UNKNOWN")
        by_method[method] = by_method.get(method, 0) + sample.value

    # Aggregate by status
    by_status = {}
    for sample in requests_counter.samples():
        status = sample.labels.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + sample.value

    total_requests = sum(by_method.values())

    # Duration statistics
    latency = {}
    if duration_hist:
        total_sum = sum(s[1] for s in duration_hist.samples())
        total_count = sum(s[2] for s in duration_hist.samples())

        if total_count > 0:
            latency = {
                "avg_ms": round((total_sum / total_count) * 1000, 2),
                "total_seconds": round(total_sum, 2),
            }

    return {
        "total_requests": int(total_requests),
        "requests_by_method": {k: int(v) for k, v in by_method.items()},
        "responses_by_status": {k: int(v) for k, v in by_status.items()},
        "latency": latency,
    }


def _extract_component_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    """Extract component-level metrics."""
    if "component_calls_total" not in registry.counters:
        return {}

    calls_counter = registry.counters["component_calls_total"]
    duration_hist = registry.histograms.get("component_duration_seconds")

    components = {}
    component_names = set()

    # Collect component names
    for sample in calls_counter.samples():
        component = sample.labels.get("component")
        if component:
            component_names.add(component)

    # Build component stats
    for component_name in sorted(component_names):
        component_labels = {"component": component_name}

        # Calls (sum success + failure)
        success_count = calls_counter.get(
            {"component": component_name, "status": "success"}
        )
        failure_count = calls_counter.get(
            {"component": component_name, "status": "failure"}
        )
        total_calls = success_count + failure_count

        # Duration
        avg_duration_ms = None
        if duration_hist:
            duration_sum = duration_hist.get_sum(component_labels)
            duration_count = duration_hist.get_count(component_labels)
            if duration_count > 0:
                avg_duration_ms = round((duration_sum / duration_count) * 1000, 2)

        components[component_name] = {
            "calls": int(total_calls),
            "avg_duration_ms": avg_duration_ms,
        }

    return components


def format_prometheus(registry: MetricsStorage) -> str:
    """
    Format metrics in Prometheus text format.

    Returns flat text with labels, compatible with Prometheus scraping.
    """
    if not registry.enabled:
        return "# Metrics disabled\n"

    lines = []

    # Counters
    for name, counter in registry.counters.items():
        lines.append(f"# HELP {name} {counter.help_text}")
        lines.append(f"# TYPE {name} counter")
        for sample in counter.samples():
            labels_str = _format_labels(sample.labels)
            lines.append(f"{name}{labels_str} {sample.value}")

    # Gauges
    for name, gauge in registry.gauges.items():
        lines.append(f"# HELP {name} {gauge.help_text}")
        lines.append(f"# TYPE {name} gauge")
        for sample in gauge.samples():
            labels_str = _format_labels(sample.labels)
            lines.append(f"{name}{labels_str} {sample.value}")

    # Histograms
    for name, histogram in registry.histograms.items():
        lines.append(f"# HELP {name} {histogram.help_text}")
        lines.append(f"# TYPE {name} histogram")

        for labels, total_sum, total_count, buckets in histogram.samples():
            labels_str_base = _format_labels(labels) if labels else ""

            # Bucket counts (already cumulative from Histogram.observe)
            for upper_bound, count in buckets:
                bucket_labels = {**labels, "le": str(upper_bound)}
                labels_str = _format_labels(bucket_labels)
                lines.append(f"{name}_bucket{labels_str} {count}")

            # +Inf bucket
            inf_labels = {**labels, "le": "+Inf"}
            labels_str = _format_labels(inf_labels)
            lines.append(f"{name}_bucket{labels_str} {total_count}")

            # Sum and count
            lines.append(f"{name}_sum{labels_str_base} {total_sum}")
            lines.append(f"{name}_count{labels_str_base} {total_count}")

    return "\n".join(lines) + "\n"


def _format_labels(labels: Dict[str, str]) -> str:
    """Format labels for Prometheus output."""
    if not labels:
        return ""

    label_pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(label_pairs) + "}"

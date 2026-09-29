from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from mitsuki.core.metrics_core import MetricSample, MetricsStorage


def format_json(registry: MetricsStorage) -> Dict[str, Any]:
    """
    Format metrics in Mitsuki's nested JSON format.

    Returns computed aggregations for human readability:
    - Averages from histograms
    - Nested structure by category
    - Timestamps
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    if not registry.enabled:
        return {"enabled": False, "timestamp": timestamp}

    sections = {
        "scheduler": _extract_scheduler_metrics(registry),
        "instrumentation": _extract_instrumentation_metrics(registry),
    }
    return {"enabled": True, "timestamp": timestamp, **_non_empty(sections)}


def _extract_scheduler_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    executions = registry.counters.get("scheduler_task_executions_total")
    if executions is None:
        return {}

    task_names = sorted(
        {name for sample in executions.samples() if (name := sample.labels.get("task"))}
    )
    if not task_names:
        return {}

    durations = registry.histograms.get("scheduler_task_duration_seconds")
    running = registry.gauges.get("scheduler_tasks_running")

    tasks = []
    for name in task_names:
        labels = {"task": name}
        successes = executions.get({"task": name, "status": "success"})
        failures = executions.get({"task": name, "status": "failure"})
        average_ms = (
            _average_ms(durations.get_sum(labels), durations.get_count(labels))
            if durations
            else None
        )
        is_running = running is not None and running.get(labels) > 0

        tasks.append(
            {
                "name": name,
                "executions": int(successes + failures),
                "failures": int(failures),
                "average_duration_ms": average_ms,
                "status": "running" if is_running else "idle",
            }
        )

    return {
        "tasks": tasks,
        "total_tasks": len(tasks),
        "running_tasks": sum(task["status"] == "running" for task in tasks),
    }


def _extract_instrumentation_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    return _non_empty(
        {
            "system": _extract_system_metrics(registry),
            "http": _extract_http_metrics(registry),
            "components": _extract_component_metrics(registry),
        }
    )


def _extract_system_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    memory_gauge = registry.gauges.get("system_memory_bytes")
    if memory_gauge is None:
        return {}

    rss = memory_gauge.get({"type": "rss"})
    vms = memory_gauge.get({"type": "vms"})
    memory = {
        "rss_bytes": int(rss),
        "rss_mb": _megabytes(rss),
        "vms_bytes": int(vms),
        "vms_mb": _megabytes(vms),
    }

    traced = registry.gauges.get("system_traced_memory_bytes")
    if traced:
        memory["traced_current_bytes"] = int(traced.get({"type": "current"}))
        memory["traced_peak_bytes"] = int(traced.get({"type": "peak"}))

    cpu = registry.gauges.get("system_cpu_percent")
    return {
        "memory": memory,
        "cpu": {"percent": round(cpu.get(), 2) if cpu else 0.0},
    }


def _extract_http_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    requests = registry.counters.get("http_requests_total")
    samples = requests.samples() if requests else []
    if not samples:
        return {}

    by_method = _sum_by(samples, "method", default="UNKNOWN")
    by_status = _sum_by(samples, "status", default="unknown")

    latency = {}
    durations = registry.histograms.get("http_request_duration_seconds")
    if durations:
        duration_samples = durations.samples()
        total_sum = sum(sample[1] for sample in duration_samples)
        total_count = sum(sample[2] for sample in duration_samples)
        if total_count:
            latency = {
                "avg_ms": _average_ms(total_sum, total_count),
                "total_seconds": round(total_sum, 2),
            }

    return {
        "total_requests": int(sum(by_method.values())),
        "requests_by_method": _as_ints(by_method),
        "responses_by_status": _as_ints(by_status),
        "latency": latency,
    }


def _extract_component_metrics(registry: MetricsStorage) -> Dict[str, Any]:
    calls = registry.counters.get("component_calls_total")
    if calls is None:
        return {}

    # stats[component][method] = [calls, duration_sum, duration_count]. Calls
    # are labelled by status as well, so success and failure samples add up.
    stats = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0]))
    for sample in calls.samples():
        component = sample.labels.get("component")
        if component:
            stats[component][sample.labels.get("method", "")][0] += sample.value

    # Durations only count for methods that have recorded calls.
    durations = registry.histograms.get("component_duration_seconds")
    if durations:
        for labels, total_sum, total_count, _ in durations.samples():
            method_stats = stats.get(labels.get("component"), {}).get(
                labels.get("method", "")
            )
            if method_stats:
                method_stats[1] += total_sum
                method_stats[2] += total_count

    components = {}
    for component in sorted(stats):
        methods = sorted(stats[component].items())
        components[component] = {
            "calls": int(sum(calls for _, (calls, _, _) in methods)),
            "avg_duration_ms": _average_ms(
                sum(total for _, (_, total, _) in methods),
                sum(count for _, (_, _, count) in methods),
            ),
            "methods": {
                method: {
                    "calls": int(method_calls),
                    "avg_duration_ms": _average_ms(total, count),
                }
                for method, (method_calls, total, count) in methods
            },
        }

    return components


def _non_empty(sections: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the sections that have content."""
    return {key: value for key, value in sections.items() if value}


def _average_ms(total_seconds: float, count: int) -> Optional[float]:
    """Average in milliseconds, rounded, or None when nothing was measured."""
    return round(total_seconds / count * 1000, 2) if count else None


def _megabytes(size_bytes: float) -> float:
    return round(size_bytes / (1024 * 1024), 2)


def _sum_by(
    samples: Iterable[MetricSample], label: str, default: str
) -> Dict[str, float]:
    """Sum sample values per value of one label."""
    totals = defaultdict(float)
    for sample in samples:
        totals[sample.labels.get(label, default)] += sample.value
    return totals


def _as_ints(values: Dict[str, float]) -> Dict[str, int]:
    return {key: int(value) for key, value in values.items()}


def format_prometheus(registry: MetricsStorage) -> str:
    """
    Format metrics in Prometheus text format.

    Returns flat text with labels, compatible with Prometheus scraping.
    """
    if not registry.enabled:
        return "# Metrics disabled\n"

    # A family with no samples carries no information, so it is omitted
    # entirely, HELP and TYPE included.
    lines = []

    for metric_type, metrics in (
        ("counter", registry.counters),
        ("gauge", registry.gauges),
    ):
        for name, metric in metrics.items():
            samples = metric.samples()
            if samples:
                lines += _family_header(name, metric.help_text, metric_type)
                lines += [
                    f"{name}{_format_labels(sample.labels)} {sample.value}"
                    for sample in samples
                ]

    for name, histogram in registry.histograms.items():
        samples = histogram.samples()
        if not samples:
            continue

        lines += _family_header(name, histogram.help_text, "histogram")
        for labels, total_sum, total_count, buckets in samples:
            # Bucket counts are already cumulative.
            for upper_bound, count in buckets:
                bucket_labels = _format_labels({**labels, "le": str(upper_bound)})
                lines.append(f"{name}_bucket{bucket_labels} {count}")
            inf_labels = _format_labels({**labels, "le": "+Inf"})
            lines.append(f"{name}_bucket{inf_labels} {total_count}")
            lines.append(f"{name}_sum{_format_labels(labels)} {total_sum}")
            lines.append(f"{name}_count{_format_labels(labels)} {total_count}")

    return "\n".join(lines) + "\n"


def _family_header(name: str, help_text: str, metric_type: str) -> List[str]:
    return [f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}"]


def _escape_label_value(value: str) -> str:
    """Escape a label value per the Prometheus exposition format."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: Dict[str, str]) -> str:
    """Format labels for Prometheus output."""
    if not labels:
        return ""

    label_pairs = [f'{k}="{_escape_label_value(v)}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(label_pairs) + "}"

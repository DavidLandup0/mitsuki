"""
Core metrics types and registry for unified metrics system.

Provides simple metric primitives that both scheduler and instrumentation use:
- Counter: Monotonically increasing value
- Gauge: Current value (can go up or down)
- Histogram: Distribution of values with buckets

All metrics support labels for multi-dimensional data.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MetricSample:
    """Single metric sample with labels and value."""

    labels: Dict[str, str]
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class Counter:
    """
    Monotonically increasing counter.

    Use for: request counts, error counts, task executions
    """

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._values: Dict[Tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, labels: Optional[Dict[str, str]] = None, amount: float = 1.0):
        """Increment counter by amount."""
        label_key = self._labels_to_key(labels or {})
        with self._lock:
            self._values[label_key] += amount

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current value for labels."""
        label_key = self._labels_to_key(labels or {})
        with self._lock:
            return self._values.get(label_key, 0.0)

    def samples(self) -> List[MetricSample]:
        """Get all samples."""
        with self._lock:
            return [
                MetricSample(labels=self._key_to_labels(key), value=value)
                for key, value in self._values.items()
            ]

    @staticmethod
    def _labels_to_key(labels: Dict[str, str]) -> Tuple[str, ...]:
        """Convert labels dict to hashable key."""
        return tuple(sorted(labels.items()))

    @staticmethod
    def _key_to_labels(key: Tuple[str, ...]) -> Dict[str, str]:
        """Convert key back to labels dict."""
        return dict(key)


class Gauge:
    """
    Current value gauge (can go up or down).

    Use for: memory usage, active connections, queue size
    """

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._values: Dict[Tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Set gauge to value."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            self._values[label_key] = value

    def inc(self, labels: Optional[Dict[str, str]] = None, amount: float = 1.0):
        """Increment gauge by amount."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            self._values[label_key] = self._values.get(label_key, 0.0) + amount

    def dec(self, labels: Optional[Dict[str, str]] = None, amount: float = 1.0):
        """Decrement gauge by amount."""
        self.inc(labels, -amount)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current value for labels."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            return self._values.get(label_key, 0.0)

    def samples(self) -> List[MetricSample]:
        """Get all samples."""
        with self._lock:
            return [
                MetricSample(labels=Counter._key_to_labels(key), value=value)
                for key, value in self._values.items()
            ]


class Histogram:
    """
    Distribution of values with configurable buckets.

    Use for: request duration, response size, task duration
    Automatically tracks sum and count for average calculation.
    """

    # Default buckets in seconds: 1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
    DEFAULT_BUCKETS = [
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ]

    def __init__(
        self, name: str, help_text: str = "", buckets: Optional[List[float]] = None
    ):
        self.name = name
        self.help_text = help_text
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._buckets_data: Dict[Tuple[str, ...], List[int]] = {}
        self._sum: Dict[Tuple[str, ...], float] = defaultdict(float)
        self._count: Dict[Tuple[str, ...], int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            # Initialize buckets if needed
            if label_key not in self._buckets_data:
                self._buckets_data[label_key] = [0] * len(self.buckets)

            # Update buckets
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._buckets_data[label_key][i] += 1

            # Update sum and count
            self._sum[label_key] += value
            self._count[label_key] += 1

    def get_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get sum of all observed values."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            return self._sum.get(label_key, 0.0)

    def get_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        """Get count of observations."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            return self._count.get(label_key, 0)

    def get_buckets(
        self, labels: Optional[Dict[str, str]] = None
    ) -> List[Tuple[float, int]]:
        """Get bucket counts as list of (upper_bound, count) tuples."""
        label_key = Counter._labels_to_key(labels or {})
        with self._lock:
            if label_key not in self._buckets_data:
                return [(bucket, 0) for bucket in self.buckets]
            return list(zip(self.buckets, self._buckets_data[label_key]))

    def samples(
        self,
    ) -> List[Tuple[Dict[str, str], float, int, List[Tuple[float, int]]]]:
        """
        Get all samples.

        Returns list of (labels, sum, count, buckets) tuples.
        """
        with self._lock:
            result = []
            for label_key in self._sum.keys():
                labels = Counter._key_to_labels(label_key)
                total_sum = self._sum[label_key]
                total_count = self._count[label_key]
                buckets = list(zip(self.buckets, self._buckets_data.get(label_key, [])))
                result.append((labels, total_sum, total_count, buckets))
            return result


class MetricsStorage:
    """
    Central registry for all application metrics.

    Singleton that stores both scheduler and instrumentation metrics.
    """

    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.enabled = False

    def enable(self):
        """Enable metrics collection."""
        self.enabled = True

    def disable(self):
        """Disable metrics collection."""
        self.enabled = False

    def counter(self, name: str, help_text: str = "") -> Counter:
        """Get or create a counter."""
        if name not in self.counters:
            self.counters[name] = Counter(name, help_text)
        return self.counters[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        """Get or create a gauge."""
        if name not in self.gauges:
            self.gauges[name] = Gauge(name, help_text)
        return self.gauges[name]

    def histogram(
        self, name: str, help_text: str = "", buckets: Optional[List[float]] = None
    ) -> Histogram:
        """Get or create a histogram."""
        if name not in self.histograms:
            self.histograms[name] = Histogram(name, help_text, buckets)
        return self.histograms[name]

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all registered metrics."""
        return {
            "counters": list(self.counters.keys()),
            "gauges": list(self.gauges.keys()),
            "histograms": list(self.histograms.keys()),
        }

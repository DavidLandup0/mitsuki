import time

import pytest

from mitsuki.core.metrics_core import (
    Counter,
    Gauge,
    Histogram,
    MetricSample,
    MetricsStorage,
)


class TestCounter:
    """Test Counter metric type."""

    def test_counter_initialization(self):
        """Test counter initializes correctly."""
        counter = Counter("requests_total", "Total requests")

        assert counter.name == "requests_total"
        assert counter.help_text == "Total requests"
        assert counter.get() == 0.0

    def test_counter_increment_default(self):
        """Test incrementing counter by default amount."""
        counter = Counter("requests_total")

        counter.inc()

        assert counter.get() == 1.0

    def test_counter_increment_custom_amount(self):
        """Test incrementing counter by custom amount."""
        counter = Counter("requests_total")

        counter.inc(amount=5.0)

        assert counter.get() == 5.0

    def test_counter_increment_with_labels(self):
        """Test incrementing counter with labels."""
        counter = Counter("requests_total")

        counter.inc({"method": "GET", "status": "200"})
        counter.inc({"method": "GET", "status": "200"})
        counter.inc({"method": "POST", "status": "201"})

        assert counter.get({"method": "GET", "status": "200"}) == 2.0
        assert counter.get({"method": "POST", "status": "201"}) == 1.0

    def test_counter_multiple_increments(self):
        """Test multiple increments accumulate."""
        counter = Counter("requests_total")

        for _ in range(10):
            counter.inc()

        assert counter.get() == 10.0

    def test_counter_samples(self):
        """Test getting all samples from counter."""
        counter = Counter("requests_total")

        counter.inc({"method": "GET"})
        counter.inc({"method": "POST"})

        samples = counter.samples()

        assert len(samples) == 2
        assert all(isinstance(s, MetricSample) for s in samples)
        assert all(s.value in [1.0] for s in samples)

    def test_counter_thread_safe(self):
        """Test that counter is thread-safe."""
        import threading

        counter = Counter("requests_total")

        def increment():
            for _ in range(100):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 1000.0


class TestGauge:
    """Test Gauge metric type."""

    def test_gauge_initialization(self):
        """Test gauge initializes correctly."""
        gauge = Gauge("memory_bytes", "Memory usage in bytes")

        assert gauge.name == "memory_bytes"
        assert gauge.help_text == "Memory usage in bytes"
        assert gauge.get() == 0.0

    def test_gauge_set_value(self):
        """Test setting gauge value."""
        gauge = Gauge("memory_bytes")

        gauge.set(1024.0)

        assert gauge.get() == 1024.0

    def test_gauge_set_with_labels(self):
        """Test setting gauge with labels."""
        gauge = Gauge("memory_bytes")

        gauge.set(1024.0, {"type": "rss"})
        gauge.set(2048.0, {"type": "vms"})

        assert gauge.get({"type": "rss"}) == 1024.0
        assert gauge.get({"type": "vms"}) == 2048.0

    def test_gauge_increment(self):
        """Test incrementing gauge."""
        gauge = Gauge("active_connections")

        gauge.inc()
        gauge.inc()
        gauge.inc(amount=3.0)

        assert gauge.get() == 5.0

    def test_gauge_decrement(self):
        """Test decrementing gauge."""
        gauge = Gauge("active_connections")

        gauge.set(10.0)
        gauge.dec()
        gauge.dec(amount=2.0)

        assert gauge.get() == 7.0

    def test_gauge_increment_with_labels(self):
        """Test incrementing gauge with labels."""
        gauge = Gauge("active_connections")

        gauge.inc({"pool": "main"})
        gauge.inc({"pool": "main"})
        gauge.inc({"pool": "backup"})

        assert gauge.get({"pool": "main"}) == 2.0
        assert gauge.get({"pool": "backup"}) == 1.0

    def test_gauge_samples(self):
        """Test getting all samples from gauge."""
        gauge = Gauge("memory_bytes")

        gauge.set(1024.0, {"type": "rss"})
        gauge.set(2048.0, {"type": "vms"})

        samples = gauge.samples()

        assert len(samples) == 2
        assert all(isinstance(s, MetricSample) for s in samples)


class TestHistogram:
    """Test Histogram metric type."""

    def test_histogram_initialization(self):
        """Test histogram initializes correctly."""
        histogram = Histogram("request_duration", "Request duration in seconds")

        assert histogram.name == "request_duration"
        assert histogram.help_text == "Request duration in seconds"
        assert histogram.buckets == Histogram.DEFAULT_BUCKETS

    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        buckets = [0.1, 0.5, 1.0, 5.0]
        histogram = Histogram("request_duration", buckets=buckets)

        assert histogram.buckets == buckets

    def test_histogram_observe(self):
        """Test observing values in histogram."""
        histogram = Histogram("request_duration")

        histogram.observe(0.05)
        histogram.observe(0.15)
        histogram.observe(0.75)

        assert histogram.get_count() == 3
        assert histogram.get_sum() == 0.95

    def test_histogram_observe_with_labels(self):
        """Test observing values with labels."""
        histogram = Histogram("request_duration")

        histogram.observe(0.1, {"method": "GET"})
        histogram.observe(0.2, {"method": "GET"})
        histogram.observe(0.5, {"method": "POST"})

        assert histogram.get_count({"method": "GET"}) == 2
        assert histogram.get_sum({"method": "GET"}) == pytest.approx(0.3)
        assert histogram.get_count({"method": "POST"}) == 1

    def test_histogram_buckets_distribution(self):
        """Test that observations are distributed into buckets correctly."""
        buckets = [0.1, 0.5, 1.0, 5.0]
        histogram = Histogram("request_duration", buckets=buckets)

        histogram.observe(0.05)  # Falls in 0.1 bucket
        histogram.observe(0.3)  # Falls in 0.5 bucket
        histogram.observe(0.7)  # Falls in 1.0 bucket
        histogram.observe(3.0)  # Falls in 5.0 bucket

        bucket_data = histogram.get_buckets()

        assert bucket_data[0] == (0.1, 1)  # 0.05 <= 0.1
        assert bucket_data[1] == (0.5, 2)  # 0.05, 0.3 <= 0.5
        assert bucket_data[2] == (1.0, 3)  # 0.05, 0.3, 0.7 <= 1.0
        assert bucket_data[3] == (5.0, 4)  # all values <= 5.0

    def test_histogram_buckets_cumulative(self):
        """Test that bucket counts are cumulative."""
        histogram = Histogram("request_duration", buckets=[1.0, 5.0, 10.0])

        histogram.observe(0.5)
        histogram.observe(3.0)
        histogram.observe(7.0)

        buckets = histogram.get_buckets()

        assert buckets[0][1] == 1  # 1 value <= 1.0
        assert buckets[1][1] == 2  # 2 values <= 5.0
        assert buckets[2][1] == 3  # 3 values <= 10.0

    def test_histogram_samples(self):
        """Test getting all samples from histogram."""
        histogram = Histogram("request_duration")

        histogram.observe(0.1, {"method": "GET"})
        histogram.observe(0.2, {"method": "POST"})

        samples = histogram.samples()

        assert len(samples) == 2
        for labels, total_sum, count, buckets in samples:
            assert isinstance(labels, dict)
            assert isinstance(total_sum, float)
            assert isinstance(count, int)
            assert isinstance(buckets, list)

    def test_histogram_average_calculation(self):
        """Test calculating average from histogram data."""
        histogram = Histogram("request_duration")

        histogram.observe(0.1)
        histogram.observe(0.2)
        histogram.observe(0.3)

        total_sum = histogram.get_sum()
        count = histogram.get_count()
        average = total_sum / count

        assert average == pytest.approx(0.2)


class TestMetricsStorage:
    """Test MetricsStorage registry."""

    def test_storage_initialization(self):
        """Test storage initializes correctly."""
        storage = MetricsStorage()

        assert storage.enabled is False
        assert len(storage.counters) == 0
        assert len(storage.gauges) == 0
        assert len(storage.histograms) == 0

    def test_storage_enable_disable(self):
        """Test enabling and disabling storage."""
        storage = MetricsStorage()

        storage.enable()
        assert storage.enabled is True

        storage.disable()
        assert storage.enabled is False

    def test_storage_get_or_create_counter(self):
        """Test getting or creating counter."""
        storage = MetricsStorage()

        counter1 = storage.counter("requests_total", "Total requests")
        counter2 = storage.counter("requests_total")

        assert counter1 is counter2
        assert counter1.name == "requests_total"
        assert counter1.help_text == "Total requests"

    def test_storage_get_or_create_gauge(self):
        """Test getting or creating gauge."""
        storage = MetricsStorage()

        gauge1 = storage.gauge("memory_bytes", "Memory usage")
        gauge2 = storage.gauge("memory_bytes")

        assert gauge1 is gauge2
        assert gauge1.name == "memory_bytes"

    def test_storage_get_or_create_histogram(self):
        """Test getting or creating histogram."""
        storage = MetricsStorage()

        histogram1 = storage.histogram("request_duration", "Request duration")
        histogram2 = storage.histogram("request_duration")

        assert histogram1 is histogram2
        assert histogram1.name == "request_duration"

    def test_storage_multiple_metrics(self):
        """Test storing multiple different metrics."""
        storage = MetricsStorage()

        storage.counter("requests_total")
        storage.counter("errors_total")
        storage.gauge("memory_bytes")
        storage.histogram("request_duration")

        assert len(storage.counters) == 2
        assert len(storage.gauges) == 1
        assert len(storage.histograms) == 1

    def test_storage_get_all_metrics(self):
        """Test getting all registered metrics."""
        storage = MetricsStorage()

        storage.counter("requests_total")
        storage.gauge("memory_bytes")
        storage.histogram("request_duration")

        all_metrics = storage.get_all_metrics()

        assert "requests_total" in all_metrics["counters"]
        assert "memory_bytes" in all_metrics["gauges"]
        assert "request_duration" in all_metrics["histograms"]

    def test_storage_metrics_independence(self):
        """Test that metrics from different storages are independent."""
        storage1 = MetricsStorage()
        storage2 = MetricsStorage()

        counter1 = storage1.counter("requests_total")
        counter2 = storage2.counter("requests_total")

        counter1.inc()
        counter1.inc()

        assert counter1.get() == 2.0
        assert counter2.get() == 0.0


class TestMetricSample:
    """Test MetricSample data class."""

    def test_sample_creation(self):
        """Test creating metric sample."""
        sample = MetricSample(labels={"method": "GET"}, value=42.0)

        assert sample.labels == {"method": "GET"}
        assert sample.value == 42.0
        assert sample.timestamp is not None

    def test_sample_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        sample1 = MetricSample(labels={}, value=1.0)
        time.sleep(0.01)
        sample2 = MetricSample(labels={}, value=2.0)

        assert sample2.timestamp > sample1.timestamp


class TestMetricsIntegration:
    """Integration tests for metrics components."""

    def test_counter_workflow(self):
        """Test complete counter workflow."""
        storage = MetricsStorage()
        storage.enable()

        counter = storage.counter("http_requests_total", "Total HTTP requests")

        counter.inc({"method": "GET", "status": "200"})
        counter.inc({"method": "GET", "status": "200"})
        counter.inc({"method": "POST", "status": "201"})
        counter.inc({"method": "GET", "status": "404"})

        assert counter.get({"method": "GET", "status": "200"}) == 2.0
        assert counter.get({"method": "POST", "status": "201"}) == 1.0
        assert counter.get({"method": "GET", "status": "404"}) == 1.0

        samples = counter.samples()
        assert len(samples) == 3

    def test_histogram_workflow(self):
        """Test complete histogram workflow."""
        storage = MetricsStorage()
        storage.enable()

        histogram = storage.histogram("request_duration_seconds")

        durations = [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
        for duration in durations:
            histogram.observe(duration, {"method": "GET"})

        assert histogram.get_count({"method": "GET"}) == 7
        assert histogram.get_sum({"method": "GET"}) == sum(durations)

        buckets = histogram.get_buckets({"method": "GET"})
        assert len(buckets) > 0

    def test_gauge_workflow(self):
        """Test complete gauge workflow."""
        storage = MetricsStorage()
        storage.enable()

        gauge = storage.gauge("active_connections")

        gauge.inc()
        gauge.inc()
        gauge.inc()
        assert gauge.get() == 3.0

        gauge.dec()
        assert gauge.get() == 2.0

        gauge.set(10.0)
        assert gauge.get() == 10.0

    def test_multiple_metrics_workflow(self):
        """Test using multiple metric types together."""
        storage = MetricsStorage()
        storage.enable()

        requests = storage.counter("requests_total")
        active = storage.gauge("active_requests")
        duration = storage.histogram("request_duration_seconds")

        active.inc()
        requests.inc({"status": "200"})
        duration.observe(0.5, {"endpoint": "/api/users"})
        active.dec()

        assert requests.get({"status": "200"}) == 1.0
        assert active.get() == 0.0
        assert duration.get_count({"endpoint": "/api/users"}) == 1

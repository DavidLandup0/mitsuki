# Instrumentation & Metrics

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Instrumentation Approaches](#instrumentation-approaches)
- [Metrics Endpoints](#metrics-endpoints)
- [Scheduler Metrics](#scheduler-metrics)
- [Custom Metrics](#custom-metrics)
- [Configuration](#configuration)
- [Integration with Prometheus & Grafana](#integration-with-prometheus--grafana)
- [Complete Example](#complete-example)

## Overview

Mitsuki provides built-in instrumentation for monitoring application performance and behavior:

- **HTTP requests**: Request counts, latency percentiles, status codes
- **Scheduled tasks**: Execution counts, durations, failures
- **Component calls**: Method execution times, error rates
- **System resources**: CPU usage, memory consumption
- **Custom metrics**: Track application-specific operational data

All metrics are exposed through unified endpoints in both human-readable and Prometheus-compatible formats.

## Quick Start

### 1. Install

Instrumentation samples process CPU and memory through `psutil`, which ships
as an optional extra:

```bash
pip install "mitsuki[metrics]"
```

Enabling instrumentation without it fails at startup with an error naming the
extra. Metrics endpoints, scheduler metrics and custom metrics work without it.

### 2. Enable in Configuration

Add to `application.yml`:

```yaml
instrumentation:
  enabled: true
  track_memory: false

metrics:
  enabled: true
  path: /metrics
  allowed_ips: []  # Empty list = allow all
```

`instrumentation.enabled` requires `metrics.enabled`. Without it, instrumentation
stays off and a warning is logged, since nothing would expose the metrics.

### 3. Apply Instrumentation

Choose one of two approaches:

**Option A: Instrument everything**

```python
from mitsuki import Application
from mitsuki.core.instrumentation import Instrumented

@Instrumented()
@Application
class App:
    pass
```

**Option B: Instrument specific components**

```python
from mitsuki import Service
from mitsuki.core.instrumentation import Instrumented

@Instrumented()
@Service()
class UserService:
    async def get_user(self, user_id: int):
        return user
```

### 4. View Metrics

Start your application and access:
- **Human-readable**: `http://localhost:8000/metrics`
- **Prometheus format**: `http://localhost:8000/metrics/prometheus`

## Instrumentation Approaches

### Application-Level Instrumentation

Apply `@Instrumented()` to your `@Application` class to automatically instrument all components:

```python
from mitsuki import Application
from mitsuki.core.instrumentation import Instrumented

@Instrumented()
@Application
class App:
    pass
```

This automatically wraps all public methods in:
- `@Service` classes
- `@Repository` classes
- `@RestController` classes

**What gets instrumented:**

```python
# All of these are automatically instrumented:

@Service()
class UserService:
    async def get_user(self, user_id: int):  # ✓ Tracked
        return user

    def _internal_helper(self):  # ✗ Skipped (private method)
        pass

@Repository()
class UserRepository:
    async def find_by_email(self, email: str):  # ✓ Tracked
        return user

@RestController("/api/users")
class UserController:
    @GetMapping("/{user_id}")
    async def get_user(self, user_id: int):  # ✓ Tracked (HTTP + component)
        return user
```

### Component-Level Instrumentation

Apply `@Instrumented()` to individual components for fine-grained control:

```python
from mitsuki import Service, Repository
from mitsuki.core.instrumentation import Instrumented

# Only this service is instrumented
@Instrumented()
@Service()
class OrderService:
    async def create_order(self, data: dict):
        return order

# This service is NOT instrumented
@Service()
class EmailService:
    async def send_email(self, to: str, subject: str):
        pass
```

**Selective instrumentation:**

```python
from mitsuki import Service
from mitsuki.core.instrumentation import Instrumented

# Instrument critical business logic
@Instrumented()
@Service()
class PaymentService:
    async def process_payment(self, amount: float):  # Tracked
        pass

# Don't instrument high-frequency background tasks
@Service()
class CacheWarmer:
    async def warm_cache(self):  # Not tracked
        pass
```

### Disabling Instrumentation

Explicitly disable instrumentation on a component:

```python
@Instrumented(enabled=False)
@Service()
class NoInstrumentationService:
    async def fast_operation(self):  # Not tracked
        pass
```

Or disable globally in configuration:

```yaml
instrumentation:
  enabled: false
```

### What Gets Tracked

**HTTP Metrics** (automatic for all HTTP requests):
- Request count by method, route and status code
- Response time distribution (histograms for percentiles)

The `path` label holds the matched route template (`/users/{user_id}`), not the
requested URL, so metric cardinality stays bounded by the size of the route
table. Requests that match no route are labelled `<unmatched>`.

**Component Metrics** (for instrumented components):
- Method call count (success vs failure), labelled by component and method
- Execution time per method
- Error rates

**Scheduler Metrics** (automatic when scheduler is enabled):
- Task execution count (success vs failure)
- Task execution duration
- Number of running tasks

**System Metrics** (automatic when instrumentation is enabled):
- CPU usage percentage
- Memory usage (RSS, VMS)
- Python traced memory, current and peak — only when `track_memory: true`

**Note:** Private methods (starting with `_`) are never instrumented.

**Which classes can be instrumented:** `@Service`, `@Repository`,
`@CrudRepository` and `@RestController` classes. `@Instrumented` has no effect
on a plain `@Component`.

For a `@CrudRepository`, every method is recorded under the repository's name:
the built-in methods (`save`, `find_by_id`, `find_all`, ...), query methods
implemented from their names (`find_by_email`), `@Query` methods and methods
you implement yourself:

```python
@CrudRepository(entity=User)
class UserRepository:
    async def find_by_email(self, email: str) -> Optional[User]: ...  # ✓ Tracked

    async def count_active(self) -> int:  # ✓ Tracked
        return len(await self.find_by_active(True))  # ✓ Tracked as well
```

**Inheritance:** a call is recorded once, under the class of the instance it
was made on. If an instrumented component inherits from another instrumented
component, calls made through the subclass are labelled with the subclass
name. A subclass that opts out with `@Instrumented(enabled=False)` is still
recorded for the methods it inherits from an instrumented parent, since those
calls go through the parent's instrumentation.

**Metrics endpoints:** requests to `/metrics` and `/metrics/prometheus` are
not recorded, so scrapes never appear in HTTP or component metrics.

## Metrics Endpoints

### /metrics (Mitsuki Format)

Human-readable JSON with computed aggregations:

```bash
curl http://localhost:8000/metrics | jq
```

Example response:

```json
{
  "enabled": true,
  "timestamp": "2025-12-15T10:30:00.000000",
  "instrumentation": {
    "system": {
      "memory": {"rss_mb": 85.2, "vms_mb": 150.3},
      "cpu": {"percent": 1.2}
    },
    "http": {
      "total_requests": 150,
      "requests_by_method": {"GET": 100, "POST": 50},
      "responses_by_status": {"200": 140, "404": 10},
      "latency": {"avg_ms": 8.5}
    },
    "components": {
      "UserService": {
        "calls": 120,
        "avg_duration_ms": 5.2,
        "methods": {
          "get_user": {"calls": 100, "avg_duration_ms": 4.1},
          "create_user": {"calls": 20, "avg_duration_ms": 10.7}
        }
      }
    }
  }
}
```

### /metrics/prometheus (Prometheus Format)

Flat text format compatible with Prometheus scraping:

```bash
curl http://localhost:8000/metrics/prometheus
```

Example response:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/users/{user_id}",status="200"} 100.0

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/api/users/{user_id}",le="0.005"} 50
http_request_duration_seconds_bucket{method="GET",path="/api/users/{user_id}",le="0.01"} 80
http_request_duration_seconds_sum{method="GET",path="/api/users/{user_id}"} 0.75
http_request_duration_seconds_count{method="GET",path="/api/users/{user_id}"} 100

# HELP component_calls_total Component method calls
# TYPE component_calls_total counter
component_calls_total{component="UserService",method="get_user",status="success"} 100.0

# HELP scheduler_task_executions_total Total number of scheduled task executions
# TYPE scheduler_task_executions_total counter
scheduler_task_executions_total{task="BackgroundService.cleanup",status="success"} 42.0

# HELP scheduler_task_duration_seconds Scheduled task execution duration in seconds
# TYPE scheduler_task_duration_seconds histogram
scheduler_task_duration_seconds_bucket{task="BackgroundService.cleanup",le="0.005"} 10
scheduler_task_duration_seconds_sum{task="BackgroundService.cleanup"} 5.25
scheduler_task_duration_seconds_count{task="BackgroundService.cleanup"} 42
```

## Scheduler Metrics

When the scheduler and metrics are enabled, Mitsuki automatically records metrics for all `@Scheduled` tasks. Scheduler metrics need only `scheduler.enabled` and `metrics.enabled`; `instrumentation.enabled` governs HTTP and component instrumentation and is not required here.

**Configuration:**
```yaml
scheduler:
  enabled: true

metrics:
  enabled: true
```

**Metrics tracked:**
- `scheduler_task_executions_total` - Counter with labels `{task, status}`
- `scheduler_task_duration_seconds` - Histogram with label `{task}`
- `scheduler_tasks_running` - Gauge with label `{task}`, counting executions currently in flight

**Example queries:**

```promql
# Task execution rate
rate(scheduler_task_executions_total{task="BackgroundService.cleanup"}[5m])

# Task failure rate
rate(scheduler_task_executions_total{status="failure"}[5m]) / rate(scheduler_task_executions_total[5m])

# Average task duration
rate(scheduler_task_duration_seconds_sum[5m]) / rate(scheduler_task_duration_seconds_count[5m])

# P95 task duration
histogram_quantile(0.95, sum(rate(scheduler_task_duration_seconds_bucket[5m])) by (le, task))

# Currently running tasks
scheduler_tasks_running
```

These metrics are automatically included in both `/metrics` and `/metrics/prometheus` endpoints.

For more information on creating scheduled tasks, see [Scheduled Tasks](./14_scheduled_tasks.md).

## Custom Metrics

Track application-specific operational data using `InstrumentationProvider`.

### Basic Usage

Inject `InstrumentationProvider` into your component:

```python
from mitsuki import Service
from mitsuki.core.instrumentation import InstrumentationProvider

@Service()
class OrderService:
    def __init__(self, instrumentation: InstrumentationProvider):
        self.instrumentation = instrumentation

    async def create_order(self, user_id: int):
        order = await self.save_order(user_id)

        # Record custom metric
        self.instrumentation.record_metric(
            metric_name="orders_created_total",
            value=1,
            labels={"source": "api"}
        )

        return order
```

### Recording Metrics

The `record_metric` method accepts:
- `metric_name` (str): Metric identifier
- `value` (float): Value to record
- `labels` (dict): Dimensional data for filtering/grouping

All custom metrics are stored as counters (monotonically increasing values).

Metric names must match `[a-zA-Z_:][a-zA-Z0-9_:]*` and label names
`[a-zA-Z_][a-zA-Z0-9_]*` (label names starting with `__` are reserved). A name
already used by a built-in gauge or histogram cannot be reused for a counter.
`record_metric` raises `ValueError` for any of these, even while metrics are
disabled, since a single invalid name would make Prometheus reject the entire
scrape.

::: tip NOTE
The `record_metric` method is designed for **counters only** (e.g., counting events). It is not suitable for tracking durations or other values where you would need averages or percentiles. For those use cases, direct integration with a metrics library would be required.
:::

### Examples

**Track database operations:**

```python
@Service()
class ProductService:
    def __init__(self, repo: ProductRepository, instrumentation: InstrumentationProvider):
        self.repo = repo
        self.instrumentation = instrumentation

    async def create_product(self, data: dict):
        product = await self.repo.save(data)

        # Track write operations
        self.instrumentation.record_metric(
            metric_name="database_writes_total",
            value=1,
            labels={"table": "products", "operation": "insert"}
        )

        return product

    async def get_all_products(self):
        products = await self.repo.find_all()

        # Track query result size
        self.instrumentation.record_metric(
            metric_name="database_query_rows_returned",
            value=len(products),
            labels={"table": "products", "query_type": "find_all"}
        )

        # Flag expensive full table scans
        self.instrumentation.record_metric(
            metric_name="database_full_scan_total",
            value=1,
            labels={"table": "products"}
        )

        return products
```

**Track cache performance:**

```python
@Service()
class CacheService:
    def __init__(self, instrumentation: InstrumentationProvider):
        self.instrumentation = instrumentation
        self.cache = {}

    async def get(self, key: str):
        if key in self.cache:
            # Cache hit
            self.instrumentation.record_metric(
                metric_name="cache_operations_total",
                value=1,
                labels={"operation": "hit", "cache_name": "user_cache"}
            )
            return self.cache[key]

        # Cache miss
        self.instrumentation.record_metric(
            metric_name="cache_operations_total",
            value=1,
            labels={"operation": "miss", "cache_name": "user_cache"}
        )
        return None
```

**Track external API calls:**

```python
@Service()
class PaymentService:
    def __init__(self, instrumentation: InstrumentationProvider):
        self.instrumentation = instrumentation

    async def charge_card(self, amount: float):
        try:
            response = await self.stripe_api.charge(amount)

            # Track successful API call
            self.instrumentation.record_metric(
                metric_name="external_api_calls_total",
                value=1,
                labels={"service": "stripe", "status": "success"}
            )
            return response
        except Exception as e:
            # Track failed API call
            self.instrumentation.record_metric(
                metric_name="external_api_calls_total",
                value=1,
                labels={"service": "stripe", "status": "failure"}
            )
            raise
```

**Track business events:**

```python
@Service()
class SubscriptionService:
    def __init__(self, instrumentation: InstrumentationProvider):
        self.instrumentation = instrumentation

    async def upgrade_subscription(self, user_id: int, plan: str):
        # Perform upgrade logic...

        # Track subscription changes
        self.instrumentation.record_metric(
            metric_name="subscription_changes_total",
            value=1,
            labels={"action": "upgrade", "plan": plan}
        )
```

## Configuration

### Basic Configuration

```yaml
instrumentation:
  enabled: true          # Enable/disable instrumentation
  track_memory: false    # Also collect Python traced memory (tracemalloc)

metrics:
  enabled: true          # Enable metrics endpoints
  path: /metrics         # Base path for metrics
  allowed_ips: []        # Empty = allow all IPs
```

### IP Allowlisting

Restrict access to metrics endpoints by IP:

::: warning Reverse Proxies and Security
The IP check is performed on the direct incoming request's IP address (`request.client.host`). If your application is running behind a reverse proxy, load balancer, or cloud gateway (like Nginx or an AWS ALB), this IP will be that of the proxy, not the original user.

You are responsible for ensuring your network configuration is secure. In a proxied setup, you should typically configure the proxy to handle access control or add your proxy's trusted IP addresses to the `allowed_ips` list.
:::

```yaml
metrics:
  enabled: true
  allowed_ips:
    - "127.0.0.1"              # Localhost
    - "10.0.0.0/8"             # Private network
    - "172.16.0.0/12"          # Docker networks (172.16-31.x.x)
    - "192.168.0.0/16"         # Home/office network
```

Entries are parsed when the application starts; an invalid entry fails
startup with an error naming it. Addresses are compared as addresses, so
`::ffff:127.0.0.1` (an IPv4 client on a dual-stack listener) matches
`127.0.0.1`. When `allowed_ips` is non-empty, a client whose address the server
does not report, or reports as something other than an IP, is denied.

When access is denied:
1. Warning logged: `WARNING Metrics access denied for IP: 192.168.1.100`
2. HTTP 404 returned (hides endpoint existence)

### Environment Variables

Override configuration via environment variables:

```bash
export INSTRUMENTATION_ENABLED=true
export INSTRUMENTATION_TRACK_MEMORY=false
export METRICS_ENABLED=true
export METRICS_PATH=/metrics
```

### Multiple Workers

Metrics are stored in the memory of the process that records them. With
`server.workers` greater than 1, each worker keeps its own separate counters,
histograms and gauges, and each request to `/metrics` or `/metrics/prometheus`
is answered by whichever worker receives it. Consecutive Prometheus scrapes
can therefore hit different workers, which Prometheus reads as counters
jumping up and down or resetting, and `rate()` results become unreliable.

This is a current limitation. Until metrics are aggregated across workers,
run instrumented applications with a single worker per process and scale by
running more processes, each scraped as its own Prometheus target:

```yaml
server:
  workers: 1
```

Scheduled tasks have the same per-worker behaviour; see
[Multi-Worker Considerations](./14_scheduled_tasks.md#multi-worker-considerations).

### Memory Tracking

Whenever instrumentation is enabled, Mitsuki samples process CPU and memory
(RSS and VMS) via `psutil` every 5 seconds. These are cheap and always
collected.

`track_memory` additionally reports Python's traced memory (current and peak)
via `tracemalloc`. This adds significant allocation overhead, so it defaults to
`false` and should stay off unless you are actively investigating memory.

```yaml
instrumentation:
  track_memory: false
```

## Integration with Prometheus & Grafana

### Prometheus Scraping

Configure Prometheus to scrape your Mitsuki application:

`prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'mitsuki'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/prometheus'
```

### Grafana Dashboard

Mitsuki ships a ready-made Grafana dashboard covering HTTP, component (including
per-method breakdowns), scheduler and system metrics. Write it out with the CLI:

```bash
# Write dashboard.json into the current directory
mitsuki grafana-dashboard

# Or into a specific directory (created if needed)
mitsuki grafana-dashboard -o ./grafana/dashboards/
```

Point a Grafana [dashboard provider](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
at the output directory, or import the file through the Grafana UI. The
dashboard queries a Prometheus datasource scraping `/metrics/prometheus`.

For a fully wired setup that generates and provisions the dashboard
automatically, see the [instrumentation demo](../examples/instrumentation_demo).

### Grafana Queries

While it's up to you to write queries useful for your particular use-case, here are a few generic examples:

**Request rate:**
```promql
rate(http_requests_total[5m])
```

**Average response time:**
```promql
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

**P95 latency:**
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**Error rate:**
```promql
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

**Component call rate:**
```promql
rate(component_calls_total{component="UserService"}[5m])
```

**Custom metric (database writes):**
```promql
rate(database_writes_total{table="users"}[5m])
```

**Scheduler task execution rate:**
```promql
rate(scheduler_task_executions_total[5m])
```

**Scheduler task failure rate:**
```promql
rate(scheduler_task_executions_total{status="failure"}[5m]) / rate(scheduler_task_executions_total[5m])
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      # For illustrative purposes, anonymous mode
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
```

## Complete Example

For a full working example, check out the `examples/instrumentation_demo` app:

```bash
cd examples/instrumentation_demo
docker compose up -d --build
```

Includes:
- Application-level instrumentation setup
- Custom operational metrics
- Pre-configured Grafana dashboards
- Prometheus + Grafana integration

## Next Steps

- [Scheduled Tasks](./14_scheduled_tasks.md) - Learn about creating scheduled tasks
- [Configuration](./06_configuration.md) - Learn more about `application.yml`
- [Decorators](./02_decorators.md) - Understand `@Service`, `@Repository`, `@RestController`
- [Controllers](./04_controllers.md) - Build HTTP endpoints

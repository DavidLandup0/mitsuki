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

### 1. Enable in Configuration

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

### 2. Apply Instrumentation

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

### 3. View Metrics

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
- Request count by method, path, and status code
- Response time distribution (histograms for percentiles)

**Component Metrics** (for instrumented components):
- Method call count (success vs failure)
- Execution time per method
- Error rates

**Scheduler Metrics** (automatic when scheduler is enabled):
- Task execution count (success vs failure)
- Task execution duration
- Number of running tasks

**System Metrics** (when `instrumentation.enabled: true`):
- CPU usage percentage
- Memory usage (RSS, VMS)

**Note:** Private methods (starting with `_`) are never instrumented.

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
      "UserService": {"calls": 120, "avg_duration_ms": 5.2},
      "OrderService": {"calls": 80, "avg_duration_ms": 12.1}
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
http_requests_total{method="GET",path="/api/users",status="200"} 100.0

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/api/users",le="0.005"} 50
http_request_duration_seconds_bucket{method="GET",path="/api/users",le="0.01"} 80
http_request_duration_seconds_sum{method="GET",path="/api/users"} 0.75
http_request_duration_seconds_count{method="GET",path="/api/users"} 100

# HELP component_calls_total Component method calls
# TYPE component_calls_total counter
component_calls_total{component="UserService",status="success"} 120.0

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

When the scheduler is enabled, Mitsuki automatically records metrics for all `@Scheduled` tasks:

**Metrics tracked:**
- `scheduler_task_executions_total` - Counter with labels `{task, status}`
- `scheduler_task_duration_seconds` - Histogram with label `{task}`
- `scheduler_tasks_running` - Gauge with label `{task}`

**Example queries:**

```promql
# Task execution rate
rate(scheduler_task_executions_total{task="BackgroundService.cleanup"}[5m])

# Task failure rate
rate(scheduler_task_executions_total{status="failure"}[5m]) / rate(scheduler_task_executions_total[5m])

# Average task duration
rate(scheduler_task_duration_seconds_sum[5m]) / rate(scheduler_task_duration_seconds_count[5m])

# P95 task duration
histogram_quantile(0.95, rate(scheduler_task_duration_seconds_bucket[5m]))

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
  track_memory: false    # Track memory with tracemalloc

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

### Memory Tracking

When `track_memory: true`:
- Uses Python's `tracemalloc` module
- Provides RSS, VMS, and traced memory metrics

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
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
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
docker-compose up -d
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

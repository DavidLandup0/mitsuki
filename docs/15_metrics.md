# Metrics and Observability

Monitor your Mitsuki application with built-in metrics endpoints. Currently, only supports scheduler metrics, when used with `@Scheduled`, but an expansion is planned.

## Table of Contents

- [Overview](#overview)
- [Scheduler Metrics](#scheduler-metrics)
- [Configuration](#configuration)
- [Custom Metrics](#custom-metrics)
- [Integration with Monitoring Tools](#integration-with-monitoring-tools)


## Overview

Mitsuki provides optional metrics endpoints to expose runtime information about your application. Metrics are disabled by default and can be enabled via configuration.

**Available Metrics:**
- ✅ Scheduler task statistics (`/metrics` - when scheduler metrics enabled)
- ⏳ Database connection pool stats (planned)
- ⏳ HTTP request metrics (planned)
- ⏳ Custom application metrics (planned)


## Scheduler Metrics

### Enable Scheduler Metrics

**Configuration** (`application.yml`):
```yaml
scheduler:
  metrics:
    enabled: true
    path: /metrics  # Optional, defaults to /metrics
```

**Environment Variable:**
```bash
MITSUKI_SCHEDULER_METRICS_ENABLED=true
MITSUKI_SCHEDULER_METRICS_PATH=/custom/metrics  # Optional
```

### Accessing Metrics

Once enabled, visit the configured endpoint:

```bash
curl http://localhost:8000/metrics
```

**Response:**
```json
{
  "tasks": [
    {
      "name": "TaskService.background_job",
      "type": "fixed_rate",
      "interval": 5000,
      "status": "running",
      "executions": 120,
      "failures": 0,
      "last_execution": "2025-11-15T10:30:45.123456",
      "last_duration_ms": 45.2,
      "average_duration_ms": 42.8
    }
  ],
  "total_tasks": 1,
  "running_tasks": 1
}
```

### Metric Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Task identifier (`ClassName.methodName`) |
| `type` | string | `fixed_rate`, `fixed_delay`, or `cron` |
| `interval` | int/string | Milliseconds for rate/delay, cron expression for cron tasks |
| `status` | string | `pending`, `running`, `stopped`, or `error` |
| `executions` | int | Number of successful executions |
| `failures` | int | Number of failed executions |
| `last_execution` | string | ISO 8601 timestamp of last execution |
| `last_duration_ms` | float | Duration of last execution in milliseconds |
| `average_duration_ms` | float | Average execution duration across all runs |

### Use Cases

**1. Health Checks**

```python
import httpx

async def check_scheduler_health():
    """Check if scheduled tasks are running properly."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/metrics")
        metrics = response.json()

        # Alert if any tasks have high failure rate
        for task in metrics["tasks"]:
            if task["failures"] > 0:
                total = task["executions"] + task["failures"]
                failure_rate = task["failures"] / total
                if failure_rate > 0.1:
                    print(f"Alert: {task['name']} has {failure_rate*100:.1f}% failure rate")

        # Alert if tasks aren't running
        if metrics["running_tasks"] < metrics["total_tasks"]:
            print(f"Warning: Only {metrics['running_tasks']}/{metrics['total_tasks']} tasks running")
```

**2. Performance Monitoring**

```python
async def monitor_task_performance():
    """Monitor task execution times."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/metrics")
        metrics = response.json()

        for task in metrics["tasks"]:
            avg_duration = task["average_duration_ms"]
            last_duration = task["last_duration_ms"]

            # Alert if last execution was much slower than average
            if last_duration and avg_duration:
                if last_duration > avg_duration * 2:
                    print(f"Performance degradation in {task['name']}")
                    print(f"  Average: {avg_duration:.1f}ms")
                    print(f"  Last: {last_duration:.1f}ms")
```

**3. Custom Dashboards**

Integrate with your application:

```python
from mitsuki import GetMapping, RestController
from mitsuki.core.scheduler import get_scheduler

@RestController("/admin")
class DashboardController:
    @GetMapping("/dashboard")
    async def dashboard(self) -> dict:
        """Comprehensive dashboard data."""
        scheduler = get_scheduler()
        scheduler_stats = scheduler.get_task_statistics()

        # Add your custom metrics
        return {
            "scheduler": scheduler_stats,
            "application": {
                "version": "1.0.0",
                "uptime_seconds": get_uptime(),
            },
            # Add database, cache, etc. stats here
        }
```


## Configuration

### Custom Metrics Path

Change the metrics endpoint path:

```yaml
scheduler:
  metrics:
    enabled: true
    path: /admin/metrics  # Custom path
```

This is useful if you want to use `/metrics` for something else, or prefer a different naming convention.

### Security Considerations

**Metrics endpoints expose internal application state.** Consider these security measures:

**1. Disable in Production** (if not needed):
```yaml
# application-prod.yml
scheduler:
  metrics:
    enabled: false
```

**2. Protect with Authentication:**
```python
from mitsuki import GetMapping, RestController, ResponseEntity
from mitsuki.web.context import get_request
from mitsuki.core.scheduler import get_scheduler

@RestController("/protected")
class SecureMetricsController:
    @GetMapping("/metrics")
    async def secure_metrics(self) -> dict:
        """Metrics endpoint with basic auth."""
        request = get_request()
        auth = request.headers.get("Authorization")

        # Implement your auth logic
        if not auth or not verify_auth(auth):
            return ResponseEntity.unauthorized({"error": "Unauthorized"})

        scheduler = get_scheduler()
        return scheduler.get_task_statistics()
```

**3. Use Firewall Rules:**

Restrict access to metrics endpoints at the network level (e.g., only allow internal monitoring systems).

## Troubleshooting

### Metrics Endpoint Returns 404

**Cause:** Metrics are disabled or path is incorrect.

**Solution:**
1. Check configuration:
   ```yaml
   scheduler:
     metrics:
       enabled: true
   ```

2. Verify the path in your request matches configuration:
   ```yaml
   scheduler:
     metrics:
       path: /metrics  # Use this path in your request
   ```

### Metrics Show No Tasks

**Cause:** No scheduled tasks registered, or scheduler is disabled.

**Solution:**
1. Verify scheduler is enabled:
   ```yaml
   scheduler:
     enabled: true
   ```

2. Ensure you have `@Scheduled` methods in your services

3. Check logs for scheduler startup messages


## Next Steps

- [Scheduled Tasks](./14_scheduled_tasks.md) - Learn about creating scheduled tasks
- [Configuration](./06_configuration.md) - Configure metrics and monitoring
- [Logging](./12_logging.md) - Application logging and debugging

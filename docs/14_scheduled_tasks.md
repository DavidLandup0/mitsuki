# Scheduled Tasks

## Table of Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [Scheduling Options](#scheduling-options)
- [Complete Examples](#complete-examples)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Planned Features](#planned-features)


## Overview

Mitsuki provides built-in task scheduling through the `@Scheduled` decorator, inspired by Spring Boot's `@Scheduled` annotation. Schedule background tasks to run at fixed intervals without external dependencies.

**Features:**
- Fixed-rate scheduling (`fixed_rate`)
- Fixed-delay scheduling (`fixed_delay`)
- Cron expressions (`cron`)
- Cron macros (`@hourly`, `@daily`, etc.)
- Timezone support for cron expressions
- Initial delay before first execution (`initial_delay`)
- Task statistics and metrics
- Optional `/metrics` REST endpoint
- Async and sync method support
- Automatic error handling and logging
- Lifecycle integration (start/stop with application)
- Exceptions within a scheduled task don't stop the scheduler

## Basic Usage

### Simple Scheduled Task

```python
from mitsuki import Application, Service, Scheduled

@Service()
class NotificationService:
    def __init__(self):
        self.message_count = 0

    @Scheduled(fixed_rate=5000)  # Every 5 seconds
    async def send_pending_notifications(self):
        """Send pending notifications every 5 seconds."""
        print(f"Checking for notifications... ({self.message_count})")
        self.message_count += 1
        # Send notifications logic here

@Application
class MyApp:
    pass

if __name__ == "__main__":
    MyApp.run()
```

### With Initial Delay

```python
@Service()
class HealthCheckService:
    @Scheduled(fixed_rate=10000, initial_delay=5000)
    async def check_services(self):
        """
        Check service health every 10 seconds.
        Wait 5 seconds before first check to allow services to initialize.
        """
        print("Running health check...")
        # Health check logic
```

### Multiple Scheduled Tasks

```python
@Service()
class MaintenanceService:
    @Scheduled(fixed_rate=60000)  # Every minute
    async def cleanup_temp_files(self):
        """Clean up temporary files every minute."""
        print("Cleaning temp files...")

    @Scheduled(fixed_rate=300000)  # Every 5 minutes
    async def refresh_cache(self):
        """Refresh cache every 5 minutes."""
        print("Refreshing cache...")

    @Scheduled(fixed_rate=3600000, initial_delay=60000)  # Every hour
    async def generate_report(self):
        """Generate hourly report, starting 1 minute after startup."""
        print("Generating report...")
```


## Scheduling Options

### Fixed Rate

Execute at a fixed interval (time between **starts**):

```python
@Scheduled(fixed_rate=1000)  # milliseconds
async def task(self):
    """Runs every 1 second."""
    pass
```

**Timing:**
```
Start -> Execute -> 1000ms -> Execute -> 1000ms -> Execute
```

If a task takes 500ms, the next execution starts 1000ms after the *previous start*.

### Fixed Delay

Execute with a fixed delay **after** the previous execution completes:

```python
@Scheduled(fixed_delay=3000)  # 3 seconds after completion
async def process_queue(self):
    # This could take variable time
    await self.process_pending_items()
    # Next run starts 3 seconds after this completes
```

**Timing:**
```
Start -> Execute (2s) -> Wait 3000ms -> Execute (1s) -> Wait 3000ms -> Execute
```

**Difference**: `fixed_rate` maintains consistent intervals between starts, while `fixed_delay` waits after each completion. Use `fixed_delay` when task duration varies.

### Cron Expressions

Use standard cron syntax for complex schedules:

```python
@Scheduled(cron="0 0 2 * * *")  # Every day at 2 AM
async def daily_report(self):
    await self.generate_daily_report()

@Scheduled(cron="0 */15 * * * *")  # Every 15 minutes
async def check_health(self):
    await self.health_check()

@Scheduled(cron="0 0 9 * * MON-FRI")  # Weekdays at 9 AM
async def weekday_summary(self):
    await self.send_summary()
```

**Cron Format**: `second minute hour day month day_of_week`
- `*` = any value
- `*/N` = every N units
- `X-Y` = range from X to Y
- `X,Y,Z` = specific values

**Examples:**
- `"* * * * * *"` - Every second
- `"0 * * * * *"` - Every minute (at second 0)
- `"0 0 * * * *"` - Every hour
- `"0 0 2 * * *"` - Every day at 2:00 AM
- `"0 0 9 * * MON"` - Every Monday at 9:00 AM

### Cron Macros

Use convenient macros for common schedules:

```python
@Scheduled(cron="@hourly")  # Equivalent to "0 0 * * * *"
async def hourly_task(self):
    pass

@Scheduled(cron="@daily")  # Equivalent to "0 0 0 * * *"
async def daily_task(self):
    pass

@Scheduled(cron="@weekly")  # Equivalent to "0 0 0 * * 0" (Sunday)
async def weekly_task(self):
    pass
```

**Available Macros:**
- `@yearly` / `@annually` - Once a year (January 1st midnight)
- `@monthly` - Once a month (1st day midnight)
- `@weekly` - Once a week (Sunday midnight)
- `@daily` / `@midnight` - Once a day (midnight)
- `@hourly` - Once an hour

### Timezone Support

Specify timezone for cron expressions:

```python
@Scheduled(cron="0 0 9 * * *", timezone="America/New_York")
async def eastern_morning_task(self):
    """Runs at 9 AM Eastern Time."""
    pass

@Scheduled(cron="0 0 18 * * MON-FRI", timezone="Europe/London")
async def london_end_of_day(self):
    """Runs at 6 PM London time on weekdays."""
    pass
```

Use standard [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `"America/New_York"`, `"Europe/London"`, `"Asia/Tokyo"`).

### Initial Delay

Delay the first execution by a specified amount.

```python
@Scheduled(fixed_rate=5000, initial_delay=10000)
async def task(self):
    """Wait 10 seconds, then run every 5 seconds."""
    pass
```

**Timing:**
```
Start -> Wait 10000ms -> Execute -> 5000ms -> Execute -> 5000ms -> Execute
```

Useful for:
- Allowing services to initialize before running tasks
- Staggering task execution across services
- Delaying resource-intensive operations during startup

### Time Units

All time values are in **milliseconds**:

```python
# Common intervals
@Scheduled(fixed_rate=1000)      # 1 second
@Scheduled(fixed_rate=60000)     # 1 minute
@Scheduled(fixed_rate=300000)    # 5 minutes
@Scheduled(fixed_rate=3600000)   # 1 hour
@Scheduled(fixed_rate=86400000)  # 24 hours
```


## Usage Examples

### Background Email Service

```python
from mitsuki import Service, Scheduled
from typing import List

@Service()
class EmailService:
    def __init__(self):
        self.pending_emails: List[dict] = []

    def queue_email(self, to: str, subject: str, body: str):
        """Add email to queue."""
        self.pending_emails.append({
            "to": to,
            "subject": subject,
            "body": body
        })

    @Scheduled(fixed_rate=30000)  # Every 30 seconds
    async def send_batch(self):
        """Send pending emails in batches."""
        if not self.pending_emails:
            return

        batch = self.pending_emails[:10]  # Process 10 at a time
        self.pending_emails = self.pending_emails[10:]

        for email in batch:
            await self._send_email(email)
            print(f"Sent email to {email['to']}")

    async def _send_email(self, email: dict):
        """Actually send the email via SMTP."""
        # SMTP sending logic here
        pass
```

### Database Cleanup

```python
from datetime import datetime, timedelta
from mitsuki import Service, Scheduled, CrudRepository

@Service()
class CleanupService:
    def __init__(self, session_repo: SessionRepository):
        self.session_repo = session_repo

    @Scheduled(fixed_rate=3600000)  # Every hour
    async def cleanup_old_sessions(self):
        """Delete sessions older than 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        count = await self.session_repo.delete_by_created_at_less_than(cutoff)
        print(f"Cleaned up {count} old sessions")

    @Scheduled(fixed_rate=86400000, initial_delay=60000)  # Daily
    async def archive_old_logs(self):
        """Archive logs older than 30 days."""
        cutoff = datetime.now() - timedelta(days=30)
        # Archive logic
        print(f"Archived logs older than {cutoff}")
```

### Cache Refresh

```python
from mitsuki import Service, Scheduled

@Service()
class CacheService:
    def __init__(self):
        self.cache = {}

    @Scheduled(fixed_rate=600000)  # Every 10 minutes
    async def refresh_product_cache(self):
        """Refresh product catalog cache."""
        products = await self._fetch_products()
        self.cache['products'] = products
        print(f"Refreshed product cache")

    async def _fetch_products(self):
        # Database query
        return []
```

### Metrics Collection

```python
import psutil
from mitsuki import Service, Scheduled

@Service()
class MetricsService:
    def __init__(self):
        self.metrics_history = []

    @Scheduled(fixed_rate=60000)  # Every minute
    async def collect_system_metrics(self):
        """Collect CPU and memory metrics."""
        metrics = {
            'timestamp': datetime.now(),
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }

        self.metrics_history.append(metrics)

        # Keep last 60 minutes
        if len(self.metrics_history) > 60:
            self.metrics_history.pop(0)

        # Alert if CPU > 90%
        if metrics['cpu_percent'] > 90:
            await self._send_alert(f"High CPU: {metrics['cpu_percent']}%")

    async def _send_alert(self, message: str):
        print(f"ALERT: {message}")
```

### Synchronous Tasks

You can also schedule synchronous methods:

```python
@Service()
class FileService:
    @Scheduled(fixed_rate=300000)  # Every 5 minutes
    def cleanup_temp_directory(self):
        """Clean temp files (synchronous method)."""
        temp_dir = "/tmp/myapp"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            print("Cleaned temp directory")
```


## Configuration

### Enable/Disable Scheduler

You can control the scheduler globally in `application.yml`. It's not turned on by default, as it requires lifecycle management internally. Even with a `@Scheduled` method, it won't execute unless the scheduler is enabled and running.

This also makes it simple to disable the scheduler while maintaining your `@Scheduled` tasks, during remediation, debugging, etc.

```yaml
scheduler:
  enabled: true  # Set to false to disable all scheduled tasks
```

Or via environment variable:

```bash
MITSUKI_SCHEDULER_ENABLED=false python app.py
```

### Disable for Testing

In your test configuration (`application-test.yml`):

```yaml
scheduler:
  enabled: false  # Don't run scheduled tasks during tests
```

### Multi-Worker Considerations

**IMPORTANT:** When using multiple worker processes (`server.workers > 1`), each worker runs its own independent scheduler. This means scheduled tasks will execute **once per worker**. This is currently a design limitation, and will be approached at a later date.

**Example:** If you have 3 workers and a task scheduled to run every 10 seconds:
- The task will execute **3 times every 10 seconds** (once in each worker)
- Each worker maintains separate task statistics
- The `/metrics` endpoint will only show metrics for the worker that handles the request

You can always simply use a single worker:

1. **Single Worker (Recommended for @Scheduled):**
   ```yaml
   server:
     workers: 1  # Use single worker when using @Scheduled tasks
   ```

Or opt to instead use an external scheduler (cron, systemd timer, Kubernetes CronJob) to trigger HTTP endpoints:
2. **External Scheduler:**
   ```python
   @RestController("/tasks")
   class TaskController:
       def __init__(self, service: MyService):
           self.service = service

       @PostMapping("/run-cleanup")
       async def trigger_cleanup(self):
           """Endpoint for external scheduler to trigger."""
           await self.service.cleanup()
           return {"status": "started"}
   ```

   Then use cron:
   ```bash
   # Run every hour via cron
   0 * * * * curl -X POST http://localhost:8000/tasks/run-cleanup
   ```

**When to use multiple workers with @Scheduled:**
- Tasks that are worker-specific (e.g., local cache refresh per worker)
- Tasks where duplicate execution is acceptable or desired


## Best Practices

### 1. Handle Long-Running Tasks

```python
@Service()
class ReportService:
    @Scheduled(fixed_delay=3600000)  # Every hour
    async def generate_report(self):
        """Generate report - may take several minutes."""
        try:
            await self._generate_large_report()
        except Exception as e:
            # Tasks continue even if one fails
            print(f"Report generation failed: {e}")
```

**Note:** If a task takes longer than the interval, the next execution will start immediately after completion.

### 2. Use Initial Delay for Startup Tasks

```python
@Service()
class WarmupService:
    @Scheduled(fixed_rate=300000, initial_delay=30000)
    async def refresh_expensive_cache(self):
        """Wait 30s for startup, then refresh every 5 minutes."""
        # Give time for database connections, etc.
        await self._load_cache()
```

### 3. Dependency Injection Works

```python
@Service()
class ScheduledDataService:
    def __init__(self, user_repo: UserRepository, email_service: EmailService):
        self.user_repo = user_repo
        self.email_service = email_service

    @Scheduled(fixed_rate=86400000)  # Daily
    async def send_daily_summary(self):
        """Dependencies are automatically injected."""
        users = await self.user_repo.find_all()
        for user in users:
            await self.email_service.send_summary(user)
```

## Observability and Monitoring

### Metrics and Instrumentation

When the scheduler is enabled, Mitsuki automatically records metrics for all `@Scheduled` tasks through the instrumentation system. These metrics are exposed at `/metrics` and `/metrics/prometheus` endpoints.

**Enable metrics:**

```yaml
# application.yml
scheduler:
  enabled: true

instrumentation:
  enabled: true

metrics:
  enabled: true
  path: /metrics
```

**Metrics tracked automatically:**
- `scheduler_task_executions_total` - Counter with labels `{task, status}`
- `scheduler_task_duration_seconds` - Histogram with label `{task}`
- `scheduler_tasks_running` - Gauge with label `{task}`

**Example Prometheus queries:**

```promql
# Task execution rate
rate(scheduler_task_executions_total{task="BackgroundService.cleanup"}[5m])

# Task failure rate
rate(scheduler_task_executions_total{status="failure"}[5m]) / rate(scheduler_task_executions_total[5m])

# Average task duration
rate(scheduler_task_duration_seconds_sum[5m]) / rate(scheduler_task_duration_seconds_count[5m])

# P95 task duration
histogram_quantile(0.95, rate(scheduler_task_duration_seconds_bucket[5m]))
```

For complete documentation on metrics, instrumentation, and Prometheus/Grafana integration, see **[Instrumentation & Metrics](./15_metrics.md)**.

### Programmatic Access to Statistics

Get task statistics programmatically:

```python
from mitsuki import Service
from mitsuki.core.scheduler import get_scheduler

@Service()
class MonitoringService:
    def __init__(self):
        self.scheduler = get_scheduler()

    async def check_task_health(self):
        """Check if scheduled tasks are healthy."""
        stats = self.scheduler.get_task_statistics()

        for task in stats["tasks"]:
            if task["failures"] > 0:
                print(f"Warning: {task['name']} has {task['failures']} failures")

            if task["status"] != "running":
                print(f"Alert: {task['name']} is not running!")

        return stats

::: tip NOTE
The statistics returned by `get_task_statistics()` are held in the scheduler's local memory. This is different from the metrics collected by the instrumentation system, which are stored in a central registry and exposed at the `/metrics` endpoints. This method is best for direct, in--process checks, while the `/metrics` endpoint is better for external monitoring.
:::
```

### Logging

All task executions are logged automatically:

```
INFO - Starting scheduled task BackgroundService.cleanup (every 60000ms)
ERROR - Scheduled task BackgroundService.cleanup failed with error: ...
INFO - Stopped 3 scheduled task(s)
```

Configure logging levels in `application.yml`:

```yaml
logging:
  level: INFO  # Set to DEBUG for detailed scheduler logs
```


## Planned Features

Future enhancements under consideration:

- Task priorities and execution order control
- Conditional execution
- Task groups and dependencies
- Persistent task history


## Troubleshooting

### Tasks Not Running

1. **Check if scheduler is enabled:**
   ```yaml
   # application.yml
   scheduler:
     enabled: true
   ```

2. **Verify the service is registered:**
   ```python
   @Service()  # Don't forget this decorator!
   class MyScheduledService:
       @Scheduled(fixed_rate=5000)
       async def task(self):
           pass
   ```

3. **Check logs for errors:**
   ```
   ERROR - Scheduled task MyService.task failed with error: ...
   ```

### Tasks Running Too Frequently

Ensure intervals are in milliseconds:
```python
@Scheduled(fixed_rate=60000)  # 1 minute (60,000 ms)
# NOT
@Scheduled(fixed_rate=60)  # 60 ms - way too frequent!
```

### Tasks Not Stopping

Tasks are automatically stopped when the application shuts down. If you need manual control, you can disable the scheduler via configuration.


## Comparison with Other Frameworks

### Spring Boot

```java
// Spring Boot - Fixed Rate
@Scheduled(fixedRate = 5000)
public void task() { }

// Spring Boot - Fixed Delay
@Scheduled(fixedDelay = 5000)
public void task() { }

// Spring Boot - Cron
@Scheduled(cron = "0 0 2 * * *")
public void task() { }
```

```python
# Mitsuki - Fixed Rate
@Scheduled(fixed_rate=5000)
async def task(self): ...

# Mitsuki - Fixed Delay
@Scheduled(fixed_delay=5000)
async def task(self): ...

# Mitsuki - Cron
@Scheduled(cron="0 0 2 * * *")
async def task(self): ...
```

### FastAPI (with APScheduler)

```python
# FastAPI requires external library
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', seconds=5)
async def task():
    pass

@scheduler.scheduled_job('cron', hour=2)
async def task():
    pass
```

```python
# Mitsuki - built-in, minimal dependencies (croniter for cron only)
@Scheduled(fixed_rate=5000)
async def task(self): ...

@Scheduled(cron="0 0 2 * * *")
async def task(self): ...
```


## Next Steps

- [Services & DI](./02_decorators.md) - Understanding `@Service` decorator
- [Configuration](./06_configuration.md) - Configure scheduler behavior
- [Logging](./12_logging.md) - Monitor scheduled task execution

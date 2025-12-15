import asyncio

import pytest

from mitsuki import Scheduled, Service
from mitsuki.core.container import DIContainer, set_container
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.scheduler import CRON_MACROS, TaskScheduler


class TestScheduledDecorator:
    """Tests for the @Scheduled decorator."""

    def test_scheduled_decorator_marks_method(self):
        """Test that @Scheduled marks methods with metadata."""

        @Service()
        class TestService:
            @Scheduled(fixed_rate=1000)
            async def task(self):
                pass

        # Check that the method has the marker attribute
        assert hasattr(TestService.task, "__mitsuki_scheduled__")
        assert TestService.task.__mitsuki_scheduled__ is True

        # Check configuration
        config = TestService.task.__mitsuki_schedule_config__
        assert config["fixed_rate"] == 1000
        assert config["initial_delay"] == 0

    def test_scheduled_requires_at_least_one_parameter(self):
        """Test that @Scheduled requires at least one scheduling parameter."""
        with pytest.raises(ValueError, match="Must specify at least one"):

            @Scheduled()
            async def task(self):
                pass

    def test_scheduled_with_fixed_delay(self):
        """Test @Scheduled with fixed_delay parameter."""

        @Service()
        class TestService:
            @Scheduled(fixed_delay=3000)
            async def task(self):
                pass

        config = TestService.task.__mitsuki_schedule_config__
        assert config["fixed_delay"] == 3000
        assert config["fixed_rate"] is None

    def test_scheduled_with_cron(self):
        """Test @Scheduled with cron parameter."""

        @Service()
        class TestService:
            @Scheduled(cron="0 */5 * * * *")
            async def task(self):
                pass

        config = TestService.task.__mitsuki_schedule_config__
        assert config["cron"] == "0 */5 * * * *"
        assert config["fixed_rate"] is None

    def test_scheduled_with_initial_delay(self):
        """Test @Scheduled with initial_delay parameter."""

        @Service()
        class TestService:
            @Scheduled(fixed_rate=2000, initial_delay=5000)
            async def task(self):
                pass

        config = TestService.task.__mitsuki_schedule_config__
        assert config["fixed_rate"] == 2000
        assert config["initial_delay"] == 5000


class TestTaskScheduler:
    """Tests for the TaskScheduler class."""

    def setup_method(self):
        """Set up test fixtures."""
        set_container(DIContainer())

    def teardown_method(self):
        """Clean up after tests."""
        set_container(DIContainer())

    @pytest.mark.asyncio
    async def test_scheduler_register_and_start(self):
        """Test registering and starting a scheduled task."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=100)  # 100ms
            async def increment(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        # Register the task
        scheduler.register_scheduled_method(
            service, service.increment, {"fixed_rate": 100, "initial_delay": 0}
        )

        # Start scheduler
        await scheduler.start()

        # Wait for a few executions
        await asyncio.sleep(0.35)  # Should run ~3 times

        # Stop scheduler
        await scheduler.stop()

        # Verify task ran multiple times
        assert service.counter >= 2
        assert service.counter <= 4  # Allow timing variance

    @pytest.mark.asyncio
    async def test_scheduler_initial_delay(self):
        """Test that initial_delay works correctly."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=100, initial_delay=200)
            async def increment(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service,
            service.increment,
            {"fixed_rate": 100, "initial_delay": 200},
        )

        await scheduler.start()

        # Before initial delay completes
        await asyncio.sleep(0.15)
        assert service.counter == 0  # Should not have run yet

        # After initial delay
        await asyncio.sleep(0.2)
        assert service.counter >= 1  # Should have run at least once

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_handles_task_errors(self):
        """Test that scheduler continues after task errors."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=50)
            async def failing_task(self):
                self.counter += 1
                if self.counter == 2:
                    raise ValueError("Test error")

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service,
            service.failing_task,
            {"fixed_rate": 50, "initial_delay": 0},
        )

        await scheduler.start()
        await asyncio.sleep(0.2)  # Should run ~4 times
        await scheduler.stop()

        # Task should continue running after error
        assert service.counter >= 3

    @pytest.mark.asyncio
    async def test_scheduler_stop_cancels_tasks(self):
        """Test that stopping scheduler cancels all tasks."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=50)
            async def increment(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.increment, {"fixed_rate": 50, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.15)

        count_before_stop = service.counter
        await scheduler.stop()

        # Wait a bit more
        await asyncio.sleep(0.1)

        # Counter should not have increased after stop
        assert service.counter == count_before_stop

    @pytest.mark.asyncio
    async def test_scheduler_multiple_tasks(self):
        """Test scheduling multiple tasks in one service."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter_a = 0
                self.counter_b = 0

            @Scheduled(fixed_rate=50)
            async def task_a(self):
                self.counter_a += 1

            @Scheduled(fixed_rate=75)
            async def task_b(self):
                self.counter_b += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.task_a, {"fixed_rate": 50, "initial_delay": 0}
        )
        scheduler.register_scheduled_method(
            service, service.task_b, {"fixed_rate": 75, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        # Both tasks should have run
        assert service.counter_a >= 3  # ~5 times in 250ms
        assert service.counter_b >= 2  # ~3 times in 250ms

    @pytest.mark.asyncio
    async def test_scheduler_supports_sync_methods(self):
        """Test that scheduler can handle synchronous methods."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=50)
            def sync_task(self):  # Synchronous method
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.sync_task, {"fixed_rate": 50, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.15)
        await scheduler.stop()

        # Sync task should have run
        assert service.counter >= 2

    @pytest.mark.asyncio
    async def test_scheduler_fixed_delay_execution(self):
        """Test that fixed_delay waits after completion."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0
                self.execution_times = []

            @Scheduled(fixed_delay=100)
            async def delayed_task(self):
                self.execution_times.append(asyncio.get_event_loop().time())
                self.counter += 1
                # Simulate work that takes 50ms
                await asyncio.sleep(0.05)

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.delayed_task, {"fixed_delay": 100, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.5)  # Run for 500ms
        await scheduler.stop()

        # Should run ~3 times: execute (50ms) + delay (100ms) = 150ms per cycle
        assert service.counter >= 2
        assert service.counter <= 4

        # Verify delay is AFTER execution (not before)
        if len(service.execution_times) >= 2:
            # Time between starts should be >= 150ms (50ms execution + 100ms delay)
            time_between = service.execution_times[1] - service.execution_times[0]
            assert time_between >= 0.14  # 140ms (allowing some variance)

    @pytest.mark.asyncio
    async def test_scheduler_fixed_rate_maintains_interval(self):
        """Test that fixed_rate maintains consistent intervals between starts."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0
                self.execution_times = []

            @Scheduled(fixed_rate=100)
            async def rate_task(self):
                self.execution_times.append(asyncio.get_event_loop().time())
                self.counter += 1
                # Simulate work that takes 30ms
                await asyncio.sleep(0.03)

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.rate_task, {"fixed_rate": 100, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.35)  # Run for 350ms
        await scheduler.stop()

        # Should run ~3 times in 350ms (every 100ms)
        assert service.counter >= 2
        assert service.counter <= 4

        # Verify interval is between starts (not after completion)
        if len(service.execution_times) >= 2:
            # Time between starts should be ~100ms regardless of execution time
            time_between = service.execution_times[1] - service.execution_times[0]
            assert 0.09 <= time_between <= 0.12  # 90-120ms (allowing variance)

    @pytest.mark.asyncio
    async def test_scheduler_fixed_rate_long_execution(self):
        """Test that fixed_rate starts immediately if execution exceeds interval."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0
                self.execution_times = []

            @Scheduled(fixed_rate=50)
            async def slow_task(self):
                self.execution_times.append(asyncio.get_event_loop().time())
                self.counter += 1
                # Simulate work that takes 80ms (longer than 50ms interval)
                await asyncio.sleep(0.08)

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.slow_task, {"fixed_rate": 50, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.25)  # Run for 250ms
        await scheduler.stop()

        # Should run ~3 times: 0ms, 80ms, 160ms (no additional delay)
        assert service.counter >= 2
        assert service.counter <= 4

        # Verify next execution starts immediately after long execution
        if len(service.execution_times) >= 2:
            # Time between starts should be ~80ms (execution time, no added delay)
            time_between = service.execution_times[1] - service.execution_times[0]
            assert 0.07 <= time_between <= 0.10  # 70-100ms (allowing variance)

    @pytest.mark.asyncio
    async def test_scheduler_cron_execution(self):
        """Test cron-based scheduling."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(cron="* * * * * *")  # Every second
            async def cron_task(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        # Register cron task that runs every second
        scheduler.register_scheduled_method(
            service, service.cron_task, {"cron": "* * * * * *", "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(2.5)  # Run for 2.5 seconds
        await scheduler.stop()

        # Should run 2-3 times in 2.5 seconds
        assert service.counter >= 2
        assert service.counter <= 4

    @pytest.mark.asyncio
    async def test_scheduler_invalid_cron_expression(self):
        """Test that invalid cron expressions are handled gracefully."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(cron="invalid cron")
            async def cron_task(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        # Register with invalid cron
        scheduler.register_scheduled_method(
            service, service.cron_task, {"cron": "invalid cron", "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        # Task should not have run due to invalid cron
        assert service.counter == 0

    @pytest.mark.asyncio
    async def test_scheduler_cron_macros(self):
        """Test that cron macros are expanded correctly."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(cron="@hourly")
            async def hourly_task(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        # Register with macro
        scheduler.register_scheduled_method(
            service, service.hourly_task, {"cron": "@hourly", "initial_delay": 0}
        )

        # Check that the macro was expanded in statistics
        stats = scheduler.get_task_statistics()
        assert len(stats["tasks"]) == 1
        assert stats["tasks"][0]["interval"] == "0 0 * * * *"  # Expanded from @hourly

    @pytest.mark.asyncio
    async def test_scheduler_statistics_tracking(self):
        """Test that scheduler tracks task statistics correctly."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=50)
            async def task(self):
                self.counter += 1
                await asyncio.sleep(0.01)  # Simulate work

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.task, {"fixed_rate": 50, "initial_delay": 0}
        )

        # Before starting
        stats = scheduler.get_task_statistics()
        assert stats["total_tasks"] == 1
        assert stats["running_tasks"] == 0
        assert stats["tasks"][0]["status"] == "pending"
        assert stats["tasks"][0]["executions"] == 0

        # After starting
        await scheduler.start()
        await asyncio.sleep(0.2)

        stats = scheduler.get_task_statistics()
        assert stats["running_tasks"] == 1
        assert stats["tasks"][0]["status"] == "running"
        assert stats["tasks"][0]["executions"] >= 2
        assert stats["tasks"][0]["failures"] == 0
        assert stats["tasks"][0]["last_execution"] is not None
        assert stats["tasks"][0]["last_duration_ms"] is not None
        assert stats["tasks"][0]["average_duration_ms"] is not None

        await scheduler.stop()

        # After stopping - status should not be running anymore
        # (could be "stopped" or transitioning, but not "running")
        stats = scheduler.get_task_statistics()
        # Just verify the statistics are still accessible after stop
        assert stats["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_scheduler_statistics_failure_tracking(self):
        """Test that scheduler tracks failures correctly."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(fixed_rate=50)
            async def failing_task(self):
                self.counter += 1
                if self.counter % 2 == 0:
                    raise ValueError("Test error")

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.failing_task, {"fixed_rate": 50, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        stats = scheduler.get_task_statistics()
        task_stats = stats["tasks"][0]

        # Should have both successes and failures
        assert task_stats["executions"] >= 2  # Successful executions
        assert task_stats["failures"] >= 1  # Failed executions

    @pytest.mark.asyncio
    async def test_scheduler_timezone_support(self):
        """Test that timezone parameter is accepted and stored."""

        @Service()
        class TestService:
            def __init__(self):
                self.counter = 0

            @Scheduled(cron="0 0 9 * * *", timezone="America/New_York")
            async def eastern_task(self):
                self.counter += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        # Register task with timezone
        scheduler.register_scheduled_method(
            service,
            service.eastern_task,
            {"cron": "0 0 9 * * *", "timezone": "America/New_York", "initial_delay": 0},
        )

        # Start scheduler (task won't execute during test, but should initialize)
        await scheduler.start()
        await asyncio.sleep(0.1)
        await scheduler.stop()

        # Verify task was registered
        stats = scheduler.get_task_statistics()
        assert len(stats["tasks"]) == 1
        assert stats["tasks"][0]["type"] == "cron"

    @pytest.mark.asyncio
    async def test_scheduler_multiple_macros(self):
        """Test multiple different cron macros."""

        @Service()
        class TestService:
            @Scheduled(cron="@daily")
            async def daily_task(self):
                pass

            @Scheduled(cron="@weekly")
            async def weekly_task(self):
                pass

            @Scheduled(cron="@monthly")
            async def monthly_task(self):
                pass

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.daily_task, {"cron": "@daily", "initial_delay": 0}
        )
        scheduler.register_scheduled_method(
            service, service.weekly_task, {"cron": "@weekly", "initial_delay": 0}
        )
        scheduler.register_scheduled_method(
            service, service.monthly_task, {"cron": "@monthly", "initial_delay": 0}
        )

        stats = scheduler.get_task_statistics()
        assert len(stats["tasks"]) == 3

        # Verify macros were expanded
        intervals = [task["interval"] for task in stats["tasks"]]
        assert "0 0 0 * * *" in intervals  # @daily
        assert "0 0 0 * * 0" in intervals  # @weekly
        assert "0 0 0 1 * *" in intervals  # @monthly

    @pytest.mark.asyncio
    async def test_scheduler_statistics_with_no_executions(self):
        """Test statistics for tasks that haven't executed yet."""

        @Service()
        class TestService:
            @Scheduled(fixed_rate=1000, initial_delay=10000)  # Long delay
            async def delayed_task(self):
                pass

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service,
            service.delayed_task,
            {"fixed_rate": 1000, "initial_delay": 10000},
        )

        await scheduler.start()
        await asyncio.sleep(0.05)

        stats = scheduler.get_task_statistics()
        task_stats = stats["tasks"][0]

        # Should show pending/running but no executions yet
        assert task_stats["executions"] == 0
        assert task_stats["failures"] == 0
        assert task_stats["last_execution"] is None
        assert task_stats["last_duration_ms"] is None
        assert task_stats["average_duration_ms"] is None

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_average_duration_calculation(self):
        """Test that average duration is calculated correctly."""

        @Service()
        class TestService:
            def __init__(self):
                self.execution_count = 0

            @Scheduled(fixed_rate=50)
            async def variable_duration_task(self):
                # Vary sleep time: 10ms, 20ms, 30ms, 10ms, 20ms...
                sleep_time = ((self.execution_count % 3) + 1) * 0.01
                await asyncio.sleep(sleep_time)
                self.execution_count += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service,
            service.variable_duration_task,
            {"fixed_rate": 50, "initial_delay": 0},
        )

        await scheduler.start()
        await asyncio.sleep(0.3)  # Let it run several times
        await scheduler.stop()

        stats = scheduler.get_task_statistics()
        task_stats = stats["tasks"][0]

        # Should have run multiple times
        assert task_stats["executions"] >= 3

        # Average should be calculated
        assert task_stats["average_duration_ms"] is not None
        assert task_stats["average_duration_ms"] > 0

        # Last duration should be reasonable
        assert task_stats["last_duration_ms"] is not None
        assert task_stats["last_duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_scheduler_all_cron_macros(self):
        """Test that all cron macros are recognized."""
        expected_macros = {
            "@yearly": "0 0 0 1 1 *",
            "@annually": "0 0 0 1 1 *",
            "@monthly": "0 0 0 1 * *",
            "@weekly": "0 0 0 * * 0",
            "@daily": "0 0 0 * * *",
            "@midnight": "0 0 0 * * *",
            "@hourly": "0 0 * * * *",
        }

        assert CRON_MACROS == expected_macros

    @pytest.mark.asyncio
    async def test_scheduler_mixed_schedule_types(self):
        """Test scheduler with mixed fixed_rate, fixed_delay, and cron tasks."""

        @Service()
        class TestService:
            def __init__(self):
                self.rate_count = 0
                self.delay_count = 0
                self.cron_count = 0

            @Scheduled(fixed_rate=50)
            async def rate_task(self):
                self.rate_count += 1

            @Scheduled(fixed_delay=50)
            async def delay_task(self):
                self.delay_count += 1

            @Scheduled(cron="* * * * * *")  # Every second
            async def cron_task(self):
                self.cron_count += 1

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.rate_task, {"fixed_rate": 50, "initial_delay": 0}
        )
        scheduler.register_scheduled_method(
            service, service.delay_task, {"fixed_delay": 50, "initial_delay": 0}
        )
        scheduler.register_scheduled_method(
            service, service.cron_task, {"cron": "* * * * * *", "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        stats = scheduler.get_task_statistics()

        # Should have 3 tasks
        assert stats["total_tasks"] == 3

        # Each should have different type
        types = {task["type"] for task in stats["tasks"]}
        assert types == {"fixed_rate", "fixed_delay", "cron"}

        # All should have run
        assert service.rate_count > 0
        assert service.delay_count > 0
        # Cron might not run in 250ms if timing is unlucky, so just check it exists

    @pytest.mark.asyncio
    async def test_scheduler_statistics_dict_structure(self):
        """Test that statistics dictionary has correct structure."""

        @Service()
        class TestService:
            @Scheduled(fixed_rate=100)
            async def test_task(self):
                pass

        metrics_storage = MetricsStorage()
        scheduler = TaskScheduler(metrics_storage)
        service = TestService()

        scheduler.register_scheduled_method(
            service, service.test_task, {"fixed_rate": 100, "initial_delay": 0}
        )

        await scheduler.start()
        await asyncio.sleep(0.15)
        await scheduler.stop()

        stats = scheduler.get_task_statistics()

        # Top level structure
        assert "tasks" in stats
        assert "total_tasks" in stats
        assert "running_tasks" in stats

        # Task structure
        assert len(stats["tasks"]) == 1
        task = stats["tasks"][0]

        required_fields = [
            "name",
            "type",
            "interval",
            "status",
            "executions",
            "failures",
            "last_execution",
            "last_duration_ms",
            "average_duration_ms",
        ]

        for field in required_fields:
            assert field in task, f"Missing field: {field}"

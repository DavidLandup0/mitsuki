import asyncio
import inspect
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pytz
from croniter import croniter

from mitsuki.core.logging import get_logger

logger = get_logger()

# Cron macros
CRON_MACROS = {
    "@yearly": "0 0 0 1 1 *",
    "@annually": "0 0 0 1 1 *",
    "@monthly": "0 0 0 1 * *",
    "@weekly": "0 0 0 * * 0",
    "@daily": "0 0 0 * * *",
    "@midnight": "0 0 0 * * *",
    "@hourly": "0 0 * * * *",
}


class TaskStatistics:
    """Statistics for a scheduled task."""

    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.executions = 0
        self.failures = 0
        self.last_execution: Optional[datetime] = None
        self.last_duration_ms: Optional[float] = None
        self.total_duration_ms: float = 0.0
        self.status = "pending"

    @property
    def average_duration_ms(self) -> Optional[float]:
        """Calculate average execution duration."""
        if self.executions == 0:
            return None
        return self.total_duration_ms / self.executions

    def to_dict(self) -> Dict:
        """Convert statistics to dictionary."""
        schedule_type = None
        interval = None

        if self.config.get("fixed_rate"):
            schedule_type = "fixed_rate"
            interval = self.config["fixed_rate"]
        elif self.config.get("fixed_delay"):
            schedule_type = "fixed_delay"
            interval = self.config["fixed_delay"]
        elif self.config.get("cron"):
            schedule_type = "cron"
            interval = self.config["cron"]

        return {
            "name": self.name,
            "type": schedule_type,
            "interval": interval,
            "status": self.status,
            "executions": self.executions,
            "failures": self.failures,
            "last_execution": self.last_execution.isoformat()
            if self.last_execution
            else None,
            "last_duration_ms": self.last_duration_ms,
            "average_duration_ms": self.average_duration_ms,
        }


class TaskScheduler:
    """Manages scheduled tasks for the application."""

    def __init__(self):
        self.tasks: List[asyncio.Task] = []
        self.running = False
        self._registered_count = 0
        self._statistics: Dict[str, TaskStatistics] = {}

    def register_scheduled_method(
        self, instance: Any, method: Callable, config: Dict
    ) -> None:
        """
        Register a scheduled method for execution.

        Args:
            instance: The object instance that owns the method
            method: The method to schedule
            config: Schedule configuration from @Scheduled decorator
        """
        # Expand cron macros
        if config.get("cron"):
            cron_expr = config["cron"]
            if cron_expr in CRON_MACROS:
                config = config.copy()
                config["cron"] = CRON_MACROS[cron_expr]

        # Create statistics tracker
        method_name = f"{instance.__class__.__name__}.{method.__name__}"
        self._statistics[method_name] = TaskStatistics(method_name, config)

        if config.get("fixed_rate"):
            self._register_fixed_rate(instance, method, config)
            self._registered_count += 1
        elif config.get("fixed_delay"):
            self._register_fixed_delay(instance, method, config)
            self._registered_count += 1
        elif config.get("cron"):
            self._register_cron(instance, method, config)
            self._registered_count += 1

    def _register_fixed_rate(
        self, instance: Any, method: Callable, config: Dict
    ) -> None:
        """Register a fixed-rate scheduled task."""

        async def task_loop():
            """Run the scheduled method at fixed intervals."""
            interval_ms = config["fixed_rate"]
            interval_sec = interval_ms / 1000.0
            initial_delay_ms = config.get("initial_delay", 0)
            initial_delay_sec = initial_delay_ms / 1000.0

            method_name = f"{instance.__class__.__name__}.{method.__name__}"
            stats = self._statistics[method_name]

            # Initial delay
            if initial_delay_sec > 0:
                logger.debug(
                    f"Scheduled task {method_name} waiting {initial_delay_ms}ms before first execution"
                )
                await asyncio.sleep(initial_delay_sec)

            logger.info(
                f"Starting scheduled task {method_name} (every {interval_ms}ms)"
            )
            stats.status = "running"

            while self.running:
                iteration_start_time = asyncio.get_event_loop().time()

                try:
                    # Call the method (it's already bound to the instance)
                    execution_start_time = asyncio.get_event_loop().time()
                    if inspect.iscoroutinefunction(method):
                        await method()
                    else:
                        # Support sync methods by running in executor
                        await asyncio.get_event_loop().run_in_executor(None, method)

                    # Track successful execution
                    duration_ms = (
                        asyncio.get_event_loop().time() - execution_start_time
                    ) * 1000
                    stats.executions += 1
                    stats.last_execution = datetime.now()
                    stats.last_duration_ms = duration_ms
                    stats.total_duration_ms += duration_ms
                except Exception as e:
                    stats.failures += 1
                    logger.error(
                        f"Scheduled task {method_name} failed with error: {e}",
                        exc_info=True,
                    )

                # Calculate remaining time to maintain fixed rate
                elapsed_time = asyncio.get_event_loop().time() - iteration_start_time
                remaining_time = interval_sec - elapsed_time

                if remaining_time > 0:
                    await asyncio.sleep(remaining_time)
                # else: next execution starts immediately (task took longer than interval)

            stats.status = "stopped"

        # Store the task creator, don't start yet
        self.tasks.append(task_loop)

    def _register_fixed_delay(
        self, instance: Any, method: Callable, config: Dict
    ) -> None:
        """Register a fixed-delay scheduled task."""

        async def task_loop():
            """Run the scheduled method with fixed delay after completion."""
            delay_ms = config["fixed_delay"]
            delay_sec = delay_ms / 1000.0
            initial_delay_ms = config.get("initial_delay", 0)
            initial_delay_sec = initial_delay_ms / 1000.0

            method_name = f"{instance.__class__.__name__}.{method.__name__}"
            stats = self._statistics[method_name]

            # Initial delay
            if initial_delay_sec > 0:
                logger.debug(
                    f"Scheduled task {method_name} waiting {initial_delay_ms}ms before first execution"
                )
                await asyncio.sleep(initial_delay_sec)

            logger.info(
                f"Starting scheduled task {method_name} ({delay_ms}ms after completion)"
            )
            stats.status = "running"

            while self.running:
                start_time = asyncio.get_event_loop().time()
                try:
                    # Call the method (it's already bound to the instance)
                    if inspect.iscoroutinefunction(method):
                        await method()
                    else:
                        # Support sync methods by running in executor
                        await asyncio.get_event_loop().run_in_executor(None, method)

                    # Track successful execution
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    stats.executions += 1
                    stats.last_execution = datetime.now()
                    stats.last_duration_ms = duration_ms
                    stats.total_duration_ms += duration_ms
                except Exception as e:
                    stats.failures += 1
                    logger.error(
                        f"Scheduled task {method_name} failed with error: {e}",
                        exc_info=True,
                    )

                # Wait after execution completes (fixed delay)
                await asyncio.sleep(delay_sec)

            stats.status = "stopped"

        # Store the task creator, don't start yet
        self.tasks.append(task_loop)

    def _register_cron(self, instance: Any, method: Callable, config: Dict) -> None:
        """Register a cron-based scheduled task."""

        async def task_loop():
            """Run the scheduled method based on cron expression."""
            cron_expr = config["cron"]
            timezone_str = config.get("timezone")

            method_name = f"{instance.__class__.__name__}.{method.__name__}"
            stats = self._statistics[method_name]

            try:
                # Get timezone-aware datetime if timezone is specified
                if timezone_str:
                    tz = pytz.timezone(timezone_str)
                    base_time = datetime.now(tz)
                else:
                    base_time = datetime.now()

                # Create croniter instance
                cron = croniter(cron_expr, base_time)
            except Exception as e:
                logger.error(f"Invalid cron expression '{cron_expr}': {e}")
                stats.status = "error"
                return

            tz_info = f" ({timezone_str})" if timezone_str else ""
            logger.info(
                f"Starting scheduled task {method_name} (cron: {cron_expr}{tz_info})"
            )
            stats.status = "running"

            while self.running:
                try:
                    # Get next execution time
                    next_run = cron.get_next(datetime)

                    # Get current time in same timezone
                    if timezone_str:
                        tz = pytz.timezone(timezone_str)
                        now = datetime.now(tz)
                    else:
                        now = datetime.now()

                    # Calculate sleep time
                    sleep_seconds = (next_run - now).total_seconds()

                    if sleep_seconds > 0:
                        # Sleep until next execution
                        await asyncio.sleep(sleep_seconds)

                        # Check if still running after sleep
                        if not self.running:
                            break

                        # Execute the task
                        start_time = asyncio.get_event_loop().time()
                        if inspect.iscoroutinefunction(method):
                            await method()
                        else:
                            await asyncio.get_event_loop().run_in_executor(None, method)

                        # Track successful execution
                        duration_ms = (
                            asyncio.get_event_loop().time() - start_time
                        ) * 1000
                        stats.executions += 1
                        stats.last_execution = datetime.now()
                        stats.last_duration_ms = duration_ms
                        stats.total_duration_ms += duration_ms

                except Exception as e:
                    stats.failures += 1
                    logger.error(
                        f"Scheduled task {method_name} failed with error: {e}",
                        exc_info=True,
                    )

                    # On error, wait a bit before next iteration
                    await asyncio.sleep(1)

            stats.status = "stopped"

        # Store the task creator, don't start yet
        self.tasks.append(task_loop)

    async def start(self) -> None:
        """Start all scheduled tasks."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True

        # Create and start all tasks
        running_tasks = []
        for task_creator in self.tasks:
            task = asyncio.create_task(task_creator())
            running_tasks.append(task)

        # Replace task creators with actual running tasks
        self.tasks = running_tasks

        if self._registered_count > 0:
            logger.info(
                f"Scheduler started with {self._registered_count} scheduled task(s)"
            )

    async def stop(self) -> None:
        """Stop all scheduled tasks."""
        if not self.running:
            return

        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            logger.info(f"Stopped {len(self.tasks)} scheduled task(s)")

        self.tasks.clear()

    def get_task_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all scheduled tasks.

        Returns:
            Dictionary containing task statistics
        """
        return {
            "tasks": [stats.to_dict() for stats in self._statistics.values()],
            "total_tasks": len(self._statistics),
            "running_tasks": sum(
                1 for s in self._statistics.values() if s.status == "running"
            ),
        }


# Global scheduler instance
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global task scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def reset_scheduler() -> None:
    """Reset the global scheduler (for testing)."""
    global _scheduler
    _scheduler = None

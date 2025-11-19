"""
Example demonstrating @Scheduled decorator for background tasks.

Run this example:
    python3 examples/scheduled_tasks_example.py

The scheduled tasks will run in the background while the web server is running.
Visit http://localhost:8000/api/status to see task execution counts.
"""

from datetime import datetime

from mitsuki import Application, GetMapping, RestController, Scheduled, Service


@Service()
class BackgroundTaskService:
    """Service with scheduled background tasks."""

    def __init__(self):
        self.quick_task_count = 0
        self.slow_task_count = 0
        self.delayed_task_count = 0

    @Scheduled(fixed_rate=2000)  # Every 2 seconds
    async def quick_task(self):
        """Quick task that runs every 2 seconds."""
        self.quick_task_count += 1
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Quick task executed (count: {self.quick_task_count})"
        )

    @Scheduled(fixed_rate=5000)  # Every 5 seconds
    async def slow_task(self):
        """Slower task that runs every 5 seconds."""
        self.slow_task_count += 1
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Slow task executed (count: {self.slow_task_count})"
        )

    @Scheduled(
        fixed_rate=3000, initial_delay=10000
    )  # Every 3 seconds, after 10 second delay
    async def delayed_task(self):
        """Task that waits 10 seconds before first execution."""
        self.delayed_task_count += 1
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Delayed task executed (count: {self.delayed_task_count})"
        )


@RestController("/api")
class StatusController:
    """Controller to check task execution status."""

    def __init__(self, task_service: BackgroundTaskService):
        self.task_service = task_service

    @GetMapping("/status")
    async def get_status(self) -> dict:
        """Get current execution counts for all scheduled tasks."""
        return {
            "message": "Scheduled tasks are running in the background",
            "tasks": {
                "quick_task": {
                    "interval": "2 seconds",
                    "executions": self.task_service.quick_task_count,
                },
                "slow_task": {
                    "interval": "5 seconds",
                    "executions": self.task_service.slow_task_count,
                },
                "delayed_task": {
                    "interval": "3 seconds",
                    "initial_delay": "10 seconds",
                    "executions": self.task_service.delayed_task_count,
                },
            },
            "timestamp": datetime.now().isoformat(),
        }


@Application
class ScheduledTasksApp:
    """Example application with scheduled background tasks."""

    pass


if __name__ == "__main__":
    ScheduledTasksApp.run()

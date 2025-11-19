from typing import Dict

from mitsuki.core.scheduler import get_scheduler
from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping


def create_metrics_endpoint(config):
    """
    Create metrics endpoint based on configuration.

    Returns controller class if metrics are enabled, None otherwise.
    """
    enabled = config.get("scheduler.metrics.enabled")
    path = config.get("scheduler.metrics.path")

    if not enabled:
        return None

    @RestController()
    class SchedulerMetricsController:
        """REST controller for scheduler metrics."""

        def __init__(self):
            pass

        @GetMapping(path)
        async def get_metrics(self) -> Dict:
            """Get scheduler metrics and task statistics."""
            scheduler = get_scheduler()
            return scheduler.get_task_statistics()

    return SchedulerMetricsController

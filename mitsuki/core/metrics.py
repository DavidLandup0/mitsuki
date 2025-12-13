from typing import Dict, Optional

from starlette.responses import PlainTextResponse

from mitsuki.core.metrics_core import MetricsRegistry as CoreMetricsRegistry
from mitsuki.core.metrics_formatters import format_mitsuki, format_prometheus
from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping


def create_metrics_endpoint(config):
    """
    Create unified metrics endpoint based on configuration.

    Exposes:
    - /metrics - Mitsuki format (nested JSON)
    - /metrics/prometheus - Prometheus format (text)

    Returns controller class if metrics are enabled, None otherwise.

    Note: Future versions will support metrics.port to expose on a separate port.
    """
    metrics_enabled = config.get_bool("metrics.enabled")

    if not metrics_enabled:
        return None

    metrics_path = config.get("metrics.path", "/metrics")
    allowed_ips = config.get("metrics.allowed_ips", [])

    @RestController()
    class MetricsController:
        """REST controller for application metrics."""

        def __init__(self):
            self._core_registry = CoreMetricsRegistry.get_instance()

        def _check_ip_allowed(self, request) -> Optional[Dict]:
            """Check if request IP is allowed. Returns error dict if not allowed, None if allowed."""
            if not allowed_ips:
                return None

            client_ip = self._get_client_ip(request)
            if client_ip not in allowed_ips:
                return {
                    "error": "Access denied",
                    "message": "Your IP address is not authorized to access metrics",
                }
            return None

        def _get_client_ip(self, request) -> str:
            """Extract client IP from request."""
            if hasattr(request, "client") and request.client:
                return request.client.host
            return "unknown"

        @GetMapping(metrics_path)
        async def get_metrics(self, request) -> Dict:
            """
            Get all application metrics in Mitsuki format.

            Returns nested JSON with computed aggregations.
            """
            ip_error = self._check_ip_allowed(request)
            if ip_error:
                return ip_error

            return format_mitsuki(self._core_registry)

        @GetMapping(f"{metrics_path}/prometheus")
        async def get_prometheus_metrics(self, request):
            """
            Get all application metrics in Prometheus format.

            Returns text format compatible with Prometheus/Grafana scraping.
            """
            ip_error = self._check_ip_allowed(request)
            if ip_error:
                return ip_error

            content = format_prometheus(self._core_registry)
            return PlainTextResponse(content, media_type="text/plain; version=0.0.4")

    return MetricsController

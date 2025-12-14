import ipaddress

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_mitsuki, format_prometheus
from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping
from mitsuki.web.response import ResponseEntity


def create_metrics_endpoint(config):
    """
    Create metrics endpoint based on configuration.

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
        def __init__(self, metrics_storage: MetricsStorage):
            self._core_registry = metrics_storage

        def _check_ip_allowed(self, request: Request) -> bool:
            """Check if request IP is allowed."""
            if not allowed_ips:
                return True

            client_ip = request.client.host
            client_addr = ipaddress.ip_address(client_ip)

            for allowed in allowed_ips:
                if "/" in allowed:
                    network = ipaddress.ip_network(allowed, strict=False)
                    if client_addr in network:
                        return True
                else:
                    if client_ip == allowed:
                        return True

            return False

        @GetMapping(metrics_path)
        async def get_metrics(self, request: Request):
            """Get all application metrics in Mitsuki format."""
            if not self._check_ip_allowed(request):
                return ResponseEntity.not_found({"error": "Not found"})

            return format_mitsuki(self._core_registry)

        @GetMapping(f"{metrics_path}/prometheus")
        async def get_prometheus_metrics(self, request: Request):
            """Get all application metrics in Prometheus format."""
            if not self._check_ip_allowed(request):
                return ResponseEntity.not_found({"error": "Not found"})

            content = format_prometheus(self._core_registry)
            return PlainTextResponse(content, media_type="text/plain; version=0.0.4")

    return MetricsController

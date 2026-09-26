import ipaddress
from typing import List, Optional, Union

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mitsuki.core.instrumentation import Instrumented
from mitsuki.core.logging import get_logger
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_json, format_prometheus
from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping
from mitsuki.web.response import ResponseEntity

logger = get_logger()

IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def parse_allowed_ips(entries: List[str]) -> List[IPNetwork]:
    """
    Parse metrics.allowed_ips into networks. A bare address becomes a
    single-host network.

    Raises ValueError naming the offending entry, so a misconfigured allowlist
    fails at startup rather than on every request.
    """
    networks = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as e:
            raise ValueError(f"Invalid entry in metrics.allowed_ips: {e}") from e
    return networks


def client_address(request: Request) -> Optional[IPAddress]:
    """
    Return the client's IP address, or None when the server did not report one
    or reported something that is not an IP (e.g. a unix socket path).

    IPv4-mapped IPv6 addresses (::ffff:a.b.c.d), as seen on dual-stack
    listeners, are unwrapped to their IPv4 form.
    """
    if request.client is None:
        return None

    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return None

    if address.version == 6 and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


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
    allowed_networks = parse_allowed_ips(config.get("metrics.allowed_ips", []))

    # Scrapes are monitoring overhead, so the metrics endpoints never record
    # component metrics, even under application-wide instrumentation.
    @Instrumented(enabled=False)
    @RestController()
    class MetricsController:
        def __init__(self, metrics_storage: MetricsStorage):
            self._core_registry = metrics_storage

        def _check_ip_allowed(self, request: Request) -> bool:
            """
            Check the request's direct peer address against the allowlist.

            An empty allowlist allows everyone. Otherwise a client whose
            address is unknown or not an IP is denied.

            NOTE: This sees the direct peer, so behind a reverse proxy or load
                balancer every request carries the proxy's address.
            TODO: Make it harder to accidentally expose the endpoint by
                allowlisting a whole proxy CIDR. For now the documentation
                warns users to choose allowlisted addresses deliberately.
            """
            if not allowed_networks:
                return True

            address = client_address(request)
            if address is None:
                return False

            return any(address in network for network in allowed_networks)

        def _deny(self, request: Request) -> ResponseEntity:
            """Log the denied client and answer as if the endpoint did not exist."""
            client = request.client.host if request.client else "<unknown>"
            logger.warning(f"Metrics access denied for IP: {client}")
            return ResponseEntity.not_found({"error": "Not found"})

        @GetMapping(metrics_path)
        async def get_metrics(self, request: Request):
            """Get all application metrics in Mitsuki format."""
            if not self._check_ip_allowed(request):
                return self._deny(request)

            return format_json(self._core_registry)

        @GetMapping(f"{metrics_path}/prometheus")
        async def get_prometheus_metrics(self, request: Request):
            """Get all application metrics in Prometheus format."""
            if not self._check_ip_allowed(request):
                return self._deny(request)

            content = format_prometheus(self._core_registry)
            return PlainTextResponse(content, media_type="text/plain; version=0.0.4")

    return MetricsController

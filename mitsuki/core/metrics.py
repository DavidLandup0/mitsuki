import ipaddress
from typing import Iterable, List, Optional, Union

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mitsuki.core.instrumentation import Instrumented
from mitsuki.core.logging import get_logger
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.metrics_formatters import format_json, format_prometheus
from mitsuki.web.controllers import RestController
from mitsuki.web.mappings import GetMapping

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


def is_allowed(request: Request, allowed_networks: List[IPNetwork]) -> bool:
    """
    Check the client address the server reports against the allowlist.

    An empty allowlist allows everyone. Otherwise a client whose address is
    unknown or not an IP is denied.

    NOTE: Behind a reverse proxy, Granian reports the proxy as the client, so
        external requests look internal: allowlisting the proxy's address
        (e.g. 127.0.0.1) exposes the endpoints to everyone it serves. Uvicorn
        fills the client from X-Forwarded-For instead.
    TODO: Make it harder to accidentally expose the endpoint by allowlisting a
        whole proxy CIDR. For now the documentation warns users to choose
        allowlisted addresses deliberately.
    """
    if not allowed_networks:
        return True

    address = client_address(request)
    if address is None:
        return False

    return any(address in network for network in allowed_networks)


class MetricsAccessMiddleware:
    """
    Restricts the metrics endpoints to metrics.allowed_ips.
    """

    def __init__(self, app, paths: Iterable[str], allowed_networks: List[IPNetwork]):
        self.app = app
        self.paths = {path.rstrip("/") for path in paths}
        self.allowed_networks = allowed_networks

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") not in self.paths:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if is_allowed(request, self.allowed_networks):
            await self.app(scope, receive, send)
            return

        client = request.client.host if request.client else "<unknown>"
        logger.warning(f"Metrics access denied for IP: {client}")

        await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)


def create_metrics_endpoint(config):
    """
    Create metrics endpoint based on configuration.

    Exposes:
    - /metrics - Mitsuki format (nested JSON)
    - /metrics/prometheus - Prometheus format (text)

    Returns controller class if metrics are enabled, None otherwise.
    """
    metrics_enabled = config.get_bool("metrics.enabled")

    if not metrics_enabled:
        return None

    metrics_path = config.get("metrics.path", "/metrics")

    @Instrumented(enabled=False)
    @RestController()
    class MetricsController:
        def __init__(self, metrics_storage: MetricsStorage):
            self._core_registry = metrics_storage

        @GetMapping(metrics_path)
        async def get_metrics(self):
            return format_json(self._core_registry)

        @GetMapping(f"{metrics_path}/prometheus")
        async def get_prometheus_metrics(self):
            content = format_prometheus(self._core_registry)
            return PlainTextResponse(content, media_type="text/plain; version=0.0.4")

    return MetricsController

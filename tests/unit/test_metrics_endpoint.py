from unittest.mock import Mock

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mitsuki.core.metrics import create_metrics_endpoint, is_allowed, parse_allowed_ips
from mitsuki.core.metrics_core import MetricsStorage


def _config(path="/metrics", enabled=True):
    config = Mock()
    config.get_bool.return_value = enabled
    config.get.side_effect = lambda key, default=None: {
        "metrics.path": path,
    }.get(key, default)
    return config


def _controller():
    storage = MetricsStorage()
    storage.enable()
    return create_metrics_endpoint(_config())(storage), storage


def _request(host):
    request = Mock(spec=Request)
    if host is None:
        request.client = None
    else:
        request.client.host = host
    return request


class TestMetricsEndpoint:
    """The metrics controller is created only when metrics are enabled."""

    def test_create_metrics_endpoint_disabled(self):
        assert create_metrics_endpoint(_config(enabled=False)) is None

    def test_create_metrics_endpoint_enabled(self):
        controller_class = create_metrics_endpoint(_config())

        assert controller_class is not None
        assert hasattr(controller_class, "get_metrics")
        assert hasattr(controller_class, "get_prometheus_metrics")

    def test_metrics_endpoint_custom_path(self):
        controller_class = create_metrics_endpoint(_config(path="/custom/metrics"))

        routes = {
            controller_class.get_metrics.__mitsuki_route__.path,
            controller_class.get_prometheus_metrics.__mitsuki_route__.path,
        }
        assert routes == {"/custom/metrics", "/custom/metrics/prometheus"}

    @pytest.mark.asyncio
    async def test_metrics_returns_enabled_data(self):
        controller, storage = _controller()
        storage.counter("test_counter").inc()

        result = await controller.get_metrics()

        assert result["enabled"] is True
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_prometheus_metrics_format(self):
        controller, storage = _controller()
        storage.counter("test_requests_total", "Test requests").inc()

        result = await controller.get_prometheus_metrics()

        assert isinstance(result, PlainTextResponse)
        assert result.media_type == "text/plain; version=0.0.4"
        assert b"test_requests_total 1.0" in result.body


class TestAllowlistParsing:
    """Allowlist entries are validated when they are parsed, at startup."""

    @pytest.mark.parametrize(
        "entry", ["not-an-ip", "10.0.0.0/33", "256.1.1.1", "localhost"]
    )
    def test_invalid_entry_fails(self, entry):
        with pytest.raises(ValueError, match="metrics.allowed_ips"):
            parse_allowed_ips(["127.0.0.1", entry])

    def test_bare_address_is_a_single_host(self):
        (network,) = parse_allowed_ips(["192.168.1.100"])

        assert network.num_addresses == 1


class TestAllowlistMatching:
    """Client addresses are compared as addresses, not strings."""

    @pytest.mark.parametrize(
        "allowed, host",
        [
            ("127.0.0.1", "127.0.0.1"),
            ("192.168.1.100", "192.168.1.100"),
            ("172.16.0.0/12", "172.20.0.5"),
            ("127.0.0.1", "::ffff:127.0.0.1"),
            ("10.0.0.0/8", "::ffff:10.1.2.3"),
            ("::1", "0:0:0:0:0:0:0:1"),
            ("0:0:0:0:0:0:0:1", "::1"),
        ],
    )
    def test_matching_address_is_allowed(self, allowed, host):
        assert is_allowed(_request(host), parse_allowed_ips([allowed]))

    @pytest.mark.parametrize(
        "allowed, host",
        [
            ("127.0.0.1", "192.168.1.100"),
            ("172.16.0.0/12", "192.168.1.1"),
            ("127.0.0.1", "::ffff:192.168.1.1"),
        ],
    )
    def test_other_address_is_denied(self, allowed, host):
        assert not is_allowed(_request(host), parse_allowed_ips([allowed]))

    @pytest.mark.parametrize("host", [None, "testclient", "", "unix:/tmp/app.sock"])
    def test_unknown_or_non_ip_client_is_denied(self, host):
        assert not is_allowed(_request(host), parse_allowed_ips(["127.0.0.1"]))

    @pytest.mark.parametrize("host", [None, "192.168.1.100", "testclient"])
    def test_empty_allowlist_allows_everyone(self, host):
        assert is_allowed(_request(host), [])

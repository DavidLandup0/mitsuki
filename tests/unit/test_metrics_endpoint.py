import pytest
from unittest.mock import Mock
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mitsuki.core.metrics import create_metrics_endpoint
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.web.response import ResponseEntity


class TestMetricsEndpoint:
    """Test metrics endpoint creation and access control."""

    def test_create_metrics_endpoint_disabled(self):
        """Test that no controller is created when metrics are disabled."""
        config = Mock()
        config.get_bool.return_value = False

        controller_class = create_metrics_endpoint(config)

        assert controller_class is None

    def test_create_metrics_endpoint_enabled(self):
        """Test that controller is created when metrics are enabled."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)

        assert controller_class is not None
        assert hasattr(controller_class, "get_metrics")
        assert hasattr(controller_class, "get_prometheus_metrics")

    def test_metrics_endpoint_custom_path(self):
        """Test creating metrics endpoint with custom path."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/custom/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)

        assert controller_class is not None

    @pytest.mark.asyncio
    async def test_get_metrics_allowed_no_restrictions(self):
        """Test accessing metrics with no IP restrictions."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"

        result = await controller.get_metrics(request)

        assert isinstance(result, dict)
        assert "enabled" in result

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics_allowed(self):
        """Test accessing Prometheus metrics with no IP restrictions."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"

        result = await controller.get_prometheus_metrics(request)

        assert isinstance(result, PlainTextResponse)

    @pytest.mark.asyncio
    async def test_get_metrics_denied_wrong_ip(self):
        """Test that metrics access is denied for non-whitelisted IP."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["127.0.0.1"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"

        result = await controller.get_metrics(request)

        assert isinstance(result, ResponseEntity)
        assert result.status == 404

    @pytest.mark.asyncio
    async def test_get_prometheus_metrics_denied_wrong_ip(self):
        """Test that Prometheus metrics access is denied for non-whitelisted IP."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["127.0.0.1"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"

        result = await controller.get_prometheus_metrics(request)

        assert isinstance(result, ResponseEntity)
        assert result.status == 404

    @pytest.mark.asyncio
    async def test_ip_whitelist_exact_match(self):
        """Test IP whitelist with exact IP match."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["127.0.0.1", "192.168.1.100"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"

        result = await controller.get_metrics(request)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ip_whitelist_cidr_match(self):
        """Test IP whitelist with CIDR range."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["172.16.0.0/12"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        # Test IP within CIDR range
        request = Mock(spec=Request)
        request.client.host = "172.20.0.5"

        result = await controller.get_metrics(request)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ip_whitelist_cidr_no_match(self):
        """Test IP whitelist CIDR range blocks IPs outside range."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["172.16.0.0/12"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        # Test IP outside CIDR range
        request = Mock(spec=Request)
        request.client.host = "192.168.1.1"

        result = await controller.get_metrics(request)

        assert isinstance(result, ResponseEntity)
        assert result.status == 404

    @pytest.mark.asyncio
    async def test_localhost_allowed(self):
        """Test that localhost is allowed when in whitelist."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": ["127.0.0.1"]
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "127.0.0.1"

        result = await controller.get_metrics(request)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_metrics_returns_enabled_data(self):
        """Test that enabled metrics return proper data structure."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        # Add some metrics
        counter = metrics_storage.counter("test_counter")
        counter.inc()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "127.0.0.1"

        result = await controller.get_metrics(request)

        assert result["enabled"] is True
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_prometheus_metrics_format(self):
        """Test that Prometheus endpoint returns text format."""
        config = Mock()
        config.get_bool.return_value = True
        config.get.side_effect = lambda key, default=None: {
            "metrics.path": "/metrics",
            "metrics.allowed_ips": []
        }.get(key, default)

        controller_class = create_metrics_endpoint(config)
        metrics_storage = MetricsStorage()
        metrics_storage.enable()

        # Add a counter
        counter = metrics_storage.counter("test_requests_total", "Test requests")
        counter.inc()

        controller = controller_class(metrics_storage)

        request = Mock(spec=Request)
        request.client.host = "127.0.0.1"

        result = await controller.get_prometheus_metrics(request)

        assert isinstance(result, PlainTextResponse)
        assert result.media_type == "text/plain; version=0.0.4"

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

import mitsuki.core.decorators as decorators
from mitsuki.config.properties import get_config
from mitsuki.core.container import get_container
from mitsuki.core.metrics import create_metrics_endpoint
from mitsuki.core.metrics_core import MetricsStorage
from mitsuki.core.server import MitsukiASGIApp

METRICS_PATHS = ["/metrics", "/metrics/", "/metrics/prometheus", "/metrics/prometheus/"]
METHODS = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]

ALLOWED_CLIENT = ("10.8.1.1", 50000)
DENIED_CLIENT = ("192.0.2.10", 50000)


class _OverlayConfig:
    """The loaded configuration, with selected keys overridden."""

    def __init__(self, overrides):
        self._config = get_config()
        self._overrides = overrides

    def get(self, key, default=None):
        if key in self._overrides:
            return self._overrides[key]
        return self._config.get(key, default)

    def get_bool(self, key, default=False):
        if key in self._overrides:
            return bool(self._overrides[key])
        return self._config.get_bool(key, default)


class _Context:
    def __init__(self, controllers):
        self.controllers = controllers


@pytest.fixture(autouse=True)
def _isolate(isolated_container):
    saved = list(decorators._instrumentable_components)
    try:
        yield
    finally:
        decorators._instrumentable_components[:] = saved


def build_app(allowed_ips):
    """A Mitsuki application serving only the metrics endpoints."""
    config = _OverlayConfig(
        {
            "metrics.enabled": True,
            "metrics.path": "/metrics",
            "metrics.allowed_ips": allowed_ips,
            "instrumentation.enabled": False,
        }
    )
    get_container().register(MetricsStorage, name="MetricsStorage")
    get_container().get(MetricsStorage).enable()

    controller = create_metrics_endpoint(config)
    with patch("mitsuki.core.server.get_config", return_value=config):
        return MitsukiASGIApp(_Context([(controller, "")]))


def signature(response):
    """Everything a client can observe about a response, apart from its date."""
    headers = sorted((k, v) for k, v in response.headers.items() if k != "date")
    return response.status_code, headers, response.content


class TestDeniedClientsCannotDetectEndpoints:
    """A denied client sees exactly what an unknown path returns."""

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize("path", METRICS_PATHS)
    def test_response_matches_unknown_path(self, path, method):
        client = TestClient(build_app(["10.8.0.0/16"]), client=DENIED_CLIENT)

        denied = client.request(method, path)
        unknown = client.request(method, "/does-not-exist")

        assert signature(denied) == signature(unknown)

    def test_non_ip_client_is_denied_like_unknown_path(self):
        client = TestClient(build_app(["10.8.0.0/16"]))

        assert signature(client.get("/metrics")) == signature(
            client.get("/does-not-exist")
        )

    def test_denial_is_logged(self, caplog):
        client = TestClient(build_app(["10.8.0.0/16"]), client=DENIED_CLIENT)

        with caplog.at_level("WARNING"):
            client.get("/metrics")

        assert "Metrics access denied for IP: 192.0.2.10" in caplog.text


class TestAllowedClients:
    """Allowed clients, and every client without an allowlist, reach the endpoints."""

    @pytest.mark.parametrize(
        "allowed_ips, client_address",
        [(["10.8.0.0/16"], ALLOWED_CLIENT), ([], DENIED_CLIENT)],
    )
    def test_json_endpoint(self, allowed_ips, client_address):
        client = TestClient(build_app(allowed_ips), client=client_address)

        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    @pytest.mark.parametrize(
        "allowed_ips, client_address",
        [(["10.8.0.0/16"], ALLOWED_CLIENT), ([], DENIED_CLIENT)],
    )
    def test_prometheus_endpoint(self, allowed_ips, client_address):
        client = TestClient(build_app(allowed_ips), client=client_address)

        response = client.get("/metrics/prometheus")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_unsupported_method_keeps_its_normal_response(self):
        client = TestClient(build_app(["10.8.0.0/16"]), client=ALLOWED_CLIENT)

        assert client.post("/metrics").status_code == 405

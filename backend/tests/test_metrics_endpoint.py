import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    import api
    importlib.reload(api)  # pick up env for module-level config if needed
    return TestClient(api.app)


def test_metrics_endpoint_public_and_prometheus_format(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Either real exposition or the graceful no-dep fallback.
    assert "aethria_" in body or "metrics unavailable" in body


def test_metrics_reports_live_gauges(client):
    import metrics

    if not metrics.ENABLED:
        pytest.skip("prometheus_client not installed")
    resp = client.get("/metrics")
    assert "aethria_sse_subscribers" in resp.text
    assert "aethria_agent_queue_depth" in resp.text


def test_metrics_token_required_when_set(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    import api
    importlib.reload(api)
    c = TestClient(api.app)
    assert c.get("/metrics").status_code == 401
    assert c.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = c.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_metrics_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "0")
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    import api
    importlib.reload(api)
    c = TestClient(api.app)
    assert c.get("/metrics").status_code == 404

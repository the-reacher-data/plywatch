from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

import plywatch.main as main_module


def test_metrics_endpoint_uses_canonical_path_only(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setattr(main_module.prometheus_client, "REGISTRY", CollectorRegistry(auto_describe=True))
    app = main_module.create_app(start_consumer=False)
    client = TestClient(app)

    response_without_slash = client.get("/metrics")
    response_with_slash = client.get("/metrics/")

    assert response_without_slash.status_code == 200
    assert response_with_slash.status_code == 404
    assert response_without_slash.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response_without_slash.text

from __future__ import annotations

from fastapi.testclient import TestClient

from plywatch.main import create_app
from plywatch.shared.raw_events import build_raw_event


def test_worker_endpoints_expose_consolidated_views(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    worker_projector = app.state.worker_projector
    raw_store = app.state.raw_event_store
    event_counter_store = app.state.event_counter_store

    for payload in (
        {
            "type": "worker-online",
            "hostname": "celery@worker-1",
            "pid": 1,
            "freq": 2.0,
            "active": 0,
            "processed": 3,
            "loadavg": [0.1, 0.2, 0.3],
            "sw_ident": "py-celery",
            "sw_ver": "5.6.2",
            "sw_sys": "Linux",
        },
        {
            "type": "worker-heartbeat",
            "hostname": "celery@worker-1",
            "pid": 1,
            "freq": 5,
            "clock": 10,
            "active": 1,
            "processed": 4,
            "loadavg": [0.3, 0.4, 0.5],
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        event_counter_store.observe(event)
        worker_projector.apply(event)

    client = TestClient(app)

    overview = client.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["workerCount"] == 1
    assert overview.json()["totalEventCount"] == 1
    assert overview.json()["heartbeatEventCount"] == 1
    assert overview.json()["bufferedEventCount"] == 2

    workers = client.get("/api/workers/?limit=5")
    assert workers.status_code == 200
    body = workers.json()
    assert body["count"] == 1
    worker = body["items"][0]
    assert worker["hostname"] == "celery@worker-1"
    assert worker["state"] == "online"
    assert worker["processed"] == 4
    assert worker["loadavg"] == [0.3, 0.4, 0.5]

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from plywatch.main import create_app
from plywatch.shared.raw_events import RawCeleryEvent, build_raw_event


def test_queue_endpoints_expose_consolidated_views(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store

    for payload in (
        {
            "type": "task-sent",
            "uuid": "task-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
        },
        {
            "type": "task-received",
            "uuid": "task-1",
        },
        {
            "type": "task-succeeded",
            "uuid": "task-1",
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        queue_projector.apply(event)

    client = TestClient(app)

    overview = client.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["queueCount"] == 1

    queues = client.get("/api/queues/?limit=5")
    assert queues.status_code == 200
    body = queues.json()
    assert body["count"] == 1
    queue = body["items"][0]
    assert queue["name"] == "default"
    assert queue["routingKeys"] == ["default"]
    assert queue["succeededCount"] == 1


def test_queue_endpoints_expose_incremental_timing_metrics(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    base = datetime.now(UTC).replace(microsecond=0)

    events = (
        RawCeleryEvent(
            captured_at=base.isoformat(),
            event_type="task-sent",
            uuid="task-1",
            hostname="gen10@producer",
            payload={"queue": "default", "routing_key": "default"},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(seconds=1)).isoformat(),
            event_type="task-received",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(seconds=3)).isoformat(),
            event_type="task-started",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(seconds=8)).isoformat(),
            event_type="task-succeeded",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
    )

    for event in events:
        raw_store.append(event)
        queue_projector.apply(event)

    client = TestClient(app)
    queues = client.get("/api/queues/?limit=5")
    assert queues.status_code == 200
    queue = queues.json()["items"][0]
    assert queue["avgQueueWaitMs"] == 1000
    assert queue["queueWaitSampleCount"] == 1
    assert queue["avgStartDelayMs"] == 2000
    assert queue["startDelaySampleCount"] == 1
    assert queue["avgRunDurationMs"] == 5000
    assert queue["runDurationSampleCount"] == 1
    assert queue["avgEndToEndMs"] == 8000
    assert queue["endToEndSampleCount"] == 1


def test_queue_endpoints_keep_default_and_slow_snapshots_separate(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    base = datetime.now(UTC).replace(microsecond=0)

    events = (
        RawCeleryEvent(
            captured_at=base.isoformat(),
            event_type="task-sent",
            uuid="task-default-1",
            hostname="gen10@producer",
            payload={"queue": "default", "routing_key": "default"},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(seconds=1)).isoformat(),
            event_type="task-succeeded",
            uuid="task-default-1",
            hostname="celery@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(minutes=1)).isoformat(),
            event_type="task-sent",
            uuid="task-slow-1",
            hostname="gen10@producer",
            payload={"queue": "slow", "routing_key": "slow"},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(minutes=1, seconds=30)).isoformat(),
            event_type="task-started",
            uuid="task-slow-1",
            hostname="slow@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(minutes=1, seconds=50)).isoformat(),
            event_type="task-succeeded",
            uuid="task-slow-1",
            hostname="slow@worker",
            payload={},
        ),
    )

    for event in events:
        raw_store.append(event)
        queue_projector.apply(event)

    client = TestClient(app)
    response = client.get("/api/queues/?limit=10")

    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert set(items) == {"default", "slow"}
    assert items["default"]["routingKeys"] == ["default"]
    assert items["slow"]["routingKeys"] == ["slow"]
    assert items["default"]["avgRunDurationMs"] in (0, None)
    assert items["slow"]["avgRunDurationMs"] == 20000


def test_queue_endpoint_exposes_live_sent_and_active_counts_before_completion(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for payload in (
        {
            "type": "task-sent",
            "uuid": "task-live-1",
            "queue": "slow",
            "routing_key": "slow",
        },
        {
            "type": "task-received",
            "uuid": "task-live-1",
        },
        {
            "type": "task-started",
            "uuid": "task-live-1",
        },
        {
            "type": "task-sent",
            "uuid": "task-live-2",
            "queue": "slow",
            "routing_key": "slow",
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        queue_projector.apply(event)

    response = client.get("/api/queues/?limit=10")

    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert "slow" in items
    assert items["slow"]["sentCount"] == 1
    assert items["slow"]["activeCount"] == 1
    assert items["slow"]["succeededCount"] == 0
    assert items["slow"]["failedCount"] == 0


def test_queue_endpoint_excludes_future_eta_runs_from_live_backlog(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "scheduled-slow-1",
            "queue": "slow",
            "routing_key": "slow",
            "eta": "2999-03-18T21:30:00+00:00",
        }
    )
    raw_store.append(event)
    queue_projector.apply(event)

    response = client.get("/api/queues/?limit=10")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_queue_endpoint_counts_lost_runs_as_failed(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    queue_repository = queue_projector._repository
    client = TestClient(app)
    base = datetime.now(UTC).replace(microsecond=0)

    for event in (
        RawCeleryEvent(
            captured_at=base.isoformat(),
            event_type="task-sent",
            uuid="task-lost-1",
            hostname="producer@host",
            payload={"queue": "default", "routing_key": "default"},
        ),
        RawCeleryEvent(
            captured_at=(base + timedelta(seconds=1)).isoformat(),
            event_type="task-started",
            uuid="task-lost-1",
            hostname="default@worker",
            payload={},
        ),
    ):
        raw_store.append(event)
        queue_projector.apply(event)

    queue_repository.apply_task_event(
        task_id="task-lost-1",
        queue_name="default",
        routing_key="default",
        state="lost",
        captured_at=(base + timedelta(minutes=31)).isoformat(),
    )

    response = client.get("/api/queues/?limit=10")

    assert response.status_code == 200
    queue = response.json()["items"][0]
    assert queue["historicalFailedCount"] == 1
    assert queue["failedCount"] == 0


def test_queue_endpoint_keeps_future_scheduled_received_runs_out_of_active_counts(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for payload in (
        {
            "type": "task-sent",
            "uuid": "scheduled-received-1",
            "queue": "default",
            "routing_key": "default",
            "eta": "2999-03-18T21:30:00+00:00",
        },
        {
            "type": "task-received",
            "uuid": "scheduled-received-1",
            "eta": "2999-03-18T21:30:00+00:00",
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        queue_projector.apply(event)

    response = client.get("/api/queues/?limit=10")

    assert response.status_code == 200
    assert response.json()["items"] == []

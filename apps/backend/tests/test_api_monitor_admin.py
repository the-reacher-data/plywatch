from __future__ import annotations

from fastapi.testclient import TestClient

from plywatch.main import create_app
from plywatch.shared.raw_events import build_raw_event


def test_reset_monitor_clears_retained_projections_but_not_totals(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    schedule_projector = app.state.schedule_projector
    worker_projector = app.state.worker_projector
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store
    event_counter_store = app.state.event_counter_store

    task_event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "task-reset-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "task-reset-1",
        }
    )
    worker_event = build_raw_event(
        {
            "type": "worker-online",
            "hostname": "worker-a",
            "pid": 1,
        }
    )
    schedule_event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "schedule-reset-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "schedule-reset-1",
            "kwargs": "{'message': 'scheduled run', '__plywatch_schedule': {'id': 'schedule:reset', 'name': 'Schedule reset', 'pattern': '*/5 * * * *'}}",
        }
    )

    for event, handler in ((task_event, projector), (worker_event, worker_projector)):
        raw_store.append(event)
        event_counter_store.observe(event)
        handler.apply(event)
    queue_projector.apply(task_event)
    raw_store.append(schedule_event)
    event_counter_store.observe(schedule_event)
    projector.apply(schedule_event)
    schedule_projector.apply(schedule_event)
    queue_projector.apply(schedule_event)

    client = TestClient(app)
    response = client.post("/api/monitor/reset")

    assert response.status_code == 200
    assert response.json() == {
        "removedTasks": 2,
        "removedWorkers": 1,
        "removedQueues": 1,
        "removedRawEvents": 3,
    }
    assert client.get("/api/tasks/?limit=10").json()["items"] == []
    assert client.get("/api/workers/?limit=10").json()["items"] == []
    assert client.get("/api/queues/?limit=10").json()["items"] == []
    assert client.get("/api/schedules?limit=10").json()["items"] == []
    assert client.get("/api/events/raw?limit=10").json()["items"] == []
    assert client.get("/api/overview").json()["totalEventCount"] == 3


def test_remove_task_family_from_monitor_keeps_historical_queue_counts(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    queue_projector = app.state.queue_projector
    raw_store = app.state.raw_event_store

    payloads = (
        {
            "type": "task-sent",
            "uuid": "task-remove-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "task-remove-1",
        },
        {
            "type": "task-succeeded",
            "uuid": "task-remove-1",
            "result": "ok",
        },
        {
            "type": "task-sent",
            "uuid": "task-remove-1-callback",
            "name": "loom.callback.RecordSuccessCallback",
            "queue": "default",
            "routing_key": "default",
            "root_id": "task-remove-1",
            "parent_id": "task-remove-1",
        },
        {
            "type": "task-succeeded",
            "uuid": "task-remove-1-callback",
            "result": "ok",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)
        queue_projector.apply(event)

    client = TestClient(app)
    response = client.request("DELETE", "/api/monitor/tasks", json={"ids": ["task-remove-1"]})

    assert response.status_code == 200
    assert response.json()["removedCount"] == 2
    assert client.get("/api/tasks/?limit=10").json()["items"] == []
    queues = client.get("/api/queues/?limit=10").json()["items"]
    assert len(queues) == 1
    assert queues[0]["historicalSucceededCount"] == 2


def test_remove_schedule_from_monitor_removes_all_retained_runs(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    dispatcher = app.state.event_dispatcher
    raw_store = app.state.raw_event_store

    for task_id in ("schedule-run-1", "schedule-run-2"):
        event = build_raw_event(
            {
                "type": "task-sent",
                "uuid": task_id,
                "name": "lab.native.echo",
                "queue": "default",
                "routing_key": "default",
                "root_id": task_id,
                "kwargs": "{'message': 'scheduled run', '__plywatch_schedule': {'id': 'schedule:test', 'name': 'Schedule test', 'pattern': '*/5 * * * *'}}",
            }
        )
        raw_store.append(event)
        dispatcher.dispatch(event)

    client = TestClient(app)
    response = client.request("DELETE", "/api/monitor/schedules", json={"ids": ["schedule:test"]})

    assert response.status_code == 200
    assert response.json()["removedCount"] == 2
    assert client.get("/api/schedules?limit=10").json()["items"] == []

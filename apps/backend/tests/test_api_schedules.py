from __future__ import annotations

from fastapi.testclient import TestClient

from plywatch.main import create_app
from plywatch.shared.raw_events import build_raw_event


def test_schedule_endpoint_survives_task_repository_eviction(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_MAX_TASKS", "2")
    monkeypatch.setenv("PLYWATCH_MAX_SCHEDULE_RUNS", "20")
    app = create_app(start_consumer=False)
    dispatcher = app.state.event_dispatcher
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    scheduled_events = (
        {
            "type": "task-sent",
            "uuid": "scheduled-survive-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-survive-1",
            "kwargs": "{'message': 'scheduled survive 1', '__plywatch_schedule': {'id': 'schedule:survive', 'name': 'Schedule survive', 'pattern': '*/5 * * * *'}}",
        },
        {
            "type": "task-sent",
            "uuid": "scheduled-survive-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-survive-2",
            "kwargs": "{'message': 'scheduled survive 2', '__plywatch_schedule': {'id': 'schedule:survive', 'name': 'Schedule survive', 'pattern': '*/5 * * * *'}}",
        },
    )
    for payload in scheduled_events:
        event = build_raw_event(payload)
        raw_store.append(event)
        dispatcher.dispatch(event)

    for index in range(6):
        event = build_raw_event(
            {
                "type": "task-sent",
                "uuid": f"plain-task-{index}",
                "name": "loom.job.HelloSuccessJob",
                "queue": "default",
                "routing_key": "default",
                "root_id": f"plain-task-{index}",
            }
        )
        raw_store.append(event)
        dispatcher.dispatch(event)

    response = client.get("/api/schedules?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["scheduleId"] == "schedule:survive"
    assert body["items"][0]["totalRuns"] == 2
    assert app.state.task_repository.get("scheduled-survive-1") is None
    assert app.state.schedule_repository.get("scheduled-survive-1") is not None


def test_remove_schedule_from_monitor_clears_dedicated_schedule_repository(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_MAX_TASKS", "1")
    monkeypatch.setenv("PLYWATCH_MAX_SCHEDULE_RUNS", "20")
    app = create_app(start_consumer=False)
    dispatcher = app.state.event_dispatcher
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for task_id in ("schedule-run-1", "schedule-run-2"):
        event = build_raw_event(
            {
                "type": "task-sent",
                "uuid": task_id,
                "name": "lab.native.echo",
                "queue": "default",
                "routing_key": "default",
                "root_id": task_id,
                "kwargs": "{'message': 'scheduled run', '__plywatch_schedule': {'id': 'schedule:cleanup', 'name': 'Schedule cleanup', 'pattern': '*/5 * * * *'}}",
            }
        )
        raw_store.append(event)
        dispatcher.dispatch(event)

    overflow_event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "overflow-task",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "overflow-task",
        }
    )
    raw_store.append(overflow_event)
    dispatcher.dispatch(overflow_event)

    response = client.request("DELETE", "/api/monitor/schedules", json={"ids": ["schedule:cleanup"]})

    assert response.status_code == 200
    assert response.json()["removedCount"] == 2
    assert client.get("/api/schedules?limit=10").json()["items"] == []

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from plywatch.main import create_app
from plywatch.shared.raw_events import build_raw_event


@pytest.fixture(autouse=True)
def _disable_metrics(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")


def test_task_endpoints_expose_consolidated_views() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    task_id = "task-http-1"

    for payload in (
        {
            "type": "task-sent",
            "uuid": task_id,
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": task_id,
            "parent_id": None,
            "kwargs": "{'payload': {'message': 'http'}}",
        },
        {
            "type": "task-received",
            "uuid": task_id,
            "name": "loom.job.HelloSuccessJob",
        },
        {
            "type": "task-started",
            "uuid": task_id,
        },
        {
            "type": "task-succeeded",
            "uuid": task_id,
            "result": "{'scenario': 'success'}",
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    client = TestClient(app)

    overview = client.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["taskCount"] == 1
    assert overview.json()["workerCount"] == 0
    assert overview.json()["maxTasks"] == 2000
    assert overview.json()["maxAgeSeconds"] == 21600

    tasks = client.get("/api/tasks/?limit=5")
    assert tasks.status_code == 200
    tasks_payload = tasks.json()
    assert tasks_payload["hasNext"] is False
    assert tasks_payload["nextCursor"] is None
    task_item = tasks_payload["items"][0]
    assert task_item["uuid"] == task_id
    assert task_item["state"] == "succeeded"

    raw_events = client.get("/api/events/raw?limit=2")
    assert raw_events.status_code == 200
    assert raw_events.json()["limit"] == 2

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["resultPreview"] == "{'scenario': 'success'}"

    events = client.get(f"/api/tasks/{task_id}/events")
    assert events.status_code == 200
    assert events.json()["count"] == 4

    graph = client.get(f"/api/tasks/{task_id}/graph")
    assert graph.status_code == 200
    assert graph.json()["rootId"] == task_id
    assert graph.json()["nodes"][0]["uuid"] == task_id

    missing = client.get("/api/tasks/missing-task")
    assert missing.status_code == 404


def test_task_list_is_fixed_to_cursor_pagination() -> None:
    app = create_app(start_consumer=False)
    client = TestClient(app)

    response = client.get("/api/tasks/?pagination=offset")

    assert response.status_code == 400
    assert "cannot override" in response.json()["detail"]


def test_task_list_applies_queue_filter_before_pagination() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for index in range(3):
        queue_name = "slow" if index < 2 else "default"
        task_id = f"task-filter-{index}"
        event = build_raw_event(
            {
                "type": "task-sent",
                "uuid": task_id,
                "name": "loom.job.HelloSuccessJob",
                "queue": queue_name,
                "routing_key": queue_name,
                "root_id": task_id,
            }
        )
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/tasks/?limit=10&queue=slow")

    assert response.status_code == 200
    body = response.json()
    assert [item["queue"] for item in body["items"]] == ["slow", "slow"]


def test_task_list_can_page_logical_failed_section_families() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "failed-root-1",
            "name": "loom.job.HelloFailureJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "failed-root-1",
        },
        {
            "type": "task-failed",
            "uuid": "failed-root-1",
            "exception": "boom",
        },
        {
            "type": "task-sent",
            "uuid": "failed-root-1-callback",
            "name": "loom.callback.RecordSuccessCallback",
            "queue": "default",
            "routing_key": "default",
            "root_id": "failed-root-1",
            "parent_id": "failed-root-1",
        },
        {
            "type": "task-succeeded",
            "uuid": "failed-root-1-callback",
            "result": "{'callback': 'ok'}",
        },
        {
            "type": "task-sent",
            "uuid": "failed-root-2",
            "name": "loom.job.HelloFailureJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "failed-root-2",
        },
        {
            "type": "task-failed",
            "uuid": "failed-root-2",
            "exception": "boom again",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/tasks/?limit=1&section=failed")

    assert response.status_code == 200
    body = response.json()
    assert body["hasNext"] is True
    assert {item["uuid"] for item in body["items"]} in (
        {"failed-root-1", "failed-root-1-callback"},
        {"failed-root-2"},
    )


def test_task_section_counts_return_family_totals_not_loaded_page_counts() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "parent-running",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "parent-running",
        },
        {
            "type": "task-sent",
            "uuid": "child-queued",
            "name": "loom.callback.RecordSuccessCallback",
            "queue": "default",
            "routing_key": "default",
            "root_id": "parent-running",
            "parent_id": "parent-running",
        },
        {
            "type": "task-sent",
            "uuid": "root-succeeded",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "root-succeeded",
        },
        {
            "type": "task-succeeded",
            "uuid": "root-succeeded",
        },
        {
            "type": "task-sent",
            "uuid": "root-failed",
            "name": "loom.job.HelloFailureJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "root-failed",
        },
        {
            "type": "task-failed",
            "uuid": "root-failed",
            "exception": "boom",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/task-sections?queue=default")

    assert response.status_code == 200
    assert response.json() == {
        "queuedFamilies": 1,
        "runningFamilies": 0,
        "succeededFamilies": 1,
        "failedFamilies": 1,
        "familyCount": 3,
        "executionCount": 4,
        "completedExecutions": 2,
        "totalExecutions": 4,
    }


def test_task_graph_returns_parent_and_callback_nodes() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for payload in (
        {
            "type": "task-sent",
            "uuid": "parent-graph-1",
            "name": "loom.job.HelloSuccessJob",
            "root_id": "parent-graph-1",
        },
        {
            "type": "task-sent",
            "uuid": "child-graph-1",
            "name": "loom.callback.RecordSuccessCallback",
            "root_id": "parent-graph-1",
            "parent_id": "parent-graph-1",
        },
    ):
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/tasks/child-graph-1/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["rootId"] == "parent-graph-1"
    assert {node["uuid"] for node in body["nodes"]} == {"parent-graph-1", "child-graph-1"}
    assert body["edges"] == [
        {
            "source": "parent-graph-1",
            "target": "child-graph-1",
            "relation": "callback",
        }
    ]


def test_task_detail_exposes_schedule_metadata_from_events(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)
    scheduled_for = _future_iso(minutes=30)

    event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "scheduled-task-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-task-1",
            "eta": scheduled_for,
            "kwargs": "{'message': 'scheduled run', '__plywatch_schedule': {'id': 'schedule:nightly-report', 'name': 'Nightly report', 'pattern': '*/15 * * * *'}}",
        }
    )
    raw_store.append(event)
    projector.apply(event)

    response = client.get("/api/tasks/scheduled-task-1")

    assert response.status_code == 200
    assert response.json()["scheduleId"] == "schedule:nightly-report"
    assert response.json()["scheduleName"] == "Nightly report"
    assert response.json()["schedulePattern"] == "*/15 * * * *"
    assert response.json()["scheduledFor"] == scheduled_for


def test_schedule_endpoint_groups_runs_by_observed_schedule(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    dispatcher = app.state.event_dispatcher
    raw_store = app.state.raw_event_store
    client = TestClient(app)
    first_scheduled_for = _future_iso(minutes=30)
    second_scheduled_for = _future_iso(minutes=60)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "scheduled-task-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-task-1",
            "eta": first_scheduled_for,
            "kwargs": "{'message': 'scheduled run 1', '__plywatch_schedule': {'id': 'schedule:nightly-report', 'name': 'Nightly report', 'pattern': '*/15 * * * *'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "scheduled-task-1",
        },
        {
            "type": "task-sent",
            "uuid": "scheduled-task-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-task-2",
            "eta": second_scheduled_for,
            "kwargs": "{'message': 'scheduled run 2', '__plywatch_schedule': {'id': 'schedule:nightly-report', 'name': 'Nightly report', 'pattern': '*/15 * * * *'}}",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        dispatcher.dispatch(event)

    response = client.get("/api/schedules?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    schedule = body["items"][0]
    assert schedule["scheduleId"] == "schedule:nightly-report"
    assert schedule["scheduleName"] == "Nightly report"
    assert schedule["totalRuns"] == 2
    assert schedule["pendingRuns"] == 1
    assert schedule["queuedRuns"] == 0
    assert schedule["runningRuns"] == 0
    assert schedule["succeededRuns"] == 1
    assert len(schedule["recentRuns"]) == 1


def test_task_section_counts_include_scheduled_runs_when_tasks_list_shows_them(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)
    scheduled_for = _future_iso(minutes=30)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "scheduled-task-succeeded",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-task-succeeded",
            "eta": scheduled_for,
            "kwargs": "{'message': 'scheduled run', '__plywatch_schedule': {'id': 'schedule:nightly-report', 'name': 'Nightly report', 'pattern': '*/15 * * * *'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "scheduled-task-succeeded",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/task-sections")

    assert response.status_code == 200
    assert response.json()["succeededFamilies"] == 1
    assert response.json()["familyCount"] == 1


def test_completed_families_survive_live_backlog_pressure(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_MAX_TASKS", "5")
    monkeypatch.setenv("PLYWATCH_MAX_COMPLETED_TASKS", "50")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    for index in range(8):
        for payload in (
            {
                "type": "task-sent",
                "uuid": f"done-{index}",
                "name": "loom.job.HelloSuccessJob",
                "queue": "default",
                "routing_key": "default",
                "root_id": f"done-{index}",
            },
            {
                "type": "task-succeeded",
                "uuid": f"done-{index}",
                "result": "ok",
            },
        ):
            event = build_raw_event(payload)
            raw_store.append(event)
            projector.apply(event)

    for index in range(20):
        event = build_raw_event(
            {
                "type": "task-sent",
                "uuid": f"queued-{index}",
                "name": "loom.job.HelloSuccessJob",
                "queue": "default",
                "routing_key": "default",
                "root_id": f"queued-{index}",
            }
        )
        raw_store.append(event)
        projector.apply(event)

    counts = client.get("/api/task-sections").json()
    assert counts["succeededFamilies"] == 8
    assert counts["queuedFamilies"] >= 5

    succeeded = client.get("/api/tasks/?limit=20&section=succeeded").json()
    assert len(succeeded["items"]) == 8

    detail = client.get("/api/tasks/done-0")
    assert detail.status_code == 200
    assert detail.json()["state"] == "succeeded"


def _future_iso(*, minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def test_task_section_counts_group_native_canvas_runs_by_logical_workflow(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "native-success-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
        },
        {
            "type": "task-sent",
            "uuid": "native-success-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
        },
        {
            "type": "task-sent",
            "uuid": "native-success-3",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
        },
        {
            "type": "task-sent",
            "uuid": "chain-head",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'head', '__plywatch_canvas': {'kind': 'chain', 'id': 'canvas-chain-1', 'role': 'head'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chain-tail",
            "name": "lab.native.followup",
            "queue": "default",
            "routing_key": "default",
            "parent_id": "chain-head",
            "kwargs": "{'message': 'tail', '__plywatch_canvas': {'kind': 'chain', 'id': 'canvas-chain-1', 'role': 'tail'}}",
        },
        {
            "type": "task-sent",
            "uuid": "group-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'g1', '__plywatch_canvas': {'kind': 'group', 'id': 'canvas-group-1', 'role': 'member'}}",
        },
        {
            "type": "task-sent",
            "uuid": "group-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'g2', '__plywatch_canvas': {'kind': 'group', 'id': 'canvas-group-1', 'role': 'member'}}",
        },
        {
            "type": "task-sent",
            "uuid": "group-3",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'g3', '__plywatch_canvas': {'kind': 'group', 'id': 'canvas-group-1', 'role': 'member'}}",
        },
        {
            "type": "task-sent",
            "uuid": "group-4",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'g4', '__plywatch_canvas': {'kind': 'group', 'id': 'canvas-group-1', 'role': 'member'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chord-header-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'h1', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-chord-1', 'role': 'header'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chord-header-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'h2', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-chord-1', 'role': 'header'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chord-header-3",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'h3', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-chord-1', 'role': 'header'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chord-header-4",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'message': 'h4', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-chord-1', 'role': 'header'}}",
        },
        {
            "type": "task-sent",
            "uuid": "chord-body",
            "name": "lab.native.collect",
            "queue": "default",
            "routing_key": "default",
            "kwargs": "{'__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-chord-1', 'role': 'body'}}",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/task-sections")

    assert response.status_code == 200
    assert response.json()["familyCount"] == 6
    assert response.json()["executionCount"] == 14


def test_task_graph_groups_native_chord_members_under_canvas_root() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "native-header-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "native-header-1",
            "kwargs": "{'message': 'h1', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-1', 'role': 'header'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "native-header-1",
            "name": "lab.native.echo",
            "result": "{'kind': 'native', 'message': 'h1'}",
        },
        {
            "type": "task-sent",
            "uuid": "native-header-2",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "native-header-2",
            "kwargs": "{'message': 'h2', '__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-1', 'role': 'header'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "native-header-2",
            "name": "lab.native.echo",
            "result": "{'kind': 'native', 'message': 'h2'}",
        },
        {
            "type": "task-sent",
            "uuid": "native-body-1",
            "name": "lab.native.collect",
            "queue": "default",
            "routing_key": "default",
            "root_id": "native-header-2",
            "parent_id": "native-header-2",
            "kwargs": "{'__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-1', 'role': 'body'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "native-body-1",
            "name": "lab.native.collect",
            "result": "{'kind': 'native', 'count': 2}",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/tasks/native-body-1/graph")
    detail = client.get("/api/tasks/native-body-1")

    assert response.status_code == 200
    assert detail.status_code == 200
    body = response.json()
    assert detail.json()["rootId"] == "canvas:canvas-1"
    assert body["rootId"] == "canvas:canvas-1"
    assert {node["uuid"] for node in body["nodes"]} == {
        "canvas:canvas-1",
        "native-header-1",
        "native-header-2",
        "native-body-1",
    }
    assert {node["kind"] for node in body["nodes"]} == {"canvas", "job"}
    assert {
        (edge["source"], edge["target"], edge["relation"])
        for edge in body["edges"]
    } == {
        ("canvas:canvas-1", "native-body-1", "body"),
        ("canvas:canvas-1", "native-header-1", "header"),
        ("canvas:canvas-1", "native-header-2", "header"),
    }


def test_task_graph_groups_native_chain_under_canvas_root() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "native-chain-head",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "native-chain-head",
            "kwargs": "{'message': 'head', '__plywatch_canvas': {'kind': 'chain', 'id': 'canvas-chain-1', 'role': 'head'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "native-chain-head",
            "name": "lab.native.echo",
            "result": "{'kind': 'native', 'message': 'head'}",
        },
        {
            "type": "task-sent",
            "uuid": "native-chain-tail",
            "name": "lab.native.followup",
            "queue": "default",
            "routing_key": "default",
            "root_id": "native-chain-head",
            "parent_id": "native-chain-head",
            "kwargs": "{'message': 'tail', '__plywatch_canvas': {'kind': 'chain', 'id': 'canvas-chain-1', 'role': 'tail'}}",
        },
        {
            "type": "task-succeeded",
            "uuid": "native-chain-tail",
            "name": "lab.native.followup",
            "result": "{'kind': 'native', 'message': 'tail'}",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/tasks/native-chain-tail/graph")
    detail = client.get("/api/tasks/native-chain-tail")

    assert response.status_code == 200
    assert detail.status_code == 200
    body = response.json()
    assert detail.json()["rootId"] == "canvas:canvas-chain-1"
    assert body["rootId"] == "canvas:canvas-chain-1"
    assert {node["uuid"] for node in body["nodes"]} == {
        "canvas:canvas-chain-1",
        "native-chain-head",
        "native-chain-tail",
    }
    assert {
        (edge["source"], edge["target"], edge["relation"])
        for edge in body["edges"]
    } == {
        ("canvas:canvas-chain-1", "native-chain-head", "head"),
        ("native-chain-head", "native-chain-tail", "chain"),
    }


def test_task_sections_exclude_future_scheduled_runs_from_history_counts() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    scheduled_for = _future_iso(minutes=30)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "scheduled-future-1",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-future-1",
            "kwargs": (
                "{'message': 'future', '__plywatch_schedule': "
                "{'id': 'schedule:test', 'name': 'Test schedule', 'pattern': 'every 30s'}}"
            ),
            "eta": scheduled_for,
        },
        {
            "type": "task-sent",
            "uuid": "regular-queued-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "regular-queued-1",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    response = client.get("/api/task-sections?queue=default")

    assert response.status_code == 200
    assert response.json() == {
        "queuedFamilies": 1,
        "runningFamilies": 0,
        "succeededFamilies": 0,
        "failedFamilies": 0,
        "familyCount": 1,
        "executionCount": 1,
        "completedExecutions": 0,
        "totalExecutions": 1,
    }


def test_overview_excludes_future_scheduled_runs_from_task_count() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "scheduled-future-overview",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "scheduled-future-overview",
            "kwargs": (
                "{'message': 'future', '__plywatch_schedule': "
                "{'id': 'schedule:test', 'name': 'Test schedule', 'pattern': 'every 30s'}}"
            ),
            "eta": _future_iso(minutes=30),
        },
        {
            "type": "task-sent",
            "uuid": "regular-overview-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "regular-overview-1",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    overview = client.get("/api/overview")

    assert overview.status_code == 200
    assert overview.json()["taskCount"] == 1


def test_overview_counts_logical_task_families_not_raw_executions() -> None:
    app = create_app(start_consumer=False)
    projector = app.state.task_projector
    raw_store = app.state.raw_event_store
    client = TestClient(app)

    payloads = (
        {
            "type": "task-sent",
            "uuid": "root-overview-1",
            "name": "loom.job.HelloSuccessJob",
            "queue": "default",
            "routing_key": "default",
            "root_id": "root-overview-1",
        },
        {
            "type": "task-sent",
            "uuid": "child-overview-1",
            "name": "loom.callback.RecordSuccessCallback",
            "queue": "default",
            "routing_key": "default",
            "root_id": "root-overview-1",
            "parent_id": "root-overview-1",
        },
    )

    for payload in payloads:
        event = build_raw_event(payload)
        raw_store.append(event)
        projector.apply(event)

    overview = client.get("/api/overview")

    assert overview.status_code == 200
    assert overview.json()["taskCount"] == 1


def test_overview_redacts_broker_url_credentials(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_CELERY_BROKER_URL", "pyamqp://guest:guest@rabbitmq:5672//")
    app = create_app(start_consumer=False)
    client = TestClient(app)

    overview = client.get("/api/overview")

    assert overview.status_code == 200
    broker_url = overview.json()["brokerUrl"]
    assert broker_url == "pyamqp://guest:***@rabbitmq:5672//"
    assert "guest:guest@" not in broker_url

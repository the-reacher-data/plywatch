from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plywatch.shared.raw_events import build_raw_event
from plywatch.task.envelope import from_raw_task_event
from plywatch.task.policies import is_future_eta, is_future_scheduled_task


def test_task_envelope_normalizes_canvas_and_schedule_metadata() -> None:
    scheduled_for = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
    raw_event = build_raw_event(
        {
            "type": "task-sent",
            "uuid": "task-1",
            "hostname": "worker-a",
            "name": "lab.native.echo",
            "queue": "default",
            "routing_key": "default",
            "root_id": "task-1",
            "parent_id": "parent-1",
            "args": "('hello',)",
            "kwargs": (
                "{'message': 'hello', "
                "'__plywatch_canvas': {'kind': 'chord', 'id': 'canvas-1', 'role': 'header'}, "
                "'__plywatch_schedule': {'id': 'schedule:nightly', 'name': 'Nightly', 'pattern': '0 * * * *'}}"
            ),
            "eta": scheduled_for,
        }
    )

    envelope = from_raw_task_event(raw_event)

    assert envelope is not None
    assert envelope.task_id == "task-1"
    assert envelope.event_type == "task-sent"
    assert envelope.state == "sent"
    assert envelope.hostname == "worker-a"
    assert envelope.canvas_kind == "chord"
    assert envelope.canvas_id == "canvas-1"
    assert envelope.canvas_role == "header"
    assert envelope.schedule_id == "schedule:nightly"
    assert envelope.schedule_name == "Nightly"
    assert envelope.schedule_pattern == "0 * * * *"
    assert envelope.scheduled_for == scheduled_for


def test_task_envelope_keeps_result_and_exception_previews_trimmed() -> None:
    raw_event = build_raw_event(
        {
            "type": "task-failed",
            "uuid": "task-2",
            "result": "x" * 800,
            "exception": "boom" * 200,
        }
    )

    envelope = from_raw_task_event(raw_event)

    assert envelope is not None
    assert envelope.result_preview == "x" * 500
    assert envelope.exception_preview == ("boom" * 200)[:500]


def test_task_envelope_ignores_non_task_events() -> None:
    raw_event = build_raw_event({"type": "worker-online", "hostname": "worker-a"})

    assert from_raw_task_event(raw_event) is None


def test_schedule_policies_depend_on_observed_eta_not_external_calendar() -> None:
    reference_at = datetime.now(UTC).isoformat()
    future_eta = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    past_eta = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()

    assert is_future_eta(scheduled_for=future_eta, reference_at=reference_at) is True
    assert is_future_eta(scheduled_for=past_eta, reference_at=reference_at) is False
    assert (
        is_future_scheduled_task(
            type(
                "ScheduledTask",
                (),
                {
                    "schedule_id": "schedule:nightly",
                    "scheduled_for": future_eta,
                    "state": "sent",
                    "last_seen_at": reference_at,
                },
            )()
        )
        is True
    )
    assert (
        is_future_scheduled_task(
            type(
                "ScheduledTask",
                (),
                {
                    "schedule_id": "schedule:nightly",
                    "scheduled_for": future_eta,
                    "state": "received",
                    "last_seen_at": reference_at,
                },
            )()
        )
        is True
    )

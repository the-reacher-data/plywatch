"""Normalized task event envelope derived from raw Celery events."""

from __future__ import annotations

from dataclasses import dataclass

from plywatch.shared.raw_events import JsonValue, RawCeleryEvent
from plywatch.task.constants import (
    TASK_EVENTS,
    TASK_EVENT_FAILED,
    TASK_EVENT_RECEIVED,
    TASK_EVENT_RETRIED,
    TASK_EVENT_SENT,
    TASK_EVENT_STARTED,
    TASK_EVENT_SUCCEEDED,
    TaskEventType,
)
from plywatch.task.metadata import extract_canvas_metadata, extract_eta, extract_schedule_metadata
from plywatch.task.models import TaskState

STATE_BY_EVENT: dict[str, TaskState] = {
    TASK_EVENT_SENT: "sent",
    TASK_EVENT_RECEIVED: "received",
    TASK_EVENT_STARTED: "started",
    TASK_EVENT_RETRIED: "retrying",
    TASK_EVENT_SUCCEEDED: "succeeded",
    TASK_EVENT_FAILED: "failed",
}


@dataclass(frozen=True)
class TaskEnvelope:
    """Stable internal task event model used by projectors."""

    task_id: str
    event_type: TaskEventType
    state: TaskState
    captured_at: str
    hostname: str | None
    name: str | None
    queue_name: str | None
    routing_key: str | None
    root_id: str | None
    parent_id: str | None
    args_preview: str | None
    kwargs_preview: str | None
    result_preview: str | None
    exception_preview: str | None
    canvas_kind: str | None
    canvas_id: str | None
    canvas_role: str | None
    schedule_id: str | None
    schedule_name: str | None
    schedule_pattern: str | None
    scheduled_for: str | None
    raw_payload: dict[str, JsonValue]


def from_raw_task_event(event: RawCeleryEvent) -> TaskEnvelope | None:
    """Normalize one raw Celery event into a projector-friendly task envelope."""

    if event.event_type not in TASK_EVENTS or event.uuid is None:
        return None
    event_type = event.event_type

    canvas_metadata = extract_canvas_metadata(event.payload)
    schedule_metadata = extract_schedule_metadata(event.payload)

    return TaskEnvelope(
        task_id=event.uuid,
        event_type=event_type,
        state=STATE_BY_EVENT[event_type],
        captured_at=event.captured_at,
        hostname=event.hostname,
        name=_string_value(event.payload.get("name")),
        queue_name=_string_value(event.payload.get("queue")),
        routing_key=_string_value(event.payload.get("routing_key")),
        root_id=_string_value(event.payload.get("root_id")),
        parent_id=_string_value(event.payload.get("parent_id")),
        args_preview=_preview_string(event.payload.get("args")),
        kwargs_preview=_preview_string(event.payload.get("kwargs")),
        result_preview=_preview_string(event.payload.get("result")),
        exception_preview=_preview_string(event.payload.get("exception")),
        canvas_kind=canvas_metadata["kind"] if canvas_metadata is not None else None,
        canvas_id=canvas_metadata["id"] if canvas_metadata is not None else None,
        canvas_role=canvas_metadata.get("role") if canvas_metadata is not None else None,
        schedule_id=schedule_metadata["id"] if schedule_metadata is not None else None,
        schedule_name=schedule_metadata["name"] if schedule_metadata is not None else None,
        schedule_pattern=schedule_metadata.get("pattern") if schedule_metadata is not None else None,
        scheduled_for=extract_eta(event.payload),
        raw_payload=event.payload,
    )


def _string_value(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) else None


def _preview_string(value: JsonValue | None, max_length: int = 500) -> str | None:
    return value[:max_length] if isinstance(value, str) else None

"""Core task projection models and public task views."""

from __future__ import annotations

from typing import Final, Literal

import msgspec
from loom.core.model import LoomStruct
from loom.core.response import Response

from plywatch.shared.raw_events import JsonValue, RawCeleryEvent
from plywatch.task.constants import (
    CANVAS_KIND_CHAIN,
    CANVAS_KIND_CHORD,
    CANVAS_KIND_GROUP,
    CANVAS_ROLE_TAIL,
    CANVAS_ROOT_PREFIX,
    TASK_KIND_CALLBACK,
    TASK_KIND_CALLBACK_ERROR,
    TASK_KIND_JOB,
    TASK_KIND_PREFIX_CALLBACK,
    TASK_KIND_PREFIX_CALLBACK_ERROR,
    TASK_KIND_PREFIX_JOB,
    TASK_KIND_UNKNOWN,
)

CanvasKind = Literal["chain", "group", "chord"]
CanvasRole = Literal["head", "tail", "member", "header", "body"]
TaskKind = Literal["job", "callback", "callback_error", "unknown"]
TaskState = Literal["sent", "received", "started", "retrying", "succeeded", "failed", "lost"]
_TASK_KIND_PREFIXES: Final[tuple[tuple[str, TaskKind], ...]] = (
    (TASK_KIND_PREFIX_CALLBACK_ERROR, TASK_KIND_CALLBACK_ERROR),
    (TASK_KIND_PREFIX_CALLBACK, TASK_KIND_CALLBACK),
    (TASK_KIND_PREFIX_JOB, TASK_KIND_JOB),
)
_SUMMARY_PAYLOAD_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("uuid", "uuid"),
    ("name", "name"),
    ("kind", "kind"),
    ("state", "state"),
    ("queue", "queue"),
    ("routingKey", "routing_key"),
    ("rootId", "root_id"),
    ("parentId", "parent_id"),
    ("retries", "retries"),
    ("firstSeenAt", "first_seen_at"),
    ("lastSeenAt", "last_seen_at"),
    ("sentAt", "sent_at"),
    ("receivedAt", "received_at"),
    ("startedAt", "started_at"),
    ("finishedAt", "finished_at"),
    ("workerHostname", "worker_hostname"),
    ("resultPreview", "result_preview"),
    ("exceptionPreview", "exception_preview"),
    ("canvasKind", "canvas_kind"),
    ("canvasId", "canvas_id"),
    ("canvasRole", "canvas_role"),
    ("scheduleId", "schedule_id"),
    ("scheduleName", "schedule_name"),
    ("schedulePattern", "schedule_pattern"),
    ("scheduledFor", "scheduled_for"),
)

class TaskTimelineEvent(LoomStruct, kw_only=True):
    """One retained lifecycle event belonging to a task."""

    captured_at: str
    event_type: str
    payload: dict[str, JsonValue]


class TaskSnapshot(LoomStruct, kw_only=True):
    """Consolidated task state derived from the raw Celery event stream."""

    uuid: str
    name: str | None = None
    kind: TaskKind = "unknown"
    state: TaskState = "sent"
    queue: str | None = None
    routing_key: str | None = None
    root_id: str | None = None
    parent_id: str | None = None
    children_ids: list[str] = msgspec.field(default_factory=list)
    retries: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    sent_at: str | None = None
    received_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    worker_hostname: str | None = None
    result_preview: str | None = None
    exception_preview: str | None = None
    args_preview: str | None = None
    kwargs_preview: str | None = None
    canvas_kind: CanvasKind | None = None
    canvas_id: str | None = None
    canvas_role: CanvasRole | None = None
    schedule_id: str | None = None
    schedule_name: str | None = None
    schedule_pattern: str | None = None
    scheduled_for: str | None = None
    events: list[TaskTimelineEvent] = msgspec.field(default_factory=list)


class TaskSummaryView(Response, frozen=True, kw_only=True):
    """Public summary view for one consolidated task."""

    uuid: str
    name: str | None = None
    kind: str = "unknown"
    state: str = "sent"
    queue: str | None = None
    routing_key: str | None = None
    root_id: str | None = None
    parent_id: str | None = None
    children_ids: tuple[str, ...] = ()
    retries: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    sent_at: str | None = None
    received_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    worker_hostname: str | None = None
    result_preview: str | None = None
    exception_preview: str | None = None
    canvas_kind: CanvasKind | None = None
    canvas_id: str | None = None
    canvas_role: CanvasRole | None = None
    schedule_id: str | None = None
    schedule_name: str | None = None
    schedule_pattern: str | None = None
    scheduled_for: str | None = None


class TaskDetailView(Response, frozen=True, kw_only=True):
    """Detailed public view for one consolidated task."""

    uuid: str
    name: str | None = None
    kind: str = "unknown"
    state: str = "sent"
    queue: str | None = None
    routing_key: str | None = None
    root_id: str | None = None
    parent_id: str | None = None
    children_ids: tuple[str, ...] = ()
    retries: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    sent_at: str | None = None
    received_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    worker_hostname: str | None = None
    result_preview: str | None = None
    exception_preview: str | None = None
    args_preview: str | None = None
    kwargs_preview: str | None = None
    canvas_kind: CanvasKind | None = None
    canvas_id: str | None = None
    canvas_role: CanvasRole | None = None
    schedule_id: str | None = None
    schedule_name: str | None = None
    schedule_pattern: str | None = None
    scheduled_for: str | None = None


class TaskTimelineEventView(Response, frozen=True, kw_only=True):
    """Public timeline event view for one task."""

    captured_at: str
    event_type: str
    payload: dict[str, JsonValue]


class TaskTimelineResponse(Response, frozen=True, kw_only=True):
    """Response containing the retained timeline of one task."""

    task_id: str
    items: tuple[TaskTimelineEventView, ...]
    count: int


class TaskGraphNodeView(Response, frozen=True, kw_only=True):
    """Graph node view for one task in the execution graph."""

    uuid: str
    name: str | None = None
    kind: str = "unknown"
    state: str = "sent"
    root_id: str | None = None
    parent_id: str | None = None
    queue: str | None = None
    worker_hostname: str | None = None


class TaskGraphEdgeView(Response, frozen=True, kw_only=True):
    """Directed edge between two related task nodes."""

    source: str
    target: str
    relation: str


class TaskGraphResponse(Response, frozen=True, kw_only=True):
    """Response containing the execution graph of one task workflow."""

    task_id: str
    root_id: str
    nodes: tuple[TaskGraphNodeView, ...]
    edges: tuple[TaskGraphEdgeView, ...]


class TaskSectionCountsView(Response, frozen=True, kw_only=True):
    """Aggregated task-family counters for the tasks monitor sections."""

    queued_families: int = 0
    running_families: int = 0
    succeeded_families: int = 0
    failed_families: int = 0
    family_count: int = 0
    execution_count: int = 0
    completed_executions: int = 0
    total_executions: int = 0


def classify_task_kind(name: str | None) -> TaskKind:
    """Classify a task from its Celery name."""
    if name is None:
        return TASK_KIND_UNKNOWN
    normalized = name.strip()
    if not normalized:
        return TASK_KIND_UNKNOWN
    for prefix, kind in _TASK_KIND_PREFIXES:
        if normalized.startswith(prefix):
            return kind
    return TASK_KIND_JOB


def build_timeline_event(event: RawCeleryEvent) -> TaskTimelineEvent:
    """Convert one raw event into a retained task timeline event."""
    return TaskTimelineEvent(
        captured_at=event.captured_at,
        event_type=event.event_type,
        payload=event.payload,
    )


def to_summary_view(snapshot: TaskSnapshot) -> TaskSummaryView:
    """Convert one snapshot into its public summary representation."""
    return TaskSummaryView(
        uuid=snapshot.uuid,
        name=snapshot.name,
        kind=snapshot.kind,
        state=snapshot.state,
        queue=snapshot.queue,
        routing_key=snapshot.routing_key,
        root_id=_public_root_id(snapshot),
        parent_id=_public_parent_id(snapshot),
        children_ids=tuple(snapshot.children_ids),
        retries=snapshot.retries,
        first_seen_at=snapshot.first_seen_at,
        last_seen_at=snapshot.last_seen_at,
        sent_at=snapshot.sent_at,
        received_at=snapshot.received_at,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        worker_hostname=snapshot.worker_hostname,
        result_preview=snapshot.result_preview,
        exception_preview=snapshot.exception_preview,
        canvas_kind=snapshot.canvas_kind,
        canvas_id=snapshot.canvas_id,
        canvas_role=snapshot.canvas_role,
        schedule_id=snapshot.schedule_id,
        schedule_name=snapshot.schedule_name,
        schedule_pattern=snapshot.schedule_pattern,
        scheduled_for=snapshot.scheduled_for,
    )


def to_detail_view(snapshot: TaskSnapshot) -> TaskDetailView:
    """Convert one snapshot into its public detail representation."""
    return TaskDetailView(
        uuid=snapshot.uuid,
        name=snapshot.name,
        kind=snapshot.kind,
        state=snapshot.state,
        queue=snapshot.queue,
        routing_key=snapshot.routing_key,
        root_id=_public_root_id(snapshot),
        parent_id=_public_parent_id(snapshot),
        children_ids=tuple(snapshot.children_ids),
        retries=snapshot.retries,
        first_seen_at=snapshot.first_seen_at,
        last_seen_at=snapshot.last_seen_at,
        sent_at=snapshot.sent_at,
        received_at=snapshot.received_at,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        worker_hostname=snapshot.worker_hostname,
        result_preview=snapshot.result_preview,
        exception_preview=snapshot.exception_preview,
        args_preview=snapshot.args_preview,
        kwargs_preview=snapshot.kwargs_preview,
        canvas_kind=snapshot.canvas_kind,
        canvas_id=snapshot.canvas_id,
        canvas_role=snapshot.canvas_role,
        schedule_id=snapshot.schedule_id,
        schedule_name=snapshot.schedule_name,
        schedule_pattern=snapshot.schedule_pattern,
        scheduled_for=snapshot.scheduled_for,
    )


def to_timeline_event_view(event: TaskTimelineEvent) -> TaskTimelineEventView:
    """Convert one internal timeline event into its public representation."""
    return TaskTimelineEventView(
        captured_at=event.captured_at,
        event_type=event.event_type,
        payload=event.payload,
    )


def to_task_summary_payload(view: TaskSummaryView) -> dict[str, JsonValue]:
    """Convert one task summary view into the frontend payload shape."""
    payload = {
        public_key: getattr(view, source_attr)
        for public_key, source_attr in _SUMMARY_PAYLOAD_FIELDS
    }
    payload["childrenIds"] = list(view.children_ids)
    return payload


def to_graph_node_view(snapshot: TaskSnapshot) -> TaskGraphNodeView:
    """Convert one snapshot into a graph node view."""
    return TaskGraphNodeView(
        uuid=snapshot.uuid,
        name=snapshot.name,
        kind=snapshot.kind,
        state=snapshot.state,
        root_id=snapshot.root_id,
        parent_id=snapshot.parent_id,
        queue=snapshot.queue,
        worker_hostname=snapshot.worker_hostname,
    )


def _public_root_id(snapshot: TaskSnapshot) -> str | None:
    if snapshot.canvas_id is None:
        return snapshot.root_id
    return f"{CANVAS_ROOT_PREFIX}{snapshot.canvas_id}"


def _public_parent_id(snapshot: TaskSnapshot) -> str | None:
    if snapshot.canvas_kind is None or snapshot.canvas_id is None:
        return snapshot.parent_id
    if snapshot.canvas_kind in {CANVAS_KIND_GROUP, CANVAS_KIND_CHORD}:
        return None
    if snapshot.canvas_kind == CANVAS_KIND_CHAIN:
        return snapshot.parent_id if snapshot.canvas_role == CANVAS_ROLE_TAIL else None
    return snapshot.parent_id

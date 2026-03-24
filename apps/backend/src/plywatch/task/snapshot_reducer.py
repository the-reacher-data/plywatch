"""Shared reducer that projects raw Celery task events into retained snapshots."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.constants import (
    TASK_EVENT_FAILED,
    TASK_EVENT_RECEIVED,
    TASK_EVENT_RETRIED,
    TASK_EVENT_SENT,
    TASK_EVENT_STARTED,
    TASK_EVENT_SUCCEEDED,
)
from plywatch.task.envelope import TaskEnvelope
from plywatch.task.models import (
    CanvasKind,
    CanvasRole,
    TaskKind,
    TaskSnapshot,
    TaskState,
    TaskTimelineEvent,
    build_timeline_event,
    classify_task_kind,
)


class ReducibleTaskSnapshot(Protocol):
    """Minimal mutable snapshot shape required by the shared reducer."""

    uuid: str
    name: str | None
    kind: TaskKind
    state: TaskState
    queue: str | None
    routing_key: str | None
    root_id: str | None
    parent_id: str | None
    worker_hostname: str | None
    args_preview: str | None
    kwargs_preview: str | None
    canvas_kind: CanvasKind | None
    canvas_id: str | None
    canvas_role: CanvasRole | None
    schedule_id: str | None
    schedule_name: str | None
    schedule_pattern: str | None
    scheduled_for: str | None
    retries: int
    first_seen_at: str
    last_seen_at: str
    sent_at: str | None
    received_at: str | None
    started_at: str | None
    finished_at: str | None
    result_preview: str | None
    exception_preview: str | None
    events: list[TaskTimelineEvent]


TSnapshot = TypeVar("TSnapshot", bound=ReducibleTaskSnapshot)
_MAX_TIMELINE_EVENTS = 50
_IDENTITY_FIELD_MAPPINGS = (
    ("queue_name", "queue"),
    ("routing_key", "routing_key"),
    ("root_id", "root_id"),
    ("parent_id", "parent_id"),
    ("hostname", "worker_hostname"),
    ("args_preview", "args_preview"),
    ("kwargs_preview", "kwargs_preview"),
)
_SCHEDULE_FIELD_MAPPINGS = (
    ("schedule_id", "schedule_id"),
    ("schedule_name", "schedule_name"),
    ("schedule_pattern", "schedule_pattern"),
    ("scheduled_for", "scheduled_for"),
)


class TaskSnapshotReducerRepository(Protocol[TSnapshot]):
    """Minimal persistence contract needed by the task snapshot reducer."""

    def get(self, task_id: str) -> TSnapshot | None:
        """Return one retained task snapshot by UUID."""
        ...

    def upsert(self, snapshot: TSnapshot) -> None:
        """Insert or replace one retained task snapshot."""
        ...


class TaskSnapshotReducer(Generic[TSnapshot]):
    """Apply normalized task envelopes to one snapshot repository."""

    def __init__(
        self,
        repository: TaskSnapshotReducerRepository[TSnapshot],
        *,
        snapshot_factory: Callable[[TaskEnvelope], TSnapshot],
    ) -> None:
        self._repository = repository
        self._snapshot_factory = snapshot_factory

    def apply_envelope(self, envelope: TaskEnvelope, event: RawCeleryEvent) -> TSnapshot:
        """Apply one normalized task event to the target repository."""

        current = self._repository.get(envelope.task_id)
        snapshot = current if current is not None else self._snapshot_factory(envelope)
        self._merge_identity(snapshot, envelope)
        self._merge_state(snapshot, envelope)
        snapshot.last_seen_at = envelope.captured_at
        if not snapshot.first_seen_at:
            snapshot.first_seen_at = envelope.captured_at
        snapshot.events.append(build_timeline_event(event))
        if len(snapshot.events) > _MAX_TIMELINE_EVENTS:
            del snapshot.events[:-_MAX_TIMELINE_EVENTS]
        self._repository.upsert(snapshot)
        return snapshot

    def _merge_identity(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        self._merge_name_and_kind(snapshot, envelope)
        self._merge_direct_identity_fields(snapshot, envelope)
        self._merge_canvas_metadata(snapshot, envelope)
        self._merge_schedule_metadata(snapshot, envelope)

    def _merge_name_and_kind(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        if envelope.name is not None:
            snapshot.name = envelope.name
            classified_kind = classify_task_kind(envelope.name)
            if classified_kind != "unknown" or snapshot.kind == "unknown":
                snapshot.kind = classified_kind

    def _merge_direct_identity_fields(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        for source_field, target_field in _IDENTITY_FIELD_MAPPINGS:
            self._assign_if_present(
                snapshot,
                target_field=target_field,
                value=getattr(envelope, source_field),
            )

    def _merge_canvas_metadata(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        if envelope.canvas_kind is None:
            return
        snapshot.canvas_kind = envelope.canvas_kind
        snapshot.canvas_id = envelope.canvas_id
        snapshot.canvas_role = envelope.canvas_role
        if snapshot.kind == "unknown":
            snapshot.kind = "job"

    def _merge_schedule_metadata(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        if envelope.schedule_id is None and envelope.scheduled_for is None:
            return
        for source_field, target_field in _SCHEDULE_FIELD_MAPPINGS:
            self._assign_if_present(
                snapshot,
                target_field=target_field,
                value=getattr(envelope, source_field),
            )

    @staticmethod
    def _assign_if_present(snapshot: TSnapshot, *, target_field: str, value: str | None) -> None:
        if value is not None:
            setattr(snapshot, target_field, value)

    def _merge_state(self, snapshot: TSnapshot, envelope: TaskEnvelope) -> None:
        snapshot.state = envelope.state

        for update in _TIMESTAMP_UPDATERS.get(envelope.event_type, ()):
            update(snapshot, envelope.captured_at)

        for update in _PAYLOAD_UPDATERS.get(envelope.event_type, ()):
            update(snapshot, envelope)


def build_task_snapshot(envelope: TaskEnvelope) -> TaskSnapshot:
    """Create one new task snapshot from the first observed envelope."""

    return TaskSnapshot(
        uuid=envelope.task_id,
        first_seen_at=envelope.captured_at,
        last_seen_at=envelope.captured_at,
    )


def _set_sent_at(snapshot: ReducibleTaskSnapshot, captured_at: str) -> None:
    if snapshot.sent_at is None:
        snapshot.sent_at = captured_at


def _set_received_at(snapshot: ReducibleTaskSnapshot, captured_at: str) -> None:
    if snapshot.received_at is None:
        snapshot.received_at = captured_at


def _set_started_at(snapshot: ReducibleTaskSnapshot, captured_at: str) -> None:
    if snapshot.started_at is None:
        snapshot.started_at = captured_at


def _set_finished_at(snapshot: ReducibleTaskSnapshot, captured_at: str) -> None:
    snapshot.finished_at = captured_at


def _set_result_preview(snapshot: ReducibleTaskSnapshot, envelope: TaskEnvelope) -> None:
    if envelope.result_preview is not None:
        snapshot.result_preview = envelope.result_preview


def _clear_exception_preview(snapshot: ReducibleTaskSnapshot, _envelope: TaskEnvelope) -> None:
    snapshot.exception_preview = None


def _set_exception_preview(snapshot: ReducibleTaskSnapshot, envelope: TaskEnvelope) -> None:
    if envelope.exception_preview is not None:
        snapshot.exception_preview = envelope.exception_preview


def _increment_retries(snapshot: ReducibleTaskSnapshot, _envelope: TaskEnvelope) -> None:
    snapshot.retries += 1


_TIMESTAMP_UPDATERS: dict[str, tuple] = {
    TASK_EVENT_SENT: (_set_sent_at,),
    TASK_EVENT_RECEIVED: (_set_received_at,),
    TASK_EVENT_STARTED: (_set_started_at,),
    TASK_EVENT_SUCCEEDED: (_set_finished_at,),
    TASK_EVENT_FAILED: (_set_finished_at,),
}

_PAYLOAD_UPDATERS: dict[str, tuple] = {
    TASK_EVENT_SUCCEEDED: (_set_result_preview, _clear_exception_preview),
    TASK_EVENT_FAILED: (_set_exception_preview,),
    TASK_EVENT_RETRIED: (_set_exception_preview, _increment_retries),
}

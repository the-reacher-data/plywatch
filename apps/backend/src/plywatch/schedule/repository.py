"""Dedicated retention for observed schedule-origin task runs."""

from __future__ import annotations

from typing import Protocol

import msgspec
from loom.core.repository import RepositoryBuildContext, repository_for
from loom.core.model import LoomStruct

from plywatch.shared.in_memory_projection_repository import InMemoryProjectionRepository, _parse_iso8601
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.task.models import CanvasKind, CanvasRole, TaskKind, TaskState, TaskTimelineEvent


class ScheduleRunSnapshot(LoomStruct, kw_only=True):
    """Retained snapshot for one schedule-origin task run."""

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


class ScheduleRunSnapshotRepository(Protocol):
    """Read/write repository for retained schedule-origin task runs."""

    def upsert(self, snapshot: ScheduleRunSnapshot) -> None:
        """Insert or replace one schedule run snapshot."""
        ...

    def get(self, task_id: str) -> ScheduleRunSnapshot | None:
        """Return one schedule run snapshot by UUID."""
        ...

    def list_all(self) -> list[ScheduleRunSnapshot]:
        """Return all retained schedule run snapshots."""
        ...

    def list_by_schedule_id(self, schedule_id: str) -> list[ScheduleRunSnapshot]:
        """Return all retained schedule run snapshots for one schedule."""
        ...

    def remove(self, task_id: str) -> ScheduleRunSnapshot | None:
        """Remove one schedule run snapshot by UUID."""
        ...

    def clear(self) -> int:
        """Clear all retained schedule run snapshots."""
        ...

    def count(self) -> int:
        """Return the number of retained schedule run snapshots."""
        ...


def build_schedule_run_snapshot_repository(context: RepositoryBuildContext) -> ScheduleRunSnapshotRepository:
    """Build the dedicated schedule-run repository for the current runtime."""

    if context.container is None:
        raise RuntimeError("Schedule run snapshot repository requires a DI container")
    settings = context.container.resolve(RuntimeSettings)
    return InMemoryScheduleRunSnapshotRepository(
        max_runs=settings.max_schedule_runs,
        max_age_seconds=settings.max_age_seconds,
    )


@repository_for(ScheduleRunSnapshot, builder=build_schedule_run_snapshot_repository)
class InMemoryScheduleRunSnapshotRepository(
    InMemoryProjectionRepository[str, ScheduleRunSnapshot],
    ScheduleRunSnapshotRepository,
):
    """Thread-safe bounded in-memory repository for schedule-origin runs."""

    def __init__(self, *, max_runs: int, max_age_seconds: int) -> None:
        super().__init__(
            max_age_seconds=max_age_seconds,
            get_last_seen_at=lambda item: item.last_seen_at,
        )
        self._max_runs = max_runs

    def upsert(self, snapshot: ScheduleRunSnapshot) -> None:
        with self._lock:
            self._upsert_locked(snapshot.uuid, snapshot)
            self._prune_locked()
            self._prune_by_count_locked()

    def get(self, task_id: str) -> ScheduleRunSnapshot | None:
        with self._lock:
            return self._get_locked(task_id)

    def list_all(self) -> list[ScheduleRunSnapshot]:
        with self._lock:
            items = self._list_locked()
        items.sort(key=lambda item: (_parse_iso8601(item.last_seen_at), item.uuid), reverse=True)
        return items

    def list_by_schedule_id(self, schedule_id: str) -> list[ScheduleRunSnapshot]:
        with self._lock:
            items = [item for item in self._list_locked() if item.schedule_id == schedule_id]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def remove(self, task_id: str) -> ScheduleRunSnapshot | None:
        with self._lock:
            return self._items.pop(task_id, None)

    def clear(self) -> int:
        with self._lock:
            removed = len(self._items)
            self._items.clear()
        return removed

    def _prune_by_count_locked(self) -> None:
        if self._max_runs <= 0 or len(self._items) <= self._max_runs:
            return
        sorted_items = sorted(
            self._items.items(),
            key=lambda item: _parse_iso8601(item[1].last_seen_at),
        )
        overflow = len(self._items) - self._max_runs
        for task_id, _snapshot in sorted_items[:overflow]:
            self._items.pop(task_id, None)

"""Separate retention for completed task snapshots."""

from __future__ import annotations

from typing import Protocol

from plywatch.shared.in_memory_projection_repository import (
    InMemoryProjectionRepository,
    _parse_iso8601,
)
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.task.models import TaskSnapshot


class CompletedTaskSnapshotRepository(Protocol):
    """Read/write repository for retained terminal task snapshots."""

    def upsert(self, snapshot: TaskSnapshot) -> None: ...
    def get(self, task_id: str) -> TaskSnapshot | None: ...
    def list_all(self) -> list[TaskSnapshot]: ...
    def list_by_root(self, root_id: str) -> list[TaskSnapshot]: ...
    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]: ...
    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]: ...
    def remove(self, task_id: str) -> TaskSnapshot | None: ...
    def clear(self) -> int: ...


class InMemoryCompletedTaskSnapshotRepository(
    InMemoryProjectionRepository[str, TaskSnapshot],
    CompletedTaskSnapshotRepository,
):
    """Thread-safe in-memory repository for completed task retention."""

    def __init__(self, *, max_tasks: int, max_age_seconds: int) -> None:
        super().__init__(
            max_age_seconds=max_age_seconds,
            get_last_seen_at=lambda item: item.last_seen_at,
        )
        self._max_tasks = max_tasks

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> InMemoryCompletedTaskSnapshotRepository:
        return cls(
            max_tasks=settings.max_completed_tasks,
            max_age_seconds=settings.max_age_seconds,
        )

    def upsert(self, snapshot: TaskSnapshot) -> None:
        with self._lock:
            self._upsert_locked(snapshot.uuid, snapshot)
            self._prune_locked()
            self._prune_by_count_locked()

    def get(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            return self._get_locked(task_id)

    def list_all(self) -> list[TaskSnapshot]:
        with self._lock:
            items = self._list_locked()
        items.sort(key=lambda item: (_parse_iso8601(item.last_seen_at), item.uuid), reverse=True)
        return items

    def list_by_root(self, root_id: str) -> list[TaskSnapshot]:
        with self._lock:
            items = [
                item
                for item in self._list_locked()
                if item.uuid == root_id or item.root_id == root_id
            ]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]:
        with self._lock:
            items = [item for item in self._list_locked() if item.canvas_id == canvas_id]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]:
        with self._lock:
            items = [item for item in self._list_locked() if item.schedule_id == schedule_id]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def remove(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            return self._items.pop(task_id, None)

    def clear(self) -> int:
        with self._lock:
            removed = len(self._items)
            self._items.clear()
        return removed

    def _prune_by_count_locked(self) -> None:
        if self._max_tasks <= 0 or len(self._items) <= self._max_tasks:
            return
        sorted_items = sorted(
            self._items.items(),
            key=lambda item: _parse_iso8601(item[1].last_seen_at),
        )
        overflow = len(self._items) - self._max_tasks
        for task_id, _snapshot in sorted_items[:overflow]:
            self._items.pop(task_id, None)

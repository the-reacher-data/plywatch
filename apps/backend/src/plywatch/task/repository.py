"""Task snapshot repository contracts and in-memory implementation."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Protocol

from loom.core.repository import RepositoryBuildContext, repository_for
from loom.core.repository.abc.query import FilterGroup, FilterOp, FilterSpec, QuerySpec
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.shared.in_memory_projection_repository import (
    InMemoryProjectionRepository,
    _parse_iso8601,
)
from plywatch.task.models import TaskSnapshot


class TaskSnapshotRepository(Protocol):
    """Read/write repository for consolidated task snapshots."""

    def upsert(self, snapshot: TaskSnapshot) -> None:
        """Insert or replace one task snapshot."""

    def get(self, task_id: str) -> TaskSnapshot | None:
        """Return one task snapshot by UUID."""

    def list_recent(self, limit: int) -> list[TaskSnapshot]:
        """Return recent task snapshots ordered by latest activity."""

    def list_all(self, *, query: QuerySpec | None = None) -> list[TaskSnapshot]:
        """Return all retained snapshots optionally filtered by the query."""

    def list_recent_cursor(
        self,
        *,
        query: QuerySpec,
    ) -> tuple[list[TaskSnapshot], str | None, bool]:
        """Return a bounded cursor page ordered by latest activity."""

    def list_by_root(self, root_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots belonging to one execution root."""

    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots stamped with one canvas identifier."""

    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots observed from one schedule."""

    def remove(self, task_id: str) -> TaskSnapshot | None:
        """Remove one task snapshot by UUID and return it if present."""

    def clear(self) -> int:
        """Remove all retained task snapshots and return the removed count."""

    def count(self) -> int:
        """Return the number of tracked task snapshots."""

    def max_tasks(self) -> int:
        """Return the configured maximum number of retained task snapshots."""

    def max_age_seconds(self) -> int:
        """Return the configured maximum task retention age in seconds."""


def build_task_snapshot_repository(context: RepositoryBuildContext) -> TaskSnapshotRepository:
    """Build the task snapshot repository for the current app runtime."""
    settings = context.container.resolve(RuntimeSettings)
    return InMemoryTaskSnapshotRepository(
        max_tasks=settings.max_tasks,
        max_age_seconds=settings.max_age_seconds,
    )


@repository_for(TaskSnapshot, builder=build_task_snapshot_repository)
class InMemoryTaskSnapshotRepository(
    InMemoryProjectionRepository[str, TaskSnapshot],
    TaskSnapshotRepository,
):
    """Thread-safe bounded in-memory repository for task snapshots."""

    def __init__(self, *, max_tasks: int, max_age_seconds: int) -> None:
        super().__init__(
            max_age_seconds=max_age_seconds,
            get_last_seen_at=lambda item: item.last_seen_at,
        )
        self._max_tasks = max_tasks

    def upsert(self, snapshot: TaskSnapshot) -> None:
        """Insert or replace one task snapshot."""
        with self._lock:
            self._upsert_locked(snapshot.uuid, snapshot)
            self._prune_locked()
            self._prune_by_count_locked()

    def get(self, task_id: str) -> TaskSnapshot | None:
        """Return one task snapshot by UUID."""
        with self._lock:
            return self._get_locked(task_id)

    def list_recent(self, limit: int) -> list[TaskSnapshot]:
        """Return recent task snapshots ordered by latest activity."""
        with self._lock:
            items = self._list_locked()
        items.sort(key=lambda item: item.last_seen_at, reverse=True)
        return items[:limit]

    def list_all(self, *, query: QuerySpec | None = None) -> list[TaskSnapshot]:
        """Return all retained task snapshots optionally filtered by query."""
        with self._lock:
            items = self._list_locked()
        if query is not None:
            items = _apply_query_filters(items, query.filters)
        items.sort(key=lambda item: (_parse_iso8601(item.last_seen_at), item.uuid), reverse=True)
        return items

    def list_recent_cursor(
        self,
        *,
        query: QuerySpec,
    ) -> tuple[list[TaskSnapshot], str | None, bool]:
        """Return a cursor page ordered by ``last_seen_at DESC, uuid DESC``."""
        with self._lock:
            items = self._list_locked()

        items = _apply_query_filters(items, query.filters)
        items.sort(
            key=lambda item: (_parse_iso8601(item.last_seen_at), item.uuid),
            reverse=True,
        )
        anchor = _decode_cursor(query.cursor) if query.cursor is not None else None
        if anchor is not None:
            items = [
                item
                for item in items
                if (_parse_iso8601(item.last_seen_at), item.uuid) < anchor
            ]

        page_items = items[:query.limit]
        has_next = len(items) > query.limit
        next_cursor = None
        if has_next and page_items:
            last_item = page_items[-1]
            next_cursor = _encode_cursor(last_item.last_seen_at, last_item.uuid)
        return page_items, next_cursor, has_next

    def list_by_root(self, root_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots belonging to one execution root."""
        with self._lock:
            items = [
                item
                for item in self._list_locked()
                if item.uuid == root_id or item.root_id == root_id
            ]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots stamped with one canvas identifier."""
        with self._lock:
            items = [
                item
                for item in self._list_locked()
                if item.canvas_id == canvas_id
            ]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]:
        """Return all tracked snapshots observed from one schedule."""
        with self._lock:
            items = [
                item
                for item in self._list_locked()
                if item.schedule_id == schedule_id
            ]
        items.sort(key=lambda item: (_parse_iso8601(item.first_seen_at), item.uuid))
        return items

    def remove(self, task_id: str) -> TaskSnapshot | None:
        """Remove one task snapshot by UUID and return it if present."""
        with self._lock:
            return self._items.pop(task_id, None)

    def clear(self) -> int:
        """Remove all retained task snapshots and return the removed count."""
        with self._lock:
            removed = len(self._items)
            self._items.clear()
        return removed

    def max_tasks(self) -> int:
        """Return the configured maximum number of retained task snapshots."""
        return self._max_tasks

    def _prune_by_count_locked(self) -> None:
        if self._max_tasks <= 0:
            return
        if len(self._items) <= self._max_tasks:
            return
        sorted_items = sorted(
            self._items.items(),
            key=lambda item: _parse_iso8601(item[1].last_seen_at),
        )
        overflow = len(self._items) - self._max_tasks
        for task_id, _snapshot in sorted_items[:overflow]:
            self._items.pop(task_id, None)


def _encode_cursor(last_seen_at: str, task_id: str) -> str:
    payload = {"last_seen_at": last_seen_at, "uuid": task_id}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    return encoded.decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
    return _parse_iso8601(str(payload["last_seen_at"])), str(payload["uuid"])


_SUPPORTED_FILTER_FIELDS = frozenset(
    {
        "queue",
        "worker_hostname",
        "state",
        "kind",
        "canvas_kind",
        "canvas_id",
        "root_id",
    }
)


def _apply_query_filters(
    items: list[TaskSnapshot],
    filters: FilterGroup | None,
) -> list[TaskSnapshot]:
    if filters is None or not filters.filters:
        return items

    if filters.op != "AND":
        raise ValueError("TaskSnapshotRepository only supports AND filter groups.")

    filtered = items
    for filter_spec in filters.filters:
        filtered = _apply_filter(filtered, filter_spec)
    return filtered


def _apply_filter(items: list[TaskSnapshot], filter_spec: FilterSpec) -> list[TaskSnapshot]:
    field_name = filter_spec.field
    if field_name not in _SUPPORTED_FILTER_FIELDS:
        raise ValueError(f"Unsupported task filter field: {field_name!r}")

    if filter_spec.op not in {FilterOp.EQ, FilterOp.IN}:
        raise ValueError(f"Unsupported task filter op: {filter_spec.op.value!r}")

    if filter_spec.op is FilterOp.EQ:
        return [
            item
            for item in items
            if getattr(item, field_name) == filter_spec.value
        ]

    values = (
        tuple(filter_spec.value)
        if isinstance(filter_spec.value, (list, tuple, set))
        else ()
    )
    return [
        item
        for item in items
        if getattr(item, field_name) in values
    ]

"""Unified task read model over live and completed retention."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Protocol

from loom.core.repository.abc.query import QuerySpec

from plywatch.task.completed_repository import CompletedTaskSnapshotRepository
from plywatch.task.models import TaskSnapshot
from plywatch.task.repository import TaskSnapshotRepository, _apply_query_filters


class TaskReadRepository(Protocol):
    """Read retained task data across live and completed stores."""

    def get(self, task_id: str) -> TaskSnapshot | None: ...
    def list_all(self, *, query: QuerySpec | None = None) -> list[TaskSnapshot]: ...
    def list_recent_cursor(self, *, query: QuerySpec) -> tuple[list[TaskSnapshot], str | None, bool]: ...
    def list_by_root(self, root_id: str) -> list[TaskSnapshot]: ...
    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]: ...
    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]: ...


class UnifiedTaskReadRepository(TaskReadRepository):
    """Merge live and completed snapshots while preferring the live version."""

    def __init__(
        self,
        *,
        live_repository: TaskSnapshotRepository,
        completed_repository: CompletedTaskSnapshotRepository,
    ) -> None:
        self._live_repository = live_repository
        self._completed_repository = completed_repository

    def get(self, task_id: str) -> TaskSnapshot | None:
        return self._live_repository.get(task_id) or self._completed_repository.get(task_id)

    def list_all(self, *, query: QuerySpec | None = None) -> list[TaskSnapshot]:
        live_items = self._live_repository.list_all(query=query)
        completed_items = self._completed_repository.list_all()
        return _merge_snapshots(live_items, completed_items, query=query)

    def list_recent_cursor(self, *, query: QuerySpec) -> tuple[list[TaskSnapshot], str | None, bool]:
        items = self.list_all(query=query)
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
        return _merge_snapshots(
            self._live_repository.list_by_root(root_id),
            self._completed_repository.list_by_root(root_id),
        )

    def list_by_canvas_id(self, canvas_id: str) -> list[TaskSnapshot]:
        return _merge_snapshots(
            self._live_repository.list_by_canvas_id(canvas_id),
            self._completed_repository.list_by_canvas_id(canvas_id),
        )

    def list_by_schedule_id(self, schedule_id: str) -> list[TaskSnapshot]:
        return _merge_snapshots(
            self._live_repository.list_by_schedule_id(schedule_id),
            self._completed_repository.list_by_schedule_id(schedule_id),
        )


def _merge_snapshots(
    live_items: list[TaskSnapshot],
    completed_items: list[TaskSnapshot],
    *,
    query: QuerySpec | None = None,
) -> list[TaskSnapshot]:
    merged: dict[str, TaskSnapshot] = {item.uuid: item for item in completed_items}
    for item in live_items:
        merged[item.uuid] = item
    items = list(merged.values())
    if query is not None and query.filters is not None:
        items = _apply_query_filters(items, query.filters)
    items.sort(key=lambda item: (_parse_iso8601(item.last_seen_at), item.uuid), reverse=True)
    return items


def _encode_cursor(last_seen_at: str, task_id: str) -> str:
    payload = {"last_seen_at": last_seen_at, "uuid": task_id}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    return encoded.decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
    return _parse_iso8601(str(payload["last_seen_at"])), str(payload["uuid"])


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value)

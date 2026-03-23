"""Administrative monitor actions over retained in-memory projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.schedule.repository import ScheduleRunSnapshotRepository
from plywatch.shared.raw_events import RawEventStore
from plywatch.task.completed_repository import CompletedTaskSnapshotRepository
from plywatch.task.models import CanvasKind, TaskSnapshot
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.worker.repository import WorkerSnapshotRepository


@dataclass(frozen=True)
class MonitorResetResult:
    removed_tasks: int
    removed_workers: int
    removed_queues: int
    removed_raw_events: int


@dataclass(frozen=True)
class MonitorRemovalResult:
    removed_count: int
    removed_ids: tuple[str, ...]


class _TaskFamilySnapshot(Protocol):
    """Minimal task snapshot shape needed to resolve one retained family."""

    uuid: str
    root_id: str | None
    canvas_id: str | None
    canvas_kind: CanvasKind | None


class MonitorAdminService:
    """Coordinate administrative cleanup of retained monitor data."""

    def __init__(
        self,
        *,
        task_repository: TaskSnapshotRepository,
        completed_task_repository: CompletedTaskSnapshotRepository,
        worker_repository: WorkerSnapshotRepository,
        queue_repository: QueueSnapshotRepository,
        schedule_repository: ScheduleRunSnapshotRepository,
        raw_event_store: RawEventStore,
    ) -> None:
        self._task_repository = task_repository
        self._completed_task_repository = completed_task_repository
        self._worker_repository = worker_repository
        self._queue_repository = queue_repository
        self._schedule_repository = schedule_repository
        self._raw_event_store = raw_event_store

    def reset(self) -> MonitorResetResult:
        """Clear retained monitor projections without touching historical totals."""

        self._schedule_repository.clear()
        return MonitorResetResult(
            removed_tasks=self._task_repository.clear() + self._completed_task_repository.clear(),
            removed_workers=self._worker_repository.clear(),
            removed_queues=self._queue_repository.clear(),
            removed_raw_events=self._raw_event_store.clear(),
        )

    def remove_task_families(self, task_ids: list[str]) -> MonitorRemovalResult:
        """Remove logical task families from monitor retention."""

        removed_ids: list[str] = []
        visited: set[str] = set()
        for task_id in task_ids:
            snapshot = self._task_repository.get(task_id) or self._completed_task_repository.get(task_id)
            if snapshot is None:
                continue
            for family_task_id in self._family_task_ids(snapshot):
                if family_task_id in visited:
                    continue
                visited.add(family_task_id)
                if self._remove_task_everywhere(family_task_id):
                    removed_ids.append(family_task_id)
        return MonitorRemovalResult(removed_count=len(removed_ids), removed_ids=tuple(removed_ids))

    def remove_schedules(self, schedule_ids: list[str]) -> MonitorRemovalResult:
        """Remove all retained runs belonging to the selected schedules."""

        removed_ids: list[str] = []
        visited: set[str] = set()
        for schedule_id in schedule_ids:
            for item in self._schedule_repository.list_by_schedule_id(schedule_id):
                if item.uuid in visited:
                    continue
                visited.add(item.uuid)
                self._remove_task_everywhere(item.uuid)
                removed_ids.append(item.uuid)
        return MonitorRemovalResult(removed_count=len(removed_ids), removed_ids=tuple(removed_ids))

    def _family_task_ids(self, snapshot: _TaskFamilySnapshot) -> tuple[str, ...]:
        live_items, completed_items = self._family_items(snapshot)
        family_items = {item.uuid: item for item in completed_items}
        family_items.update({item.uuid: item for item in live_items})
        return tuple(family_items)

    def _family_items(
        self,
        snapshot: _TaskFamilySnapshot,
    ) -> tuple[list[TaskSnapshot], list[TaskSnapshot]]:
        if snapshot.canvas_id is not None and snapshot.canvas_kind is not None:
            return (
                self._task_repository.list_by_canvas_id(snapshot.canvas_id),
                self._completed_task_repository.list_by_canvas_id(snapshot.canvas_id),
            )

        root_id = snapshot.root_id or snapshot.uuid
        return (
            self._task_repository.list_by_root(root_id),
            self._completed_task_repository.list_by_root(root_id),
        )

    def _remove_task_everywhere(self, task_id: str) -> bool:
        self._queue_repository.remove_task(task_id)
        self._schedule_repository.remove(task_id)
        removed_live = self._task_repository.remove(task_id)
        removed_completed = self._completed_task_repository.remove(task_id)
        return removed_live is not None or removed_completed is not None

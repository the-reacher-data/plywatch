"""Task projection reducer fed by raw Celery events."""

from __future__ import annotations

from copy import deepcopy

from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.completed_repository import CompletedTaskSnapshotRepository
from plywatch.task.constants import COMPLETED_TASK_STATES, TASK_EVENTS
from plywatch.task.envelope import from_raw_task_event
from plywatch.task.models import TaskSnapshot
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.task.snapshot_reducer import TaskSnapshotReducer, build_task_snapshot


class TaskProjector:
    """Build consolidated task snapshots from the raw Celery event stream."""

    handled_event_types = TASK_EVENTS

    def __init__(
        self,
        repository: TaskSnapshotRepository,
        completed_repository: CompletedTaskSnapshotRepository | None = None,
    ) -> None:
        self._repository = repository
        self._completed_repository = completed_repository
        self._reducer = TaskSnapshotReducer(
            repository,
            snapshot_factory=build_task_snapshot,
        )

    def apply(self, event: RawCeleryEvent) -> None:
        """Update the task projection when one task lifecycle event arrives."""
        envelope = from_raw_task_event(event)
        if envelope is None:
            return
        snapshot = self._reducer.apply_envelope(envelope, event)
        self._link_parent_child(snapshot)
        self._mirror_completed(snapshot)

    def _link_parent_child(self, snapshot: TaskSnapshot) -> None:
        if snapshot.parent_id is None or snapshot.parent_id == snapshot.uuid:
            return
        parent = self._repository.get(snapshot.parent_id)
        if parent is None:
            return
        if snapshot.uuid not in parent.children_ids:
            parent.children_ids.append(snapshot.uuid)
            parent.last_seen_at = max(parent.last_seen_at, snapshot.last_seen_at)
            self._repository.upsert(parent)

    def _mirror_completed(self, snapshot: TaskSnapshot) -> None:
        if self._completed_repository is None:
            return
        if snapshot.state not in COMPLETED_TASK_STATES:
            return
        self._completed_repository.upsert(deepcopy(snapshot))

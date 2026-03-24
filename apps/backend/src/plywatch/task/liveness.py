"""Task liveness reconciliation against the real worker state."""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from loom.core.model import LoomStruct

from plywatch.task.completed_repository import CompletedTaskSnapshotRepository
from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.task.constants import TASK_STATE_LOST
from plywatch.task.models import TaskSnapshot, TaskTimelineEvent
from plywatch.task.policies import current_utc, is_lost_candidate
from plywatch.task.repository import TaskSnapshotRepository


class TaskExecutionPresenceSnapshot(Protocol):
    """Read-only view of live task presence in workers."""

    def contains(self, *, worker_hostname: str, task_id: str) -> bool:
        """Return whether the worker still reports the task in flight."""
        ...


class TaskExecutionPresenceGateway(Protocol):
    """Bridge to the underlying execution system for liveness checks."""

    def capture(self) -> TaskExecutionPresenceSnapshot:
        """Return the current live-task presence snapshot."""
        ...


class LostTaskReconciliationResult(LoomStruct, frozen=True, kw_only=True):
    """Outcome of one liveness reconciliation pass."""

    updated_task_ids: tuple[str, ...]


class TaskLivenessReconciler:
    """Mark orphaned running tasks as lost when workers no longer report them."""

    def __init__(
        self,
        *,
        task_repository: TaskSnapshotRepository,
        completed_task_repository: CompletedTaskSnapshotRepository,
        queue_repository: QueueSnapshotRepository,
        presence_gateway: TaskExecutionPresenceGateway,
        lost_after_seconds: int,
    ) -> None:
        self._task_repository = task_repository
        self._completed_task_repository = completed_task_repository
        self._queue_repository = queue_repository
        self._presence_gateway = presence_gateway
        self._lost_after_seconds = lost_after_seconds

    def reconcile(self) -> LostTaskReconciliationResult:
        """Return all tasks that transitioned to ``lost`` in this pass."""

        reference_at = current_utc()
        candidates = [
            snapshot
            for snapshot in self._task_repository.list_all()
            if is_lost_candidate(
                snapshot,
                reference_at=reference_at,
                lost_after_seconds=self._lost_after_seconds,
            )
        ]
        if not candidates:
            return LostTaskReconciliationResult(updated_task_ids=())

        presence = self._presence_gateway.capture()
        reconciled_ids: list[str] = []
        captured_at = reference_at.isoformat()
        for snapshot in candidates:
            worker_hostname = snapshot.worker_hostname
            if worker_hostname is None:
                continue
            if presence.contains(worker_hostname=worker_hostname, task_id=snapshot.uuid):
                continue
            self._mark_lost(snapshot, captured_at=captured_at)
            reconciled_ids.append(snapshot.uuid)

        return LostTaskReconciliationResult(updated_task_ids=tuple(reconciled_ids))

    def _mark_lost(self, snapshot: TaskSnapshot, *, captured_at: str) -> None:
        snapshot.state = TASK_STATE_LOST
        snapshot.finished_at = snapshot.finished_at or captured_at
        snapshot.last_seen_at = captured_at
        snapshot.events.append(
            TaskTimelineEvent(
                captured_at=captured_at,
                event_type="task-lost",
                payload={
                    "reason": "worker_no_longer_reports_task",
                    "workerHostname": snapshot.worker_hostname,
                },
            )
        )
        self._task_repository.upsert(snapshot)
        self._completed_task_repository.upsert(deepcopy(snapshot))
        self._queue_repository.apply_task_event(
            task_id=snapshot.uuid,
            queue_name=snapshot.queue,
            routing_key=snapshot.routing_key,
            state=TASK_STATE_LOST,
            captured_at=captured_at,
            scheduled_for=snapshot.scheduled_for,
        )

from __future__ import annotations

from datetime import UTC, datetime

from plywatch.queue.repository import InMemoryQueueSnapshotRepository
from plywatch.task.completed_repository import InMemoryCompletedTaskSnapshotRepository
from plywatch.task.liveness import (
    TaskExecutionPresenceGateway,
    TaskExecutionPresenceSnapshot,
    TaskLivenessReconciler,
)
from plywatch.task.models import TaskSnapshot
from plywatch.task.repository import InMemoryTaskSnapshotRepository


class _PresenceSnapshot(TaskExecutionPresenceSnapshot):
    def __init__(self, present: set[tuple[str, str]]) -> None:
        self._present = present

    def contains(self, *, worker_hostname: str, task_id: str) -> bool:
        return (worker_hostname, task_id) in self._present


class _PresenceGateway(TaskExecutionPresenceGateway):
    def __init__(self, present: set[tuple[str, str]]) -> None:
        self._present = present

    def capture(self) -> TaskExecutionPresenceSnapshot:
        return _PresenceSnapshot(self._present)


def _iso_at(hour: int, minute: int, second: int = 0) -> str:
    return datetime(2026, 3, 19, hour, minute, second, tzinfo=UTC).isoformat()


def test_reconciler_marks_old_started_tasks_as_lost_and_decrements_queue_counts(monkeypatch) -> None:
    task_repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=604_800)
    completed_task_repository = InMemoryCompletedTaskSnapshotRepository(max_tasks=100, max_age_seconds=604_800)
    queue_repository = InMemoryQueueSnapshotRepository(max_age_seconds=604_800)

    snapshot = TaskSnapshot(
        uuid="task-lost-1",
        name="loom.job.HelloSlowJob",
        kind="job",
        state="started",
        queue="slow",
        routing_key="slow",
        root_id="task-lost-1",
        first_seen_at=_iso_at(13, 0),
        last_seen_at=_iso_at(13, 5),
        sent_at=_iso_at(13, 0),
        received_at=_iso_at(13, 5),
        started_at=_iso_at(13, 5),
        worker_hostname="slow@worker-1",
    )
    task_repository.upsert(snapshot)
    queue_repository.apply_task_event(
        task_id="task-lost-1",
        queue_name="slow",
        routing_key="slow",
        state="started",
        captured_at=_iso_at(13, 5),
    )

    monkeypatch.setattr("plywatch.task.liveness.current_utc", lambda: datetime(2026, 3, 19, 14, 0, tzinfo=UTC))
    reconciler = TaskLivenessReconciler(
        task_repository=task_repository,
        completed_task_repository=completed_task_repository,
        queue_repository=queue_repository,
        presence_gateway=_PresenceGateway(set()),
        lost_after_seconds=1800,
    )

    result = reconciler.reconcile()

    assert result.updated_task_ids == ("task-lost-1",)
    updated = task_repository.get("task-lost-1")
    assert updated is not None
    assert updated.state == "lost"
    assert updated.finished_at == _iso_at(14, 0)
    assert updated.events[-1].event_type == "task-lost"
    archived = completed_task_repository.get("task-lost-1")
    assert archived is not None
    assert archived.state == "lost"

    queue = queue_repository.list_recent(10)
    assert len(queue) == 1
    assert queue[0].name == "slow"
    assert queue[0].total_tasks == 0
    assert queue[0].failed_count == 0
    assert queue[0].historical_failed_count == 1


def test_reconciler_keeps_present_tasks_running(monkeypatch) -> None:
    task_repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=604_800)
    completed_task_repository = InMemoryCompletedTaskSnapshotRepository(max_tasks=100, max_age_seconds=604_800)
    queue_repository = InMemoryQueueSnapshotRepository(max_age_seconds=604_800)

    snapshot = TaskSnapshot(
        uuid="task-running-1",
        name="loom.job.HelloSlowJob",
        kind="job",
        state="started",
        queue="slow",
        routing_key="slow",
        root_id="task-running-1",
        first_seen_at=_iso_at(13, 0),
        last_seen_at=_iso_at(13, 5),
        sent_at=_iso_at(13, 0),
        received_at=_iso_at(13, 5),
        started_at=_iso_at(13, 5),
        worker_hostname="slow@worker-1",
    )
    task_repository.upsert(snapshot)

    monkeypatch.setattr("plywatch.task.liveness.current_utc", lambda: datetime(2026, 3, 19, 14, 0, tzinfo=UTC))
    reconciler = TaskLivenessReconciler(
        task_repository=task_repository,
        completed_task_repository=completed_task_repository,
        queue_repository=queue_repository,
        presence_gateway=_PresenceGateway({("slow@worker-1", "task-running-1")}),
        lost_after_seconds=1800,
    )

    result = reconciler.reconcile()

    assert result.updated_task_ids == ()
    updated = task_repository.get("task-running-1")
    assert updated is not None
    assert updated.state == "started"

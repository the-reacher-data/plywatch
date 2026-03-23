"""Queue snapshot repository contracts and in-memory implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from loom.core.repository import RepositoryBuildContext, repository_for
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.shared.in_memory_projection_repository import (
    InMemoryProjectionRepository,
    _parse_iso8601,
)
from plywatch.task.models import TaskState
from plywatch.task.policies import is_future_live_eta

from plywatch.queue.models import QueueSnapshot


class QueueSnapshotRepository(Protocol):
    """Read/write repository for consolidated queue snapshots."""

    def apply_task_event(
        self,
        *,
        task_id: str,
        queue_name: str | None,
        routing_key: str | None,
        state: TaskState | None,
        captured_at: str,
        scheduled_for: str | None = None,
    ) -> None:
        """Apply one observed task transition to the queue projection."""

    def list_recent(self, limit: int) -> list[QueueSnapshot]:
        """Return queues ordered by latest activity."""
        ...

    def count(self) -> int:
        """Return the number of tracked queue snapshots."""
        ...

    def remove_task(self, task_id: str) -> bool:
        """Remove one tracked task from queue live counts if present."""
        ...

    def clear(self) -> int:
        """Remove all retained queue snapshots and live task entries."""
        ...


@dataclass
class _TrackedTask:
    task_id: str
    queue_name: str
    routing_key: str | None
    state: TaskState
    last_seen_at: str
    sent_at: str | None = None
    latest_received_at: str | None = None
    latest_started_at: str | None = None
    scheduled_for: str | None = None
    counted: bool = True
    queue_wait_recorded: bool = False
    start_delay_recorded: bool = False
    run_duration_recorded: bool = False
    end_to_end_recorded: bool = False


def build_queue_snapshot_repository(context: RepositoryBuildContext) -> QueueSnapshotRepository:
    """Build the queue snapshot repository for the current app runtime."""
    if context.container is None:
        raise RuntimeError("Queue snapshot repository requires a DI container")
    settings = context.container.resolve(RuntimeSettings)
    return InMemoryQueueSnapshotRepository(max_age_seconds=settings.max_age_seconds)


@repository_for(QueueSnapshot, builder=build_queue_snapshot_repository)
class InMemoryQueueSnapshotRepository(
    InMemoryProjectionRepository[str, QueueSnapshot],
    QueueSnapshotRepository,
):
    """Thread-safe in-memory repository for queue snapshots."""

    def __init__(self, *, max_age_seconds: int) -> None:
        super().__init__(
            max_age_seconds=max_age_seconds,
            get_last_seen_at=lambda item: item.last_seen_at,
        )
        self._tasks: dict[str, _TrackedTask] = {}

    def apply_task_event(
        self,
        *,
        task_id: str,
        queue_name: str | None,
        routing_key: str | None,
        state: TaskState | None,
        captured_at: str,
        scheduled_for: str | None = None,
    ) -> None:
        """Apply one observed task transition to the queue projection."""
        if state is None:
            return

        with self._lock:
            previous = self._tasks.get(task_id)
            resolved_queue = queue_name or (previous.queue_name if previous is not None else None)
            if resolved_queue is None:
                return

            target = self._items.get(resolved_queue)
            if target is None:
                target = QueueSnapshot(
                    name=resolved_queue,
                    first_seen_at=captured_at,
                    last_seen_at=captured_at,
                )
                self._upsert_locked(resolved_queue, target)

            if previous is None:
                target.historical_total_seen += 1
            if state == "retrying":
                target.historical_retried_count += 1
            if state == "succeeded" and (previous is None or previous.state != "succeeded"):
                target.historical_succeeded_count += 1
            if state in {"failed", "lost"} and (
                previous is None or previous.state not in {"failed", "lost"}
            ):
                target.historical_failed_count += 1

            if previous is not None and previous.counted:
                self._decrement(previous)

            tracked = _TrackedTask(
                task_id=task_id,
                queue_name=resolved_queue,
                routing_key=routing_key or (previous.routing_key if previous is not None else None),
                state=state,
                last_seen_at=captured_at,
                sent_at=previous.sent_at if previous is not None else None,
                latest_received_at=previous.latest_received_at if previous is not None else None,
                latest_started_at=previous.latest_started_at if previous is not None else None,
                scheduled_for=scheduled_for or (previous.scheduled_for if previous is not None else None),
                counted=previous.counted if previous is not None else True,
                queue_wait_recorded=previous.queue_wait_recorded if previous is not None else False,
                start_delay_recorded=previous.start_delay_recorded if previous is not None else False,
                run_duration_recorded=previous.run_duration_recorded if previous is not None else False,
                end_to_end_recorded=previous.end_to_end_recorded if previous is not None else False,
            )
            self._update_timing_markers(tracked, state=state, captured_at=captured_at)
            self._record_timing_metrics(target, tracked, state=state, captured_at=captured_at)
            tracked.counted = _should_count_state(tracked, state=state, captured_at=captured_at)
            self._tasks[task_id] = tracked
            if tracked.counted:
                self._increment(tracked, target, captured_at)
            self._upsert_locked(resolved_queue, target)
            self._prune_locked()

    def list_recent(self, limit: int) -> list[QueueSnapshot]:
        """Return queues ordered by latest activity."""
        with self._lock:
            self._prune_locked()
            items = [snapshot for snapshot in self._list_locked() if _is_visible_snapshot(snapshot)]
        items.sort(key=lambda item: (item.last_seen_at, item.name), reverse=True)
        return items[:limit]

    def count(self) -> int:
        """Return the number of tracked queue snapshots."""
        with self._lock:
            self._prune_locked()
            return sum(1 for snapshot in self._items.values() if _is_visible_snapshot(snapshot))

    def remove_task(self, task_id: str) -> bool:
        """Remove one tracked task from queue live counts if present."""
        with self._lock:
            tracked = self._tasks.pop(task_id, None)
            if tracked is None:
                return False
            if tracked.counted:
                self._decrement(tracked)
            return True

    def clear(self) -> int:
        """Remove all retained queue snapshots and live task entries."""
        with self._lock:
            removed = len(self._items)
            self._items.clear()
            self._tasks.clear()
        return removed

    def _increment(self, tracked: _TrackedTask, snapshot: QueueSnapshot, captured_at: str) -> None:
        snapshot.last_seen_at = captured_at
        if not snapshot.first_seen_at:
            snapshot.first_seen_at = captured_at
        snapshot.total_tasks += 1
        if tracked.routing_key and tracked.routing_key not in snapshot.routing_keys:
            snapshot.routing_keys.append(tracked.routing_key)
        self._bump_state(snapshot, tracked.state, delta=1)

    def _decrement(self, tracked: _TrackedTask) -> None:
        snapshot = self._get_locked(tracked.queue_name)
        if snapshot is None:
            return
        snapshot.total_tasks = max(0, snapshot.total_tasks - 1)
        self._bump_state(snapshot, tracked.state, delta=-1)

    def _prune_locked(self) -> None:
        if self.max_age_seconds() <= 0:
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=self.max_age_seconds())
        expired = [
            task_id
            for task_id, tracked in self._tasks.items()
            if _parse_iso8601(tracked.last_seen_at) < cutoff
        ]
        for task_id in expired:
            tracked = self._tasks.pop(task_id, None)
            if tracked is not None:
                self._decrement(tracked)

    def _bump_state(self, snapshot: QueueSnapshot, state: TaskState, *, delta: int) -> None:
        if state == "sent":
            snapshot.sent_count = max(0, snapshot.sent_count + delta)
            return
        if state in {"received", "started"}:
            snapshot.active_count = max(0, snapshot.active_count + delta)
            return
        if state == "retrying":
            snapshot.retrying_count = max(0, snapshot.retrying_count + delta)
            return
        if state == "succeeded":
            snapshot.succeeded_count = max(0, snapshot.succeeded_count + delta)
            return
        if state in {"failed", "lost"}:
            snapshot.failed_count = max(0, snapshot.failed_count + delta)
            return

    def _update_timing_markers(
        self,
        tracked: _TrackedTask,
        *,
        state: TaskState,
        captured_at: str,
    ) -> None:
        if state == "sent" and tracked.sent_at is None:
            tracked.sent_at = captured_at
            return
        if state == "received":
            tracked.latest_received_at = captured_at
            return
        if state == "started":
            tracked.latest_started_at = captured_at

    def _record_timing_metrics(
        self,
        snapshot: QueueSnapshot,
        tracked: _TrackedTask,
        *,
        state: TaskState,
        captured_at: str,
    ) -> None:
        if state == "received" and not tracked.queue_wait_recorded:
            queue_wait_ms = _duration_ms(tracked.sent_at, captured_at)
            if queue_wait_ms is not None:
                snapshot.queue_wait_total_ms += queue_wait_ms
                snapshot.queue_wait_sample_count += 1
                tracked.queue_wait_recorded = True

        if state == "started" and not tracked.start_delay_recorded:
            start_delay_ms = _duration_ms(tracked.latest_received_at, captured_at)
            if start_delay_ms is not None:
                snapshot.start_delay_total_ms += start_delay_ms
                snapshot.start_delay_sample_count += 1
                tracked.start_delay_recorded = True

        if state in {"succeeded", "failed", "lost"}:
            if not tracked.run_duration_recorded:
                run_duration_ms = _duration_ms(tracked.latest_started_at, captured_at)
                if run_duration_ms is not None:
                    snapshot.run_duration_total_ms += run_duration_ms
                    snapshot.run_duration_sample_count += 1
                    tracked.run_duration_recorded = True

            if not tracked.end_to_end_recorded:
                end_to_end_ms = _duration_ms(tracked.sent_at, captured_at)
                if end_to_end_ms is not None:
                    snapshot.end_to_end_total_ms += end_to_end_ms
                    snapshot.end_to_end_sample_count += 1
                    tracked.end_to_end_recorded = True


def _duration_ms(start_at: str | None, end_at: str) -> int | None:
    if start_at is None:
        return None
    start = _parse_iso8601(start_at)
    end = _parse_iso8601(end_at)
    delta_ms = round((end - start).total_seconds() * 1000)
    return max(delta_ms, 0)


def _should_count_state(
    tracked: _TrackedTask,
    *,
    state: TaskState,
    captured_at: str,
) -> bool:
    if state == "lost":
        return False
    return not is_future_live_eta(scheduled_for=tracked.scheduled_for, reference_at=captured_at)


def _is_visible_snapshot(snapshot: QueueSnapshot) -> bool:
    return snapshot.total_tasks > 0 or any(
        (
            snapshot.historical_succeeded_count > 0,
            snapshot.historical_failed_count > 0,
            snapshot.historical_retried_count > 0,
        )
    )

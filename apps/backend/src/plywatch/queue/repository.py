"""Queue snapshot repository contracts and in-memory implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, TypeAlias
from collections.abc import Callable

from loom.core.repository import RepositoryBuildContext, repository_for
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.shared.in_memory_projection_repository import (
    InMemoryProjectionRepository,
    _parse_iso8601,
)
from plywatch.task.models import TaskState
from plywatch.task.policies import is_future_live_eta
from plywatch.task.constants import (
    FAILED_TASK_STATES,
    TASK_STATE_FAILED,
    TASK_STATE_LOST,
    TASK_STATE_RECEIVED,
    TASK_STATE_RETRYING,
    TASK_STATE_SENT,
    TASK_STATE_STARTED,
    TASK_STATE_SUCCEEDED,
)

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


class _QueueCounterAttr(StrEnum):
    SENT_COUNT = "sent_count"
    ACTIVE_COUNT = "active_count"
    RETRYING_COUNT = "retrying_count"
    SUCCEEDED_COUNT = "succeeded_count"
    FAILED_COUNT = "failed_count"


class _TrackedTimestampAttr(StrEnum):
    SENT_AT = "sent_at"
    LATEST_RECEIVED_AT = "latest_received_at"
    LATEST_STARTED_AT = "latest_started_at"


class _TrackedDurationFlag(StrEnum):
    QUEUE_WAIT_RECORDED = "queue_wait_recorded"
    START_DELAY_RECORDED = "start_delay_recorded"
    RUN_DURATION_RECORDED = "run_duration_recorded"
    END_TO_END_RECORDED = "end_to_end_recorded"


class _QueueMetricTotalAttr(StrEnum):
    QUEUE_WAIT_TOTAL_MS = "queue_wait_total_ms"
    START_DELAY_TOTAL_MS = "start_delay_total_ms"
    RUN_DURATION_TOTAL_MS = "run_duration_total_ms"
    END_TO_END_TOTAL_MS = "end_to_end_total_ms"


class _QueueMetricCountAttr(StrEnum):
    QUEUE_WAIT_SAMPLE_COUNT = "queue_wait_sample_count"
    START_DELAY_SAMPLE_COUNT = "start_delay_sample_count"
    RUN_DURATION_SAMPLE_COUNT = "run_duration_sample_count"
    END_TO_END_SAMPLE_COUNT = "end_to_end_sample_count"


DurationMetricSpec: TypeAlias = tuple[
    _TrackedDurationFlag,
    _TrackedTimestampAttr,
    _QueueMetricTotalAttr,
    _QueueMetricCountAttr,
]

_STATE_COUNTER_ATTR_BY_TASK_STATE: dict[TaskState, _QueueCounterAttr] = {
    TASK_STATE_SENT: _QueueCounterAttr.SENT_COUNT,
    TASK_STATE_RECEIVED: _QueueCounterAttr.ACTIVE_COUNT,
    TASK_STATE_STARTED: _QueueCounterAttr.ACTIVE_COUNT,
    TASK_STATE_RETRYING: _QueueCounterAttr.RETRYING_COUNT,
    TASK_STATE_SUCCEEDED: _QueueCounterAttr.SUCCEEDED_COUNT,
    TASK_STATE_FAILED: _QueueCounterAttr.FAILED_COUNT,
    TASK_STATE_LOST: _QueueCounterAttr.FAILED_COUNT,
}

_TIMESTAMP_MARKER_ATTR_BY_STATE: dict[TaskState, _TrackedTimestampAttr] = {
    TASK_STATE_SENT: _TrackedTimestampAttr.SENT_AT,
    TASK_STATE_RECEIVED: _TrackedTimestampAttr.LATEST_RECEIVED_AT,
    TASK_STATE_STARTED: _TrackedTimestampAttr.LATEST_STARTED_AT,
}

_DURATION_METRIC_SPECS_BY_STATE: dict[TaskState, tuple[DurationMetricSpec, ...]] = {
    TASK_STATE_RECEIVED: (
        (
            _TrackedDurationFlag.QUEUE_WAIT_RECORDED,
            _TrackedTimestampAttr.SENT_AT,
            _QueueMetricTotalAttr.QUEUE_WAIT_TOTAL_MS,
            _QueueMetricCountAttr.QUEUE_WAIT_SAMPLE_COUNT,
        ),
    ),
    TASK_STATE_STARTED: (
        (
            _TrackedDurationFlag.START_DELAY_RECORDED,
            _TrackedTimestampAttr.LATEST_RECEIVED_AT,
            _QueueMetricTotalAttr.START_DELAY_TOTAL_MS,
            _QueueMetricCountAttr.START_DELAY_SAMPLE_COUNT,
        ),
    ),
    TASK_STATE_SUCCEEDED: (
        (
            _TrackedDurationFlag.RUN_DURATION_RECORDED,
            _TrackedTimestampAttr.LATEST_STARTED_AT,
            _QueueMetricTotalAttr.RUN_DURATION_TOTAL_MS,
            _QueueMetricCountAttr.RUN_DURATION_SAMPLE_COUNT,
        ),
        (
            _TrackedDurationFlag.END_TO_END_RECORDED,
            _TrackedTimestampAttr.SENT_AT,
            _QueueMetricTotalAttr.END_TO_END_TOTAL_MS,
            _QueueMetricCountAttr.END_TO_END_SAMPLE_COUNT,
        ),
    ),
    TASK_STATE_FAILED: (
        (
            _TrackedDurationFlag.RUN_DURATION_RECORDED,
            _TrackedTimestampAttr.LATEST_STARTED_AT,
            _QueueMetricTotalAttr.RUN_DURATION_TOTAL_MS,
            _QueueMetricCountAttr.RUN_DURATION_SAMPLE_COUNT,
        ),
        (
            _TrackedDurationFlag.END_TO_END_RECORDED,
            _TrackedTimestampAttr.SENT_AT,
            _QueueMetricTotalAttr.END_TO_END_TOTAL_MS,
            _QueueMetricCountAttr.END_TO_END_SAMPLE_COUNT,
        ),
    ),
    TASK_STATE_LOST: (
        (
            _TrackedDurationFlag.RUN_DURATION_RECORDED,
            _TrackedTimestampAttr.LATEST_STARTED_AT,
            _QueueMetricTotalAttr.RUN_DURATION_TOTAL_MS,
            _QueueMetricCountAttr.RUN_DURATION_SAMPLE_COUNT,
        ),
        (
            _TrackedDurationFlag.END_TO_END_RECORDED,
            _TrackedTimestampAttr.SENT_AT,
            _QueueMetricTotalAttr.END_TO_END_TOTAL_MS,
            _QueueMetricCountAttr.END_TO_END_SAMPLE_COUNT,
        ),
    ),
}


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

            target = self._get_or_create_snapshot(resolved_queue, captured_at)
            self._record_historical_counts(target, previous=previous, state=state)

            if previous is not None and previous.counted:
                self._decrement(previous)

            tracked = self._build_tracked_task(
                task_id=task_id,
                resolved_queue=resolved_queue,
                routing_key=routing_key,
                state=state,
                captured_at=captured_at,
                scheduled_for=scheduled_for,
                previous=previous,
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
        counter_attr = _STATE_COUNTER_ATTR_BY_TASK_STATE.get(state)
        if counter_attr is None:
            return
        setattr(snapshot, counter_attr.value, max(0, getattr(snapshot, counter_attr.value) + delta))

    def _update_timing_markers(
        self,
        tracked: _TrackedTask,
        *,
        state: TaskState,
        captured_at: str,
    ) -> None:
        target_attr = _TIMESTAMP_MARKER_ATTR_BY_STATE.get(state)
        if target_attr is None:
            return
        if target_attr is _TrackedTimestampAttr.SENT_AT and tracked.sent_at is not None:
            return
        setattr(tracked, target_attr.value, captured_at)

    def _record_timing_metrics(
        self,
        snapshot: QueueSnapshot,
        tracked: _TrackedTask,
        *,
        state: TaskState,
        captured_at: str,
    ) -> None:
        for recorded_attr, start_attr, total_attr, count_attr in _DURATION_METRIC_SPECS_BY_STATE.get(state, ()):
            self._record_duration_metric(
                tracked=tracked,
                recorded_attr=recorded_attr,
                start_at=getattr(tracked, start_attr.value),
                end_at=captured_at,
                apply=lambda value, *, total_attr=total_attr, count_attr=count_attr: _accumulate_metric(
                    snapshot,
                    total_attr=total_attr,
                    count_attr=count_attr,
                    value=value,
                ),
            )

    def _get_or_create_snapshot(self, queue_name: str, captured_at: str) -> QueueSnapshot:
        target = self._items.get(queue_name)
        if target is not None:
            return target

        target = QueueSnapshot(
            name=queue_name,
            first_seen_at=captured_at,
            last_seen_at=captured_at,
        )
        self._upsert_locked(queue_name, target)
        return target

    def _record_historical_counts(
        self,
        snapshot: QueueSnapshot,
        *,
        previous: _TrackedTask | None,
        state: TaskState,
    ) -> None:
        if previous is None:
            snapshot.historical_total_seen += 1
        if state == TASK_STATE_RETRYING:
            snapshot.historical_retried_count += 1
        previous_state = previous.state if previous is not None else None
        if state == TASK_STATE_SUCCEEDED and previous_state != TASK_STATE_SUCCEEDED:
            snapshot.historical_succeeded_count += 1
        if state in FAILED_TASK_STATES and previous_state not in FAILED_TASK_STATES:
            snapshot.historical_failed_count += 1

    def _build_tracked_task(
        self,
        *,
        task_id: str,
        resolved_queue: str,
        routing_key: str | None,
        state: TaskState,
        captured_at: str,
        scheduled_for: str | None,
        previous: _TrackedTask | None,
    ) -> _TrackedTask:
        return _TrackedTask(
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

    def _record_duration_metric(
        self,
        *,
        tracked: _TrackedTask,
        recorded_attr: _TrackedDurationFlag,
        start_at: str | None,
        end_at: str,
        apply: Callable[[int], None],
    ) -> None:
        if getattr(tracked, recorded_attr.value):
            return
        duration_ms = _duration_ms(start_at, end_at)
        if duration_ms is None:
            return
        apply(duration_ms)
        setattr(tracked, recorded_attr.value, True)


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
    if state == TASK_STATE_LOST:
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


def _accumulate_metric(
    snapshot: QueueSnapshot,
    *,
    total_attr: _QueueMetricTotalAttr,
    count_attr: _QueueMetricCountAttr,
    value: int,
) -> None:
    setattr(snapshot, total_attr.value, getattr(snapshot, total_attr.value) + value)
    setattr(snapshot, count_attr.value, getattr(snapshot, count_attr.value) + 1)

"""Projection reducer dedicated to observed schedule-origin runs."""

from __future__ import annotations

from collections.abc import Collection

from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.constants import TASK_EVENTS
from plywatch.task.envelope import TaskEnvelope, from_raw_task_event
from plywatch.task.snapshot_reducer import TaskSnapshotReducer

from plywatch.schedule.repository import ScheduleRunSnapshot, ScheduleRunSnapshotRepository


def build_schedule_run_snapshot(envelope: TaskEnvelope) -> ScheduleRunSnapshot:
    """Create one new schedule-run snapshot from the first observed envelope."""

    return ScheduleRunSnapshot(
        uuid=envelope.task_id,
        first_seen_at=envelope.captured_at,
        last_seen_at=envelope.captured_at,
    )


class ScheduleProjector:
    """Persist only task runs that originate from observed schedules."""

    @property
    def handled_event_types(self) -> Collection[str]:
        return TASK_EVENTS

    def __init__(self, repository: ScheduleRunSnapshotRepository) -> None:
        self._repository = repository
        self._reducer = TaskSnapshotReducer(
            repository,
            snapshot_factory=build_schedule_run_snapshot,
        )

    def apply(self, event: RawCeleryEvent) -> None:
        """Update the schedule-run projection when one schedule-origin event arrives."""

        envelope = from_raw_task_event(event)
        if envelope is None:
            return
        if envelope.schedule_id is None and self._repository.get(envelope.task_id) is None:
            return
        self._reducer.apply_envelope(envelope, event)

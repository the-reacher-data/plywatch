"""Queue projection reducer fed by raw task events."""

from __future__ import annotations

from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.constants import TASK_EVENTS
from plywatch.task.envelope import from_raw_task_event


class QueueProjector:
    """Build consolidated queue snapshots from observed task events."""

    handled_event_types = TASK_EVENTS

    def __init__(self, repository: QueueSnapshotRepository) -> None:
        self._repository = repository

    def apply(self, event: RawCeleryEvent) -> None:
        """Update the queue projection when one task event arrives."""
        envelope = from_raw_task_event(event)
        if envelope is None:
            return

        self._repository.apply_task_event(
            task_id=envelope.task_id,
            queue_name=envelope.queue_name,
            routing_key=envelope.routing_key,
            state=envelope.state,
            captured_at=envelope.captured_at,
            scheduled_for=envelope.scheduled_for,
        )

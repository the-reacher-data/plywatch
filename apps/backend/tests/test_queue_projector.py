from __future__ import annotations

from plywatch.queue.projector import QueueProjector
from plywatch.queue.repository import InMemoryQueueSnapshotRepository
from plywatch.shared.raw_events import RawCeleryEvent, build_raw_event


def test_queue_projector_tracks_state_transitions_per_queue() -> None:
    repository = InMemoryQueueSnapshotRepository(max_age_seconds=3600)
    projector = QueueProjector(repository)

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "task-1",
                "queue": "priority",
                "routing_key": "priority",
            }
        )
    )
    projector.apply(build_raw_event({"type": "task-received", "uuid": "task-1"}))
    projector.apply(build_raw_event({"type": "task-succeeded", "uuid": "task-1"}))

    items = repository.list_recent(limit=10)
    assert len(items) == 1
    snapshot = items[0]
    assert snapshot.name == "priority"
    assert snapshot.routing_keys == ["priority"]
    assert snapshot.total_tasks == 1
    assert snapshot.sent_count == 0
    assert snapshot.active_count == 0
    assert snapshot.succeeded_count == 1


def test_queue_projector_tracks_multiple_tasks_in_same_queue() -> None:
    repository = InMemoryQueueSnapshotRepository(max_age_seconds=3600)
    projector = QueueProjector(repository)

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "task-1",
                "queue": "default",
            }
        )
    )
    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "task-2",
                "queue": "default",
            }
        )
    )
    projector.apply(build_raw_event({"type": "task-failed", "uuid": "task-2"}))

    snapshot = repository.list_recent(limit=10)[0]
    assert snapshot.name == "default"
    assert snapshot.total_tasks == 2
    assert snapshot.sent_count == 1
    assert snapshot.failed_count == 1


def test_queue_projector_accumulates_incremental_queue_timings() -> None:
    repository = InMemoryQueueSnapshotRepository(max_age_seconds=86400)
    projector = QueueProjector(repository)

    events = [
        RawCeleryEvent(
            captured_at="2099-03-16T10:00:00+00:00",
            event_type="task-sent",
            uuid="task-1",
            hostname="gen10@producer",
            payload={"queue": "default", "routing_key": "default"},
        ),
        RawCeleryEvent(
            captured_at="2099-03-16T10:00:02+00:00",
            event_type="task-received",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at="2099-03-16T10:00:05+00:00",
            event_type="task-started",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
        RawCeleryEvent(
            captured_at="2099-03-16T10:00:11+00:00",
            event_type="task-succeeded",
            uuid="task-1",
            hostname="celery@worker",
            payload={},
        ),
    ]

    for event in events:
        projector.apply(event)

    snapshot = repository.list_recent(limit=10)[0]
    assert snapshot.queue_wait_sample_count == 1
    assert snapshot.queue_wait_total_ms == 2000
    assert snapshot.start_delay_sample_count == 1
    assert snapshot.start_delay_total_ms == 3000
    assert snapshot.run_duration_sample_count == 1
    assert snapshot.run_duration_total_ms == 6000
    assert snapshot.end_to_end_sample_count == 1
    assert snapshot.end_to_end_total_ms == 11000

from __future__ import annotations

from unittest.mock import Mock

from plywatch.shared.celery_events import CeleryEventConsumer
from plywatch.shared.raw_events import EventCounterStore, RawEventStore


def test_consumer_counts_all_events_and_skips_excluded_buffer_events() -> None:
    store = RawEventStore(10)
    counter_store = EventCounterStore()
    callback = Mock()
    consumer = CeleryEventConsumer(
        Mock(),
        store,
        counter_store,
        buffer_excluded_event_types=("worker-heartbeat",),
        on_event=callback,
    )

    consumer._handle_event(  # noqa: SLF001
        {
            "type": "worker-heartbeat",
            "hostname": "celery@worker-1",
        }
    )
    consumer._handle_event(  # noqa: SLF001
        {
            "type": "task-sent",
            "uuid": "task-1",
        }
    )

    assert counter_store.total_count() == 2
    assert counter_store.count_for("worker-heartbeat") == 1
    assert counter_store.count_for("task-sent") == 1
    assert store.count() == 1
    retained = store.list_recent(10)
    assert len(retained) == 1
    assert retained[0].event_type == "task-sent"
    assert callback.call_count == 2

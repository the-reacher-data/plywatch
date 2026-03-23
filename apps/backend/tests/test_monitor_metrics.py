from __future__ import annotations

from prometheus_client import CollectorRegistry, generate_latest

from plywatch.shared.monitor_metrics import (
    CompositeMonitorMetricsAdapter,
    CompositeRuntimeMetricsAdapter,
)
from plywatch.queue.projector import QueueProjector
from plywatch.queue.repository import InMemoryQueueSnapshotRepository
from plywatch.shared.monitor_metrics import MonitorMetricsContext
from plywatch.shared.prometheus_monitor_adapter import PrometheusPlywatchMetricsAdapter
from plywatch.shared.raw_events import RawEventStore, build_raw_event
from plywatch.task.projector import TaskProjector
from plywatch.task.repository import InMemoryTaskSnapshotRepository
from plywatch.worker.projector import WorkerProjector
from plywatch.worker.repository import InMemoryWorkerSnapshotRepository


def test_prometheus_monitor_adapter_records_plywatch_and_flower_metrics() -> None:
    registry = CollectorRegistry()
    adapter = PrometheusPlywatchMetricsAdapter(registry=registry)
    raw_store = RawEventStore(50)
    task_repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=3600)
    worker_repository = InMemoryWorkerSnapshotRepository(
        max_age_seconds=3600,
        stale_after_seconds=15,
    )
    queue_repository = InMemoryQueueSnapshotRepository(max_age_seconds=3600)
    task_projector = TaskProjector(task_repository)
    worker_projector = WorkerProjector(worker_repository)
    queue_projector = QueueProjector(queue_repository)
    context = MonitorMetricsContext(
        raw_event_store=raw_store,
        task_repository=task_repository,
        worker_repository=worker_repository,
        queue_repository=queue_repository,
    )

    events = [
        build_raw_event(
            {
                "type": "worker-heartbeat",
                "hostname": "celery@worker-1",
                "active": 1,
                "processed": 2,
            }
        ),
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "task-1",
                "name": "loom.job.HelloSuccessJob",
                "queue": "default",
                "routing_key": "default",
            }
        ),
        build_raw_event(
            {
                "type": "task-received",
                "uuid": "task-1",
                "hostname": "celery@worker-1",
                "name": "loom.job.HelloSuccessJob",
            }
        ),
        build_raw_event(
            {
                "type": "task-started",
                "uuid": "task-1",
                "hostname": "celery@worker-1",
            }
        ),
        build_raw_event(
            {
                "type": "task-succeeded",
                "uuid": "task-1",
                "hostname": "celery@worker-1",
                "result": "{'ok': true}",
            }
        ),
    ]

    for event in events:
        raw_store.append(event)
        task_projector.apply(event)
        worker_projector.apply(event)
        queue_projector.apply(event)
        adapter.record_projection_event(event, context=context)

    payload = generate_latest(registry).decode("utf-8")

    assert 'plywatch_celery_events_total{event_type="task-sent"} 1.0' in payload
    assert 'plywatch_tasks_tracked 1.0' in payload
    assert 'plywatch_workers_by_state{state="online"} 1.0' in payload
    assert 'plywatch_queue_tasks{queue="default",state="succeeded"} 1.0' in payload
    assert 'plywatch_task_queue_wait_seconds_count{kind="job",queue="default"} 1.0' in payload
    assert 'plywatch_task_runtime_seconds_count{kind="job",queue="default"} 1.0' in payload
    assert 'flower_events_total{task="loom.job.HelloSuccessJob",type="task-sent",worker="unknown"} 1.0' in payload
    assert (
        'flower_task_prefetch_time_seconds_count{task="loom.job.HelloSuccessJob",worker="celery@worker-1"} 1.0'
        in payload
    )
    assert (
        'flower_task_runtime_seconds_count{task="loom.job.HelloSuccessJob",worker="celery@worker-1"} 1.0'
        in payload
    )
    assert 'flower_worker_online{worker="celery@worker-1"} 1.0' in payload
    assert (
        'flower_worker_number_of_currently_executing_tasks{worker="celery@worker-1"} 1.0'
        in payload
    )


def test_composite_runtime_metrics_adapter_forwards_events_to_all_adapters() -> None:
    received: list[tuple[str, object]] = []

    class RecordingRuntimeAdapter:
        def __init__(self, name: str) -> None:
            self._name = name

        def on_event(self, event: object) -> None:
            received.append((self._name, event))

    event = object()
    adapter = CompositeRuntimeMetricsAdapter(
        (
            RecordingRuntimeAdapter("first"),
            RecordingRuntimeAdapter("second"),
        )
    )

    adapter.on_event(event)

    assert received == [("first", event), ("second", event)]


def test_composite_monitor_metrics_adapter_forwards_events_to_all_adapters() -> None:
    raw_store = RawEventStore(10)
    task_repository = InMemoryTaskSnapshotRepository(max_tasks=10, max_age_seconds=60)
    worker_repository = InMemoryWorkerSnapshotRepository(max_age_seconds=60, stale_after_seconds=15)
    queue_repository = InMemoryQueueSnapshotRepository(max_age_seconds=60)
    context = MonitorMetricsContext(
        raw_event_store=raw_store,
        task_repository=task_repository,
        worker_repository=worker_repository,
        queue_repository=queue_repository,
    )
    event = build_raw_event({"type": "task-sent", "uuid": "task-1"})
    received: list[tuple[str, str, MonitorMetricsContext]] = []

    class RecordingMonitorAdapter:
        def __init__(self, name: str) -> None:
            self._name = name

        def record_projection_event(self, event: object, *, context: MonitorMetricsContext) -> None:
            received.append((self._name, event.event_type, context))

    adapter = CompositeMonitorMetricsAdapter(
        (
            RecordingMonitorAdapter("first"),
            RecordingMonitorAdapter("second"),
        )
    )

    adapter.record_projection_event(event, context=context)

    assert received == [
        ("first", "task-sent", context),
        ("second", "task-sent", context),
    ]

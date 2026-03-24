"""Prometheus adapters for Plywatch runtime and monitor metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loom.prometheus import PrometheusMetricsAdapter

from plywatch.shared.monitor_metrics import MonitorMetricsAdapter, MonitorMetricsContext
from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.constants import (
    TASK_EVENT_FAILED,
    TASK_EVENT_RECEIVED,
    TASK_EVENT_STARTED,
    TASK_EVENT_SUCCEEDED,
    TASK_TERMINAL_EVENTS,
)
from plywatch.worker.constants import WORKER_STATES, WORKER_STATE_ONLINE

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
    from plywatch.task.models import TaskSnapshot

@dataclass(frozen=True)
class MonitorInstruments:
    """Prometheus instrument set used by the monitor adapter."""

    plywatch_events_total: Counter
    plywatch_queue_wait_seconds: Histogram
    plywatch_task_runtime_seconds: Histogram
    plywatch_raw_events_tracked: Gauge
    plywatch_tasks_tracked: Gauge
    plywatch_workers_tracked: Gauge
    plywatch_workers_by_state: Gauge
    plywatch_queue_tasks: Gauge
    flower_events_total: Counter | None
    flower_task_prefetch_time_seconds: Histogram | None
    flower_worker_prefetched_tasks: Gauge | None
    flower_task_runtime_seconds: Histogram | None
    flower_worker_online: Gauge | None
    flower_worker_running_tasks: Gauge | None


_GLOBAL_INSTRUMENTS_BY_FLOWER_COMPAT: dict[bool, MonitorInstruments] = {}

_QUEUE_STATES: tuple[str, ...] = ("total", "sent", "active", "retrying", "succeeded", "failed")


def _create_instruments(
    registry: CollectorRegistry | None,
    *,
    enable_flower_compat: bool,
) -> MonitorInstruments:
    """Create Prometheus instruments bound to *registry*."""
    from prometheus_client import Counter, Gauge, Histogram

    plywatch_events_total: Counter = Counter(
        "plywatch_celery_events",
        "Total number of raw Celery events observed by Plywatch.",
        ["event_type"],
        registry=registry,
    )
    plywatch_queue_wait_seconds: Histogram = Histogram(
        "plywatch_task_queue_wait_seconds",
        "Observed time between task publication and worker receipt.",
        ["kind", "queue"],
        registry=registry,
    )
    plywatch_task_runtime_seconds: Histogram = Histogram(
        "plywatch_task_runtime_seconds",
        "Observed time between task start and task completion.",
        ["kind", "queue"],
        registry=registry,
    )
    plywatch_raw_events_tracked: Gauge = Gauge(
        "plywatch_raw_events_tracked",
        "Current number of retained raw Celery events.",
        registry=registry,
    )
    plywatch_tasks_tracked: Gauge = Gauge(
        "plywatch_tasks_tracked",
        "Current number of tracked task snapshots.",
        registry=registry,
    )
    plywatch_workers_tracked: Gauge = Gauge(
        "plywatch_workers_tracked",
        "Current number of tracked worker snapshots.",
        registry=registry,
    )
    plywatch_workers_by_state: Gauge = Gauge(
        "plywatch_workers_by_state",
        "Current number of tracked workers grouped by state.",
        ["state"],
        registry=registry,
    )
    plywatch_queue_tasks: Gauge = Gauge(
        "plywatch_queue_tasks",
        "Current queue snapshot counts grouped by queue and task state.",
        ["queue", "state"],
        registry=registry,
    )

    flower_events_total: Counter | None = None
    flower_task_prefetch_time_seconds: Histogram | None = None
    flower_worker_prefetched_tasks: Gauge | None = None
    flower_task_runtime_seconds: Histogram | None = None
    flower_worker_online: Gauge | None = None
    flower_worker_number_of_currently_executing_tasks: Gauge | None = None
    if enable_flower_compat:
        flower_events_total = Counter(
            "flower_events",
            "Deprecated compatibility counter matching Flower event totals.",
            ["task", "type", "worker"],
            registry=registry,
        )
        flower_task_prefetch_time_seconds = Histogram(
            "flower_task_prefetch_time_seconds",
            "Deprecated compatibility histogram for task publish-to-receive latency.",
            ["task", "worker"],
            registry=registry,
        )
        flower_worker_prefetched_tasks = Gauge(
            "flower_worker_prefetched_tasks",
            "Deprecated compatibility gauge for prefetched tasks per worker and task name.",
            ["task", "worker"],
            registry=registry,
        )
        flower_task_runtime_seconds = Histogram(
            "flower_task_runtime_seconds",
            "Deprecated compatibility histogram for task runtime per worker and task name.",
            ["task", "worker"],
            registry=registry,
        )
        flower_worker_online = Gauge(
            "flower_worker_online",
            "Deprecated compatibility gauge indicating whether a worker is online.",
            ["worker"],
            registry=registry,
        )
        flower_worker_number_of_currently_executing_tasks = Gauge(
            "flower_worker_number_of_currently_executing_tasks",
            "Deprecated compatibility gauge for running tasks per worker.",
            ["worker"],
            registry=registry,
        )

    return MonitorInstruments(
        plywatch_events_total=plywatch_events_total,
        plywatch_queue_wait_seconds=plywatch_queue_wait_seconds,
        plywatch_task_runtime_seconds=plywatch_task_runtime_seconds,
        plywatch_raw_events_tracked=plywatch_raw_events_tracked,
        plywatch_tasks_tracked=plywatch_tasks_tracked,
        plywatch_workers_tracked=plywatch_workers_tracked,
        plywatch_workers_by_state=plywatch_workers_by_state,
        plywatch_queue_tasks=plywatch_queue_tasks,
        flower_events_total=flower_events_total,
        flower_task_prefetch_time_seconds=flower_task_prefetch_time_seconds,
        flower_worker_prefetched_tasks=flower_worker_prefetched_tasks,
        flower_task_runtime_seconds=flower_task_runtime_seconds,
        flower_worker_online=flower_worker_online,
        flower_worker_running_tasks=flower_worker_number_of_currently_executing_tasks,
    )


def _get_instruments(
    registry: CollectorRegistry | None,
    *,
    enable_flower_compat: bool,
) -> MonitorInstruments:
    """Return instruments, creating them if needed."""
    if registry is not None:
        return _create_instruments(registry, enable_flower_compat=enable_flower_compat)
    instruments = _GLOBAL_INSTRUMENTS_BY_FLOWER_COMPAT.get(enable_flower_compat)
    if instruments is None:
        instruments = _create_instruments(None, enable_flower_compat=enable_flower_compat)
        _GLOBAL_INSTRUMENTS_BY_FLOWER_COMPAT[enable_flower_compat] = instruments
    return instruments


class PrometheusPlywatchMetricsAdapter(MonitorMetricsAdapter):
    """Prometheus adapter for Plywatch monitor metrics.

    Exposes canonical ``plywatch_*`` metrics and deprecated ``flower_*``
    aliases to ease migration from Flower dashboards.
    """

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        *,
        enable_flower_compat: bool = True,
    ) -> None:
        instruments = _get_instruments(
            registry,
            enable_flower_compat=enable_flower_compat,
        )
        self._plywatch_events_total = instruments.plywatch_events_total
        self._plywatch_queue_wait_seconds = instruments.plywatch_queue_wait_seconds
        self._plywatch_task_runtime_seconds = instruments.plywatch_task_runtime_seconds
        self._plywatch_raw_events_tracked = instruments.plywatch_raw_events_tracked
        self._plywatch_tasks_tracked = instruments.plywatch_tasks_tracked
        self._plywatch_workers_tracked = instruments.plywatch_workers_tracked
        self._plywatch_workers_by_state = instruments.plywatch_workers_by_state
        self._plywatch_queue_tasks = instruments.plywatch_queue_tasks
        self._flower_events_total = instruments.flower_events_total
        self._flower_task_prefetch_time_seconds = instruments.flower_task_prefetch_time_seconds
        self._flower_worker_prefetched_tasks = instruments.flower_worker_prefetched_tasks
        self._flower_task_runtime_seconds = instruments.flower_task_runtime_seconds
        self._flower_worker_online = instruments.flower_worker_online
        self._flower_worker_running_tasks = instruments.flower_worker_running_tasks
        self._seen_queue_labels: set[tuple[str, str]] = set()
        self._prefetched_by_task: dict[str, tuple[str, str]] = {}

    def record_projection_event(
        self,
        event: RawCeleryEvent,
        *,
        context: MonitorMetricsContext,
    ) -> None:
        """Record monitor metrics for one observed Celery event."""
        self._plywatch_events_total.labels(event_type=event.event_type).inc()
        self._plywatch_raw_events_tracked.set(context.raw_event_store.count())
        self._plywatch_tasks_tracked.set(context.task_repository.count())

        snapshot = context.task_repository.get(event.uuid) if event.uuid is not None else None
        task_name = snapshot.name if snapshot is not None and snapshot.name is not None else "unknown"
        worker_name = event.hostname or (snapshot.worker_hostname if snapshot is not None else None) or "unknown"

        if self._flower_events_total is not None:
            self._flower_events_total.labels(
                task=task_name,
                type=event.event_type,
                worker=worker_name,
            ).inc()

        self._observe_task_latencies(event, snapshot, worker_name)
        self._update_flower_task_gauges(event, task_name, worker_name)
        self._update_worker_gauges(context)
        self._update_queue_gauges(context)

    def _observe_task_latencies(
        self,
        event: RawCeleryEvent,
        snapshot: TaskSnapshot | None,
        worker_name: str,
    ) -> None:
        if snapshot is None:
            return

        queue = snapshot.queue or "unknown"
        kind = snapshot.kind
        task_name = snapshot.name or "unknown"

        if event.event_type == TASK_EVENT_RECEIVED:
            seconds = _duration_seconds(snapshot.sent_at, snapshot.received_at)
            if seconds is not None:
                self._plywatch_queue_wait_seconds.labels(kind=kind, queue=queue).observe(seconds)
                if self._flower_task_prefetch_time_seconds is not None:
                    self._flower_task_prefetch_time_seconds.labels(
                        task=task_name,
                        worker=worker_name,
                    ).observe(seconds)

        if event.event_type in {TASK_EVENT_SUCCEEDED, TASK_EVENT_FAILED}:
            seconds = _duration_seconds(snapshot.started_at, snapshot.finished_at)
            if seconds is not None:
                self._plywatch_task_runtime_seconds.labels(kind=kind, queue=queue).observe(seconds)
                if self._flower_task_runtime_seconds is not None:
                    self._flower_task_runtime_seconds.labels(
                        task=task_name,
                        worker=worker_name,
                    ).observe(seconds)

    def _update_flower_task_gauges(
        self,
        event: RawCeleryEvent,
        task_name: str,
        worker_name: str,
    ) -> None:
        if self._flower_worker_prefetched_tasks is None:
            return
        if event.uuid is None:
            return

        if event.event_type == TASK_EVENT_RECEIVED:
            self._prefetched_by_task[event.uuid] = (task_name, worker_name)
            self._flower_worker_prefetched_tasks.labels(task=task_name, worker=worker_name).inc()
            return

        if event.event_type == TASK_EVENT_STARTED:
            prefetched = self._prefetched_by_task.pop(event.uuid, None)
            if prefetched is not None:
                self._flower_worker_prefetched_tasks.labels(
                    task=prefetched[0],
                    worker=prefetched[1],
                ).dec()
            return

        if event.event_type in TASK_TERMINAL_EVENTS:
            prefetched = self._prefetched_by_task.pop(event.uuid, None)
            if prefetched is not None:
                self._flower_worker_prefetched_tasks.labels(
                    task=prefetched[0],
                    worker=prefetched[1],
                ).dec()

    def _update_worker_gauges(self, context: MonitorMetricsContext) -> None:
        count = context.worker_repository.count()
        self._plywatch_workers_tracked.set(count)
        workers = context.worker_repository.list_recent(count) if count > 0 else []
        state_counts = dict.fromkeys(WORKER_STATES, 0)

        for worker in workers:
            state_counts[worker.state] += 1
            if self._flower_worker_online is not None:
                self._flower_worker_online.labels(worker=worker.hostname).set(
                    1 if worker.state == WORKER_STATE_ONLINE else 0
                )
            if self._flower_worker_running_tasks is not None:
                self._flower_worker_running_tasks.labels(worker=worker.hostname).set(float(worker.active or 0))

        for state in WORKER_STATES:
            self._plywatch_workers_by_state.labels(state=state).set(state_counts[state])

    def _update_queue_gauges(self, context: MonitorMetricsContext) -> None:
        count = context.queue_repository.count()
        queues = context.queue_repository.list_recent(count) if count > 0 else []

        current_labels: set[tuple[str, str]] = set()
        for queue in queues:
            values = {
                "total": queue.total_tasks,
                "sent": queue.sent_count,
                "active": queue.active_count,
                "retrying": queue.retrying_count,
                "succeeded": queue.succeeded_count,
                "failed": queue.failed_count,
            }
            for state in _QUEUE_STATES:
                self._plywatch_queue_tasks.labels(queue=queue.name, state=state).set(values[state])
                current_labels.add((queue.name, state))

        removed = self._seen_queue_labels - current_labels
        for queue_name, state in removed:
            self._plywatch_queue_tasks.labels(queue=queue_name, state=state).set(0)
        self._seen_queue_labels = current_labels


def build_prometheus_runtime_adapter(
    registry: CollectorRegistry | None = None,
) -> PrometheusMetricsAdapter:
    """Build the Prometheus adapter used for Loom runtime metrics."""
    return PrometheusMetricsAdapter(registry=registry)


def build_prometheus_monitor_adapter(
    registry: CollectorRegistry | None = None,
    *,
    enable_flower_compat: bool = True,
) -> PrometheusPlywatchMetricsAdapter:
    """Build the Prometheus adapter used for Plywatch monitor metrics."""
    return PrometheusPlywatchMetricsAdapter(
        registry=registry,
        enable_flower_compat=enable_flower_compat,
    )


def _duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    """Return the non-negative duration between two ISO-8601 timestamps."""
    if started_at is None or finished_at is None:
        return None
    started = _parse_iso8601(started_at)
    finished = _parse_iso8601(finished_at)
    return max((finished - started).total_seconds(), 0.0)


def _parse_iso8601(value: str) -> datetime:
    """Parse one ISO-8601 timestamp into UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

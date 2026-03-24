"""Ports and helpers for Plywatch monitor-specific metrics adapters."""

from __future__ import annotations

from typing import Protocol

from loom.core.engine.events import RuntimeEvent
from loom.core.engine.metrics import MetricsAdapter
from loom.core.model import LoomStruct

from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.shared.raw_events import RawCeleryEvent, RawEventStore
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.worker.repository import WorkerSnapshotRepository

MONITOR_METRICS_ADAPTER_PROMETHEUS = "prometheus"


class MonitorMetricsContext(LoomStruct, kw_only=True):
    """Projection state passed to monitor metrics adapters."""

    raw_event_store: RawEventStore
    task_repository: TaskSnapshotRepository
    worker_repository: WorkerSnapshotRepository
    queue_repository: QueueSnapshotRepository


class MonitorMetricsAdapter(Protocol):
    """Port for recording Plywatch monitor-specific observations."""

    def record_projection_event(
        self,
        event: RawCeleryEvent,
        *,
        context: MonitorMetricsContext,
    ) -> None:
        """Record metrics for one observed Celery event after projection update.

        Args:
            event: Observed raw Celery event.
            context: Current projection state after reducers have applied the event.
        """


class CompositeRuntimeMetricsAdapter:
    """Fan out Loom runtime metrics to multiple adapters."""

    def __init__(self, adapters: tuple[MetricsAdapter, ...]) -> None:
        self._adapters = adapters

    def on_event(self, event: RuntimeEvent) -> None:
        """Forward one Loom runtime event to all configured adapters."""
        for adapter in self._adapters:
            adapter.on_event(event)


class CompositeMonitorMetricsAdapter:
    """Fan out monitor observations to multiple adapters."""

    def __init__(self, adapters: tuple[MonitorMetricsAdapter, ...]) -> None:
        self._adapters = adapters

    def record_projection_event(
        self,
        event: RawCeleryEvent,
        *,
        context: MonitorMetricsContext,
    ) -> None:
        """Forward one monitor observation to all configured adapters."""
        for adapter in self._adapters:
            adapter.record_projection_event(event, context=context)

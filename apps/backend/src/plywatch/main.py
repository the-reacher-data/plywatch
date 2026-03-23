"""ASGI entrypoint for the Plywatch backend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
import contextlib
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Any

import prometheus_client
from pydantic import BaseModel
from fastapi import Body, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from loom.celery.config import create_celery_app
from loom.core.bootstrap import create_kernel
from loom.core.engine.metrics import MetricsAdapter
from loom.core.di.container import LoomContainer
from loom.core.logger import configure_logging_from_values
from loom.core.repository import (
    DefaultRepositoryBuilder,
    RepositoryBuildContext,
    RepositoryRegistration,
    build_repository_registration_module,
)
from loom.core.repository.abc.query import PaginationMode
from loom.prometheus.middleware import PrometheusMiddleware
from loom.rest.fastapi.app import create_fastapi_app
from loom.rest.middleware import TraceIdMiddleware
from loom.rest.model import RestApiDefaults

from plywatch.queue.interface import QueueRestInterface
from plywatch.queue.models import QueueSnapshot
from plywatch.queue.projector import QueueProjector
from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.queue.use_cases import ListQueuesUseCase
from plywatch.monitor.interface import MonitorRestInterface
from plywatch.monitor.admin import MonitorAdminService
from plywatch.monitor.use_cases import GetOverviewUseCase, ListRawEventsUseCase
from plywatch.schedule.interface import ScheduleRestInterface
from plywatch.schedule.projector import ScheduleProjector
from plywatch.schedule.repository import ScheduleRunSnapshot, ScheduleRunSnapshotRepository
from plywatch.schedule.use_cases import ListSchedulesUseCase
from plywatch.shared.celery_events import CeleryEventConsumer
from plywatch.shared.event_dispatcher import EventDispatcher
from plywatch.shared.monitor_metrics import (
    CompositeMonitorMetricsAdapter,
    CompositeRuntimeMetricsAdapter,
    MonitorMetricsAdapter,
    MonitorMetricsContext,
)
from plywatch.shared.prometheus_monitor_adapter import (
    build_prometheus_monitor_adapter,
    build_prometheus_runtime_adapter,
)
from plywatch.shared.raw_events import EventCounterStore, RawEventStore
from plywatch.shared.runtime_config import RuntimeSettings, load_runtime_settings
from plywatch.shared.sse import SseFanout
from plywatch.task.interface import TaskRestInterface
from plywatch.task.celery_presence import CeleryTaskExecutionPresenceGateway
from plywatch.task.completed_repository import (
    CompletedTaskSnapshotRepository,
    InMemoryCompletedTaskSnapshotRepository,
)
from plywatch.task.liveness import TaskLivenessReconciler
from plywatch.task.read_repository import TaskReadRepository, UnifiedTaskReadRepository
from plywatch.task.models import TaskSnapshot
from plywatch.task.projector import TaskProjector
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.task.sections_interface import TaskSectionsRestInterface
from plywatch.task.use_cases import (
    GetTaskGraphUseCase,
    GetTaskTimelineUseCase,
    GetTaskUseCase,
    ListTaskSectionsUseCase,
    ListTasksUseCase,
)
from plywatch.worker.interface import WorkerRestInterface
from plywatch.worker.models import WorkerSnapshot
from plywatch.worker.projector import WorkerProjector
from plywatch.worker.repository import WorkerSnapshotRepository
from plywatch.worker.use_cases import ListWorkersUseCase

logger = logging.getLogger(__name__)


class MonitorIdsPayload(BaseModel):
    """Identifiers targeted by one monitor admin operation."""

    ids: list[str]


def create_app(*, start_consumer: bool = True) -> FastAPI:
    """Create the Plywatch API using Loom use cases and REST interfaces.

    Args:
        start_consumer: Whether to start the background Celery event consumer.
            Tests can disable this and feed events directly into the projector.

    Returns:
        A configured FastAPI application.
    """
    settings = load_runtime_settings()
    configure_logging_from_values(
        name=settings.logger.name,
        environment=settings.logger.environment,
        renderer=settings.logger.renderer,
        colors=settings.logger.colors,
        level=settings.logger.level,
        named_levels=settings.logger.named_levels,
        handlers=settings.logger.handlers,
    )
    raw_event_store = RawEventStore(settings.raw_event_limit)
    event_counter_store = EventCounterStore()
    sse_fanout = SseFanout()
    runtime_metrics_adapter, monitor_metrics_adapter = _build_metrics_adapters(settings)
    kernel = create_kernel(
        config=settings,
        use_cases=(
            GetOverviewUseCase,
            ListRawEventsUseCase,
            ListTasksUseCase,
            GetTaskUseCase,
            GetTaskTimelineUseCase,
            GetTaskGraphUseCase,
            ListTaskSectionsUseCase,
            ListSchedulesUseCase,
            ListWorkersUseCase,
            ListQueuesUseCase,
        ),
        modules=(
            _runtime_module(
                settings=settings,
                raw_event_store=raw_event_store,
                event_counter_store=event_counter_store,
            ),
        ),
        metrics=runtime_metrics_adapter,
    )
    task_repository = kernel.container.resolve(TaskSnapshotRepository)
    completed_task_repository = kernel.container.resolve(CompletedTaskSnapshotRepository)
    task_read_repository = kernel.container.resolve(TaskReadRepository)
    worker_repository = kernel.container.resolve(WorkerSnapshotRepository)
    queue_repository = kernel.container.resolve(QueueSnapshotRepository)
    schedule_repository = kernel.container.resolve(ScheduleRunSnapshotRepository)
    task_projector = TaskProjector(task_repository, completed_task_repository)
    worker_projector = WorkerProjector(worker_repository)
    queue_projector = QueueProjector(queue_repository)
    schedule_projector = ScheduleProjector(schedule_repository)
    event_dispatcher = EventDispatcher()
    event_dispatcher.register_many((task_projector, worker_projector, queue_projector, schedule_projector))

    def _on_event(event: Any) -> None:
        task_exists_before = (
            event.uuid is not None and event.event_type.startswith('task-') and task_repository.get(event.uuid) is not None
        )
        worker_exists_before = (
            event.hostname is not None
            and event.event_type.startswith('worker-')
            and worker_repository.get(event.hostname) is not None
        )
        event_dispatcher.dispatch(event)
        if monitor_metrics_adapter is not None:
            monitor_metrics_adapter.record_projection_event(
                event,
                context=MonitorMetricsContext(
                    raw_event_store=raw_event_store,
                    task_repository=task_repository,
                    worker_repository=worker_repository,
                    queue_repository=queue_repository,
                ),
            )
        for message in _build_frontend_events(
            event,
            task_exists_before=task_exists_before,
            worker_exists_before=worker_exists_before,
            task_repository=task_repository,
        ):
            sse_fanout.publish(message)

    celery_app = create_celery_app(settings.celery)
    consumer = CeleryEventConsumer(
        celery_app,
        raw_event_store,
        event_counter_store,
        buffer_excluded_event_types=settings.raw_event_buffer_excluded_types,
        on_event=_on_event,
    )
    task_liveness_reconciler = TaskLivenessReconciler(
        task_repository=task_repository,
        completed_task_repository=completed_task_repository,
        queue_repository=queue_repository,
        presence_gateway=CeleryTaskExecutionPresenceGateway(celery_app),
        lost_after_seconds=settings.task_lost_after_seconds,
    )
    monitor_admin = MonitorAdminService(
        task_repository=task_repository,
        completed_task_repository=completed_task_repository,
        worker_repository=worker_repository,
        queue_repository=queue_repository,
        schedule_repository=schedule_repository,
        raw_event_store=raw_event_store,
    )

    async def _reconcile_lost_tasks_loop() -> None:
        interval = settings.task_liveness_reconcile_interval_seconds
        if interval <= 0:
            return
        while True:
            await asyncio.sleep(interval)
            try:
                result = task_liveness_reconciler.reconcile()
            except Exception:
                logger.exception("Task liveness reconciliation failed")
                continue
            for task_id in result.updated_task_ids:
                sse_fanout.publish(
                    {
                        "type": "task.updated",
                        "eventType": "task-lost",
                        "taskId": task_id,
                        "workerHostname": None,
                        "queueName": None,
                        "capturedAt": None,
                        "taskName": None,
                    }
                )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        sse_fanout.attach_loop(asyncio.get_running_loop())
        reconcile_task: asyncio.Task[None] | None = None
        if start_consumer:
            consumer.start()
            if settings.task_liveness_reconcile_interval_seconds > 0:
                reconcile_task = asyncio.create_task(_reconcile_lost_tasks_loop())
        try:
            yield
        finally:
            if reconcile_task is not None:
                reconcile_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reconcile_task
            if start_consumer:
                consumer.stop()

    app = create_fastapi_app(
        kernel,
        interfaces=(
            MonitorRestInterface,
            TaskRestInterface,
            TaskSectionsRestInterface,
            ScheduleRestInterface,
            WorkerRestInterface,
            QueueRestInterface,
        ),
        defaults=RestApiDefaults(pagination_mode=PaginationMode.CURSOR),
        title=settings.app.rest.title,
        version=settings.app.rest.version,
        docs_url=settings.app.rest.docs_url,
        redoc_url=settings.app.rest.redoc_url,
        lifespan=lifespan,
    )
    if settings.trace.enabled:
        app.add_middleware(TraceIdMiddleware, header=settings.trace.header)
    if _prometheus_metrics_enabled(settings):
        app.add_middleware(PrometheusMiddleware, registry=prometheus_client.REGISTRY)
        app.mount(
            settings.metrics.path,
            prometheus_client.make_asgi_app(registry=prometheus_client.REGISTRY),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return the backend health status."""
        return {"status": "ok"}

    @app.get("/api/events/stream")
    async def events_stream() -> StreamingResponse:
        """Stream live monitor events for the frontend."""

        async def _stream() -> AsyncIterator[str]:
            async for message in sse_fanout.subscribe():
                yield message

        return StreamingResponse(_stream(), media_type="text/event-stream")

    @app.post("/api/monitor/reset")
    async def reset_monitor() -> dict[str, int]:
        """Clear retained monitor data without touching historical totals."""
        result = monitor_admin.reset()
        return {
            "removedTasks": result.removed_tasks,
            "removedWorkers": result.removed_workers,
            "removedQueues": result.removed_queues,
            "removedRawEvents": result.removed_raw_events,
        }

    @app.delete("/api/monitor/tasks")
    async def remove_monitored_tasks(payload: MonitorIdsPayload = Body(...)) -> dict[str, object]:
        """Remove retained task families from the monitor only."""
        result = monitor_admin.remove_task_families(payload.ids)
        return {
            "removedCount": result.removed_count,
            "removedIds": list(result.removed_ids),
        }

    @app.delete("/api/monitor/schedules")
    async def remove_monitored_schedules(payload: MonitorIdsPayload = Body(...)) -> dict[str, object]:
        """Remove retained schedule runs from the monitor only."""
        result = monitor_admin.remove_schedules(payload.ids)
        return {
            "removedCount": result.removed_count,
            "removedIds": list(result.removed_ids),
        }

    _mount_frontend(app)

    app.state.runtime_settings = settings
    app.state.raw_event_store = raw_event_store
    app.state.event_counter_store = event_counter_store
    app.state.task_repository = task_repository
    app.state.completed_task_repository = completed_task_repository
    app.state.task_read_repository = task_read_repository
    app.state.task_projector = task_projector
    app.state.schedule_repository = schedule_repository
    app.state.schedule_projector = schedule_projector
    app.state.worker_repository = worker_repository
    app.state.worker_projector = worker_projector
    app.state.queue_repository = queue_repository
    app.state.queue_projector = queue_projector
    app.state.event_dispatcher = event_dispatcher
    app.state.sse_fanout = sse_fanout
    app.state.runtime_metrics_adapter = runtime_metrics_adapter
    app.state.monitor_metrics_adapter = monitor_metrics_adapter
    app.state.celery_event_consumer = consumer
    app.state.task_liveness_reconciler = task_liveness_reconciler
    app.state.monitor_admin = monitor_admin
    return app


def _runtime_module(
    *,
    settings: RuntimeSettings,
    raw_event_store: RawEventStore,
    event_counter_store: EventCounterStore,
) -> Callable[[LoomContainer], None]:
    """Build the DI registration module for monitor runtime singletons."""

    repository_module = build_repository_registration_module(
        models=(),
        explicit_models=(TaskSnapshot, ScheduleRunSnapshot, WorkerSnapshot, QueueSnapshot),
        build_registered_repository=_build_registered_repository,
    )

    def _module(container: LoomContainer) -> None:
        container.register_instance(RuntimeSettings, settings)
        container.register_instance(RawEventStore, raw_event_store)
        container.register_instance(EventCounterStore, event_counter_store)
        container.register_instance(DefaultRepositoryBuilder, build_plywatch_default_repository)
        repository_module(container)
        live_repository = container.resolve(TaskSnapshotRepository)
        completed_repository = InMemoryCompletedTaskSnapshotRepository.from_settings(settings)
        container.register_instance(CompletedTaskSnapshotRepository, completed_repository)
        container.register_instance(
            TaskReadRepository,
            UnifiedTaskReadRepository(
                live_repository=live_repository,
                completed_repository=completed_repository,
            ),
        )

    return _module


def _build_registered_repository(
    context: RepositoryBuildContext,
    registration: RepositoryRegistration,
) -> Any:
    """Build one registered monitor repository for a logical Loom struct."""
    if registration.builder is not None:
        return registration.builder(context)

    repository_type = registration.repository_type
    if isinstance(repository_type, type):
        return repository_type()
    raise RuntimeError(
        "Plywatch repository registration requires either a builder or a class "
        f"type, got {repository_type!r}."
    )


def build_plywatch_default_repository(context: RepositoryBuildContext) -> Any:
    """Build the app-specific default repository.

    Plywatch is projection-driven and currently expects explicit repository
    registrations for its logical models. Persistible BaseModel defaults are
    not used yet in this app.
    """
    raise RuntimeError(
        "Plywatch has no default repository for persistible model "
        f"{context.model.__qualname__}; register an explicit repository_for(...) builder."
    )


def _build_frontend_events(
    event: Any,
    *,
    task_exists_before: bool,
    worker_exists_before: bool,
    task_repository: TaskSnapshotRepository,
) -> tuple[dict[str, object], ...]:
    """Convert one raw monitor event into frontend-oriented SSE messages."""
    event_type = str(getattr(event, "event_type", "unknown"))
    payload = getattr(event, "payload", {})
    task_id = getattr(event, "uuid", None)
    queue_name = payload.get("queue") if isinstance(payload, dict) else None
    task_name = payload.get("name") if isinstance(payload, dict) else None

    if event_type.startswith("task-") and task_id is not None:
        snapshot = task_repository.get(task_id)
        if snapshot is not None:
            queue_name = snapshot.queue or queue_name
            task_name = snapshot.name or task_name
        return (
            {
                "type": "task.updated" if task_exists_before else "task.created",
                "eventType": event_type,
                "taskId": task_id,
                "workerHostname": getattr(event, "hostname", None),
                "queueName": queue_name,
                "capturedAt": getattr(event, "captured_at", None),
                "taskName": task_name,
            },
            {
                "type": "queue.updated",
                "eventType": event_type,
                "taskId": task_id,
                "workerHostname": getattr(event, "hostname", None),
                "queueName": queue_name,
                "capturedAt": getattr(event, "captured_at", None),
                "taskName": task_name,
            },
        )

    if event_type.startswith("worker-"):
        return (
            {
                "type": "worker.updated" if worker_exists_before else "worker.created",
                "eventType": event_type,
                "taskId": task_id,
                "workerHostname": getattr(event, "hostname", None),
                "queueName": queue_name,
                "capturedAt": getattr(event, "captured_at", None),
                "taskName": task_name,
            },
        )

    return (
        {
            "type": "raw.event",
            "eventType": event_type,
            "taskId": task_id,
            "workerHostname": getattr(event, "hostname", None),
            "queueName": queue_name,
            "capturedAt": getattr(event, "captured_at", None),
            "taskName": task_name,
        },
    )


def _build_metrics_adapters(
    settings: RuntimeSettings,
) -> tuple[MetricsAdapter | None, MonitorMetricsAdapter | None]:
    """Build runtime and monitor metrics adapters from app settings."""
    if not settings.metrics.enabled:
        return None, None

    runtime_adapters: list[MetricsAdapter] = []
    monitor_adapters: list[MonitorMetricsAdapter] = []

    for adapter_name in settings.metrics.adapters:
        if adapter_name == "prometheus":
            runtime_adapters.append(build_prometheus_runtime_adapter(registry=prometheus_client.REGISTRY))
            monitor_adapters.append(build_prometheus_monitor_adapter(registry=prometheus_client.REGISTRY))
            continue
        raise RuntimeError(
            f"Unsupported Plywatch metrics adapter {adapter_name!r}. "
            "Supported adapters: ('prometheus',)."
        )

    runtime_adapter: MetricsAdapter | None
    if not runtime_adapters:
        runtime_adapter = None
    elif len(runtime_adapters) == 1:
        runtime_adapter = runtime_adapters[0]
    else:
        runtime_adapter = CompositeRuntimeMetricsAdapter(tuple(runtime_adapters))

    monitor_adapter: MonitorMetricsAdapter | None
    if not monitor_adapters:
        monitor_adapter = None
    elif len(monitor_adapters) == 1:
        monitor_adapter = monitor_adapters[0]
    else:
        monitor_adapter = CompositeMonitorMetricsAdapter(tuple(monitor_adapters))

    return runtime_adapter, monitor_adapter


def _prometheus_metrics_enabled(settings: RuntimeSettings) -> bool:
    """Return whether Prometheus exposition is enabled for this app."""
    return settings.metrics.enabled and "prometheus" in settings.metrics.adapters


def _mount_frontend(app: FastAPI) -> None:
    """Mount the compiled Svelte frontend when the build output exists."""
    build_dir = Path(__file__).resolve().parents[4] / "apps" / "web" / "build"
    index_path = build_dir / "index.html"
    if not index_path.exists():
        return

    assets_dir = build_dir / "_app"
    if assets_dir.exists():
        app.mount("/_app", StaticFiles(directory=assets_dir), name="frontend-app-assets")

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend_path(path: str) -> FileResponse:
        candidate = build_dir / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


app = create_app()

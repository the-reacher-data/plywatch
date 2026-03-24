"""ASGI entrypoint for the Plywatch backend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
import contextlib
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Annotated, Any

import prometheus_client
from pydantic import BaseModel
from fastapi import Body, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
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
from plywatch.shared.frontend_events import (
    build_frontend_events,
    task_exists_before_event,
    task_lost_message,
    worker_exists_before_event,
)
from plywatch.shared.monitor_metrics import (
    CompositeMonitorMetricsAdapter,
    CompositeRuntimeMetricsAdapter,
    MonitorMetricsAdapter,
    MonitorMetricsContext,
    MONITOR_METRICS_ADAPTER_PROMETHEUS,
)
from plywatch.shared.prometheus_monitor_adapter import (
    build_prometheus_monitor_adapter,
    build_prometheus_runtime_adapter,
)
from plywatch.shared.raw_events import EventCounterStore, RawCeleryEvent, RawEventStore
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


@dataclass(frozen=True)
class MonitorRuntime:
    """In-memory runtime collaborators wired into the FastAPI app."""

    settings: RuntimeSettings
    kernel: Any
    raw_event_store: RawEventStore
    event_counter_store: EventCounterStore
    sse_fanout: SseFanout
    runtime_metrics_adapter: MetricsAdapter | None
    monitor_metrics_adapter: MonitorMetricsAdapter | None
    task_repository: TaskSnapshotRepository
    completed_task_repository: CompletedTaskSnapshotRepository
    task_read_repository: TaskReadRepository
    worker_repository: WorkerSnapshotRepository
    queue_repository: QueueSnapshotRepository
    schedule_repository: ScheduleRunSnapshotRepository
    task_projector: TaskProjector
    worker_projector: WorkerProjector
    queue_projector: QueueProjector
    schedule_projector: ScheduleProjector
    event_dispatcher: EventDispatcher
    consumer: CeleryEventConsumer
    task_liveness_reconciler: TaskLivenessReconciler
    monitor_admin: MonitorAdminService


def create_app(*, start_consumer: bool = True) -> FastAPI:
    """Create the Plywatch API using Loom use cases and REST interfaces.

    Args:
        start_consumer: Whether to start the background Celery event consumer.
            Tests can disable this and feed events directly into the projector.

    Returns:
        A configured FastAPI application.
    """
    runtime = _build_monitor_runtime()
    app = create_fastapi_app(
        runtime.kernel,
        interfaces=(
            MonitorRestInterface,
            TaskRestInterface,
            TaskSectionsRestInterface,
            ScheduleRestInterface,
            WorkerRestInterface,
            QueueRestInterface,
        ),
        defaults=RestApiDefaults(pagination_mode=PaginationMode.CURSOR),
        title=runtime.settings.app.rest.title,
        version=runtime.settings.app.rest.version,
        docs_url=runtime.settings.app.rest.docs_url,
        redoc_url=runtime.settings.app.rest.redoc_url,
        lifespan=_build_lifespan(runtime, start_consumer=start_consumer),
    )
    _configure_app_middleware(app, runtime.settings)
    _register_operational_routes(app, runtime)
    _mount_frontend(app, runtime.settings)
    _attach_runtime_state(app, runtime)
    return app


def _build_monitor_runtime() -> MonitorRuntime:
    """Construct and wire the backend runtime dependencies."""
    settings = load_runtime_settings()
    _configure_app_logging(settings)
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
    repositories = _resolve_runtime_repositories(kernel)
    projectors = _build_runtime_projectors(repositories)
    event_dispatcher = EventDispatcher()
    event_dispatcher.register_many(projectors)
    celery_app = create_celery_app(settings.celery)
    consumer = CeleryEventConsumer(
        celery_app,
        raw_event_store,
        event_counter_store,
        buffer_excluded_event_types=settings.raw_event_buffer_excluded_types,
        on_event=_build_event_handler(
            repositories=repositories,
            event_dispatcher=event_dispatcher,
            raw_event_store=raw_event_store,
            worker_repository=repositories.worker_repository,
            queue_repository=repositories.queue_repository,
            sse_fanout=sse_fanout,
            monitor_metrics_adapter=monitor_metrics_adapter,
        ),
    )
    task_liveness_reconciler = TaskLivenessReconciler(
        task_repository=repositories.task_repository,
        completed_task_repository=repositories.completed_task_repository,
        queue_repository=repositories.queue_repository,
        presence_gateway=CeleryTaskExecutionPresenceGateway(celery_app),
        lost_after_seconds=settings.task_lost_after_seconds,
    )
    monitor_admin = MonitorAdminService(
        task_repository=repositories.task_repository,
        completed_task_repository=repositories.completed_task_repository,
        worker_repository=repositories.worker_repository,
        queue_repository=repositories.queue_repository,
        schedule_repository=repositories.schedule_repository,
        raw_event_store=raw_event_store,
    )
    return MonitorRuntime(
        settings=settings,
        kernel=kernel,
        raw_event_store=raw_event_store,
        event_counter_store=event_counter_store,
        sse_fanout=sse_fanout,
        runtime_metrics_adapter=runtime_metrics_adapter,
        monitor_metrics_adapter=monitor_metrics_adapter,
        task_repository=repositories.task_repository,
        completed_task_repository=repositories.completed_task_repository,
        task_read_repository=repositories.task_read_repository,
        worker_repository=repositories.worker_repository,
        queue_repository=repositories.queue_repository,
        schedule_repository=repositories.schedule_repository,
        task_projector=projectors[0],
        worker_projector=projectors[1],
        queue_projector=projectors[2],
        schedule_projector=projectors[3],
        event_dispatcher=event_dispatcher,
        consumer=consumer,
        task_liveness_reconciler=task_liveness_reconciler,
        monitor_admin=monitor_admin,
    )


@dataclass(frozen=True)
class RuntimeRepositories:
    """Repository dependencies resolved from the kernel container."""

    task_repository: TaskSnapshotRepository
    completed_task_repository: CompletedTaskSnapshotRepository
    task_read_repository: TaskReadRepository
    worker_repository: WorkerSnapshotRepository
    queue_repository: QueueSnapshotRepository
    schedule_repository: ScheduleRunSnapshotRepository


def _resolve_runtime_repositories(kernel: Any) -> RuntimeRepositories:
    """Resolve the repositories needed by runtime projectors and services."""
    return RuntimeRepositories(
        task_repository=kernel.container.resolve(TaskSnapshotRepository),
        completed_task_repository=kernel.container.resolve(CompletedTaskSnapshotRepository),
        task_read_repository=kernel.container.resolve(TaskReadRepository),
        worker_repository=kernel.container.resolve(WorkerSnapshotRepository),
        queue_repository=kernel.container.resolve(QueueSnapshotRepository),
        schedule_repository=kernel.container.resolve(ScheduleRunSnapshotRepository),
    )


def _build_runtime_projectors(
    repositories: RuntimeRepositories,
) -> tuple[TaskProjector, WorkerProjector, QueueProjector, ScheduleProjector]:
    """Create the projector set that reacts to incoming Celery events."""
    return (
        TaskProjector(repositories.task_repository, repositories.completed_task_repository),
        WorkerProjector(repositories.worker_repository),
        QueueProjector(repositories.queue_repository),
        ScheduleProjector(repositories.schedule_repository),
    )


def _configure_app_logging(settings: RuntimeSettings) -> None:
    """Apply logger settings from runtime configuration."""
    configure_logging_from_values(
        name=settings.logger.name,
        environment=settings.logger.environment,
        renderer=settings.logger.renderer,
        colors=settings.logger.colors,
        level=settings.logger.level,
        named_levels=settings.logger.named_levels,
        handlers=settings.logger.handlers,
    )


def _build_event_handler(
    *,
    repositories: RuntimeRepositories,
    event_dispatcher: EventDispatcher,
    raw_event_store: RawEventStore,
    worker_repository: WorkerSnapshotRepository,
    queue_repository: QueueSnapshotRepository,
    sse_fanout: SseFanout,
    monitor_metrics_adapter: MonitorMetricsAdapter | None,
) -> Callable[[RawCeleryEvent], None]:
    """Create the event callback used by the Celery event consumer."""

    def _on_event(event: RawCeleryEvent) -> None:
        task_exists_before = task_exists_before_event(event, repositories.task_repository)
        worker_exists_before = worker_exists_before_event(event, worker_repository)
        event_dispatcher.dispatch(event)
        _record_monitor_projection_metrics(
            event=event,
            monitor_metrics_adapter=monitor_metrics_adapter,
            raw_event_store=raw_event_store,
            task_repository=repositories.task_repository,
            worker_repository=worker_repository,
            queue_repository=queue_repository,
        )
        _publish_frontend_events(
            event=event,
            sse_fanout=sse_fanout,
            task_exists_before=task_exists_before,
            worker_exists_before=worker_exists_before,
            task_repository=repositories.task_repository,
        )

    return _on_event


def _record_monitor_projection_metrics(
    *,
    event: RawCeleryEvent,
    monitor_metrics_adapter: MonitorMetricsAdapter | None,
    raw_event_store: RawEventStore,
    task_repository: TaskSnapshotRepository,
    worker_repository: WorkerSnapshotRepository,
    queue_repository: QueueSnapshotRepository,
) -> None:
    """Record monitor-specific metrics for one projected event when enabled."""
    if monitor_metrics_adapter is None:
        return
    monitor_metrics_adapter.record_projection_event(
        event,
        context=MonitorMetricsContext(
            raw_event_store=raw_event_store,
            task_repository=task_repository,
            worker_repository=worker_repository,
            queue_repository=queue_repository,
        ),
    )


def _publish_frontend_events(
    *,
    event: RawCeleryEvent,
    sse_fanout: SseFanout,
    task_exists_before: bool,
    worker_exists_before: bool,
    task_repository: TaskSnapshotRepository,
) -> None:
    """Push the derived frontend SSE messages for one projected event."""
    for message in build_frontend_events(
        event,
        task_exists_before=task_exists_before,
        worker_exists_before=worker_exists_before,
        task_repository=task_repository,
    ):
        sse_fanout.publish(message)


def _build_lifespan(
    runtime: MonitorRuntime,
    *,
    start_consumer: bool,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Create the FastAPI lifespan handler for background runtime services."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime.sse_fanout.attach_loop(asyncio.get_running_loop())
        reconcile_task: asyncio.Task[None] | None = None
        if start_consumer:
            runtime.consumer.start()
            if runtime.settings.task_liveness_reconcile_interval_seconds > 0:
                reconcile_task = asyncio.create_task(_reconcile_lost_tasks_loop(runtime))
        try:
            yield
        finally:
            if reconcile_task is not None:
                reconcile_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reconcile_task
            if start_consumer:
                runtime.consumer.stop()

    return lifespan


async def _reconcile_lost_tasks_loop(runtime: MonitorRuntime) -> None:
    """Periodically reconcile tasks that disappeared from Celery workers."""
    interval = runtime.settings.task_liveness_reconcile_interval_seconds
    if interval <= 0:
        return
    while True:
        await asyncio.sleep(interval)
        try:
            result = runtime.task_liveness_reconciler.reconcile()
        except Exception:
            logger.exception("Task liveness reconciliation failed")
            continue
        for task_id in result.updated_task_ids:
            runtime.sse_fanout.publish(task_lost_message(task_id))


def _configure_app_middleware(app: FastAPI, settings: RuntimeSettings) -> None:
    """Apply optional middleware and metrics exposition to the app."""
    if settings.trace.enabled:
        app.add_middleware(TraceIdMiddleware, header=settings.trace.header)
    if not _prometheus_metrics_enabled(settings):
        return
    metrics_path = settings.metrics.path.rstrip("/") or "/metrics"
    app.add_middleware(PrometheusMiddleware, registry=prometheus_client.REGISTRY)

    @app.get(metrics_path, include_in_schema=False)
    async def metrics_without_trailing_slash() -> Response:
        return Response(
            content=prometheus_client.generate_latest(prometheus_client.REGISTRY),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get(
        metrics_path + "/",
        include_in_schema=False,
        responses={404: {"description": "Not Found"}},
    )
    async def metrics_with_trailing_slash() -> None:
        raise HTTPException(status_code=404, detail="Not Found")


def _register_operational_routes(app: FastAPI, runtime: MonitorRuntime) -> None:
    """Register health, SSE, and monitor admin endpoints."""

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return the backend health status."""
        return {"status": "ok"}

    @app.get("/api/events/stream")
    async def events_stream() -> StreamingResponse:
        """Stream live monitor events for the frontend."""
        return StreamingResponse(_stream_frontend_events(runtime.sse_fanout), media_type="text/event-stream")

    @app.post("/api/monitor/reset")
    async def reset_monitor() -> dict[str, int]:
        """Clear retained monitor data without touching historical totals."""
        result = runtime.monitor_admin.reset()
        return {
            "removedTasks": result.removed_tasks,
            "removedWorkers": result.removed_workers,
            "removedQueues": result.removed_queues,
            "removedRawEvents": result.removed_raw_events,
        }

    @app.delete("/api/monitor/tasks")
    async def remove_monitored_tasks(
        payload: Annotated[MonitorIdsPayload, Body(...)],
    ) -> dict[str, object]:
        """Remove retained task families from the monitor only."""
        result = runtime.monitor_admin.remove_task_families(payload.ids)
        return {
            "removedCount": result.removed_count,
            "removedIds": list(result.removed_ids),
        }

    @app.delete("/api/monitor/schedules")
    async def remove_monitored_schedules(
        payload: Annotated[MonitorIdsPayload, Body(...)],
    ) -> dict[str, object]:
        """Remove retained schedule runs from the monitor only."""
        result = runtime.monitor_admin.remove_schedules(payload.ids)
        return {
            "removedCount": result.removed_count,
            "removedIds": list(result.removed_ids),
        }


async def _stream_frontend_events(sse_fanout: SseFanout) -> AsyncIterator[str]:
    """Yield SSE messages from the in-memory fanout."""
    async for message in sse_fanout.subscribe():
        yield message


def _attach_runtime_state(app: FastAPI, runtime: MonitorRuntime) -> None:
    """Expose runtime collaborators on app.state for tests and integrations."""
    app.state.runtime_settings = runtime.settings
    app.state.raw_event_store = runtime.raw_event_store
    app.state.event_counter_store = runtime.event_counter_store
    app.state.task_repository = runtime.task_repository
    app.state.completed_task_repository = runtime.completed_task_repository
    app.state.task_read_repository = runtime.task_read_repository
    app.state.task_projector = runtime.task_projector
    app.state.schedule_repository = runtime.schedule_repository
    app.state.schedule_projector = runtime.schedule_projector
    app.state.worker_repository = runtime.worker_repository
    app.state.worker_projector = runtime.worker_projector
    app.state.queue_repository = runtime.queue_repository
    app.state.queue_projector = runtime.queue_projector
    app.state.event_dispatcher = runtime.event_dispatcher
    app.state.sse_fanout = runtime.sse_fanout
    app.state.runtime_metrics_adapter = runtime.runtime_metrics_adapter
    app.state.monitor_metrics_adapter = runtime.monitor_metrics_adapter
    app.state.celery_event_consumer = runtime.consumer
    app.state.task_liveness_reconciler = runtime.task_liveness_reconciler
    app.state.monitor_admin = runtime.monitor_admin


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


def _build_metrics_adapters(
    settings: RuntimeSettings,
) -> tuple[MetricsAdapter | None, MonitorMetricsAdapter | None]:
    """Build runtime and monitor metrics adapters from app settings."""
    if not settings.metrics.enabled:
        return None, None

    runtime_adapters: list[MetricsAdapter] = []
    monitor_adapters: list[MonitorMetricsAdapter] = []

    for adapter_name in settings.metrics.adapters:
        if adapter_name == MONITOR_METRICS_ADAPTER_PROMETHEUS:
            runtime_adapters.append(build_prometheus_runtime_adapter(registry=prometheus_client.REGISTRY))
            monitor_adapters.append(
                build_prometheus_monitor_adapter(
                    registry=prometheus_client.REGISTRY,
                    enable_flower_compat=settings.metrics.flower_compat_enabled,
                )
            )
            continue
        raise RuntimeError(
            f"Unsupported Plywatch metrics adapter {adapter_name!r}. "
            f"Supported adapters: ({MONITOR_METRICS_ADAPTER_PROMETHEUS!r},)."
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
    return settings.metrics.enabled and MONITOR_METRICS_ADAPTER_PROMETHEUS in settings.metrics.adapters


def _is_reserved_operational_path(path: str, *, metrics_path: str) -> bool:
    """Return whether one frontend fallback path is reserved for backend operations."""
    normalized = path.strip("/")
    if not normalized:
        return False

    if normalized == "api" or normalized.startswith("api/"):
        return True

    for reserved in ("health", "docs", "redoc", "openapi.json"):
        if normalized == reserved or normalized.startswith(f"{reserved}/"):
            return True

    normalized_metrics = metrics_path.strip("/")
    if normalized_metrics and (
        normalized == normalized_metrics or normalized.startswith(f"{normalized_metrics}/")
    ):
        return True
    return False


def _mount_frontend(app: FastAPI, settings: RuntimeSettings) -> None:
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

    @app.get(
        "/{path:path}",
        include_in_schema=False,
        responses={404: {"description": "Not Found"}},
    )
    async def frontend_path(path: str) -> FileResponse:
        if _is_reserved_operational_path(path, metrics_path=settings.metrics.path):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = build_dir / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


app = create_app()

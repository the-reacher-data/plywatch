"""Monitor read use cases exposed by the Plywatch API."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from loom.core.repository.abc.query import QuerySpec
from loom.core.use_case.use_case import UseCase

from plywatch.monitor.contracts import OverviewResponse, RawEventsResponse, RawEventView
from plywatch.task.families import build_section_counts
from plywatch.task.read_repository import TaskReadRepository
from plywatch.shared.raw_events import EventCounterStore, RawEventStore
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.queue.repository import QueueSnapshotRepository
from plywatch.task.policies import is_future_scheduled_task
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.worker.repository import WorkerSnapshotRepository


class GetOverviewUseCase(UseCase[object, OverviewResponse]):
    """Return a compact runtime overview for the monitor backend."""

    read_only = True

    def __init__(
        self,
        settings: RuntimeSettings,
        raw_event_store: RawEventStore,
        event_counter_store: EventCounterStore,
        task_repository: TaskSnapshotRepository,
        task_read_repository: TaskReadRepository,
        worker_repository: WorkerSnapshotRepository,
        queue_repository: QueueSnapshotRepository,
    ) -> None:
        self._settings = settings
        self._raw_event_store = raw_event_store
        self._event_counter_store = event_counter_store
        self._task_repository = task_repository
        self._task_read_repository = task_read_repository
        self._worker_repository = worker_repository
        self._queue_repository = queue_repository

    async def execute(self) -> OverviewResponse:
        """Return the monitor runtime overview."""
        heartbeat_event_count = self._event_counter_store.count_for("worker-heartbeat")
        visible_snapshots = [
            snapshot for snapshot in self._task_read_repository.list_all() if not is_future_scheduled_task(snapshot)
        ]
        visible_task_count = build_section_counts(visible_snapshots).family_count
        return OverviewResponse(
            product="plywatch",
            version=self._settings.app.rest.version,
            config_path=self._settings.config_paths[0],
            broker_url=_redact_connection_url(self._settings.celery.broker_url),
            raw_event_limit=self._settings.raw_event_limit,
            raw_event_count=self._raw_event_store.count(),
            buffered_event_count=self._raw_event_store.count(),
            total_event_count=self._event_counter_store.total_count() - heartbeat_event_count,
            heartbeat_event_count=heartbeat_event_count,
            task_count=visible_task_count,
            worker_count=self._worker_repository.count(),
            queue_count=self._queue_repository.count(),
            max_tasks=self._task_repository.max_tasks(),
            max_age_seconds=self._task_repository.max_age_seconds(),
            mode="monitor-backend",
        )


class ListRawEventsUseCase(UseCase[object, RawEventsResponse]):
    """Return recent raw Celery events for debugging and modeling."""

    read_only = True

    def __init__(self, raw_event_store: RawEventStore) -> None:
        self._raw_event_store = raw_event_store

    async def execute(self, query: QuerySpec) -> RawEventsResponse:
        """Return recent raw Celery events.

        Args:
            query: Query options resolved from the request.

        Returns:
            A raw event response.
        """
        limit = query.limit if query.limit is not None else 50
        items = self._raw_event_store.list_recent(limit)
        return RawEventsResponse(
            items=tuple(
                RawEventView(
                    captured_at=item.captured_at,
                    event_type=item.event_type,
                    uuid=item.uuid,
                    hostname=item.hostname,
                    payload=item.payload,
                )
                for item in items
            ),
            count=self._raw_event_store.count(),
            limit=limit,
        )


def _redact_connection_url(url: str) -> str:
    """Redact sensitive URL parts while keeping it operationally readable."""
    parsed = urlsplit(url)
    if parsed.scheme == "":
        return "***redacted***"

    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    port = f":{parsed.port}" if parsed.port is not None else ""

    userinfo = ""
    if parsed.username is not None:
        if parsed.password is not None:
            userinfo = f"{parsed.username}:***@"
        else:
            userinfo = f"{parsed.username}@"
    elif parsed.password is not None:
        userinfo = "***@"

    safe_query = ""
    if parsed.query:
        safe_query = urlencode(
            [(key, "***") for key, _ in parse_qsl(parsed.query, keep_blank_values=True)],
            doseq=True,
        )

    return urlunsplit(
        (
            parsed.scheme,
            f"{userinfo}{hostname}{port}",
            parsed.path,
            safe_query,
            "",
        )
    )

"""Worker snapshot repository contracts and in-memory implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from loom.core.repository import RepositoryBuildContext, repository_for
from plywatch.shared.runtime_config import RuntimeSettings
from plywatch.shared.in_memory_projection_repository import (
    InMemoryProjectionRepository,
    _parse_iso8601,
)
from plywatch.worker.models import WorkerSnapshot


class WorkerSnapshotRepository(Protocol):
    """Read/write repository for consolidated worker snapshots."""

    def upsert(self, snapshot: WorkerSnapshot) -> None:
        """Insert or replace one worker snapshot."""
        ...

    def get(self, hostname: str) -> WorkerSnapshot | None:
        """Return one worker snapshot by hostname."""
        ...

    def list_recent(self, limit: int) -> list[WorkerSnapshot]:
        """Return workers ordered by latest activity."""
        ...

    def count(self) -> int:
        """Return the number of tracked worker snapshots."""
        ...

    def mark_stale(self) -> None:
        """Derive stale states from the heartbeat timeout policy."""
        ...

    def clear(self) -> int:
        """Remove all retained worker snapshots and return the removed count."""
        ...


def build_worker_snapshot_repository(context: RepositoryBuildContext) -> WorkerSnapshotRepository:
    """Build the worker snapshot repository for the current app runtime."""
    if context.container is None:
        raise RuntimeError("Worker snapshot repository requires a DI container")
    settings = context.container.resolve(RuntimeSettings)
    return InMemoryWorkerSnapshotRepository(
        max_age_seconds=settings.max_age_seconds,
        stale_after_seconds=settings.worker_stale_after_seconds,
    )


@repository_for(WorkerSnapshot, builder=build_worker_snapshot_repository)
class InMemoryWorkerSnapshotRepository(
    InMemoryProjectionRepository[str, WorkerSnapshot],
    WorkerSnapshotRepository,
):
    """Thread-safe in-memory repository for worker snapshots."""

    def __init__(self, *, max_age_seconds: int, stale_after_seconds: int) -> None:
        super().__init__(
            max_age_seconds=max_age_seconds,
            get_last_seen_at=lambda item: item.last_seen_at,
        )
        self._stale_after_seconds = stale_after_seconds

    def upsert(self, snapshot: WorkerSnapshot) -> None:
        """Insert or replace one worker snapshot."""
        with self._lock:
            self._upsert_locked(snapshot.hostname, snapshot)
            self._prune_locked()

    def get(self, hostname: str) -> WorkerSnapshot | None:
        """Return one worker snapshot by hostname."""
        with self._lock:
            snapshot = self._get_locked(hostname)
        return self._with_derived_state(snapshot)

    def list_recent(self, limit: int) -> list[WorkerSnapshot]:
        """Return workers ordered by latest activity."""
        self.mark_stale()
        with self._lock:
            items = [item for item in (self._with_derived_state(entry) for entry in self._list_locked()) if item is not None]
        items.sort(key=lambda item: item.last_seen_at, reverse=True)
        return items[:limit]

    def mark_stale(self) -> None:
        """Derive stale states from the heartbeat timeout policy."""
        with self._lock:
            for snapshot in self._items.values():
                if snapshot.state == "offline":
                    continue
                if _is_stale(snapshot.last_seen_at, self._stale_after_seconds):
                    snapshot.state = "stale"
            self._prune_locked()

    def _with_derived_state(self, snapshot: WorkerSnapshot | None) -> WorkerSnapshot | None:
        if snapshot is None:
            return None
        if snapshot.state != "offline" and _is_stale(snapshot.last_seen_at, self._stale_after_seconds):
            snapshot.state = "stale"
        return snapshot

    def clear(self) -> int:
        """Remove all retained worker snapshots and return the removed count."""
        with self._lock:
            removed = len(self._items)
            self._items.clear()
        return removed


def _is_stale(last_seen_at: str, stale_after_seconds: int) -> bool:
    if stale_after_seconds <= 0:
        return False
    return _parse_iso8601(last_seen_at) < (datetime.now(UTC) - timedelta(seconds=stale_after_seconds))

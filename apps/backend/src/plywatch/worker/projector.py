"""Worker projection reducer fed by raw Celery worker events."""

from __future__ import annotations

from collections.abc import Collection

from plywatch.shared.raw_events import JsonValue, RawCeleryEvent
from plywatch.worker.constants import (
    WORKER_EVENT_HEARTBEAT,
    WORKER_EVENT_OFFLINE,
    WORKER_EVENT_ONLINE,
    WORKER_EVENT_TYPES,
    WORKER_STATE_OFFLINE,
    WORKER_STATE_ONLINE,
)
from plywatch.worker.models import WorkerSnapshot
from plywatch.worker.repository import WorkerSnapshotRepository


class WorkerProjector:
    """Build consolidated worker snapshots from raw Celery worker events."""

    @property
    def handled_event_types(self) -> Collection[str]:
        return WORKER_EVENT_TYPES

    def __init__(self, repository: WorkerSnapshotRepository) -> None:
        self._repository = repository

    def apply(self, event: RawCeleryEvent) -> None:
        """Update the worker projection when one worker event arrives."""
        if event.event_type not in WORKER_EVENT_TYPES or event.hostname is None:
            return

        current = self._repository.get(event.hostname)
        snapshot = current if current is not None else self._create_snapshot(event)
        snapshot.last_seen_at = event.captured_at
        if not snapshot.first_seen_at:
            snapshot.first_seen_at = event.captured_at

        _TRANSITION_HANDLERS[event.event_type](snapshot, event.captured_at)

        self._merge_runtime_fields(snapshot, event.payload)
        self._repository.upsert(snapshot)

    def _create_snapshot(self, event: RawCeleryEvent) -> WorkerSnapshot:
        return WorkerSnapshot(
            hostname=event.hostname or "unknown",
            first_seen_at=event.captured_at,
            last_seen_at=event.captured_at,
        )

    def _merge_runtime_fields(self, snapshot: WorkerSnapshot, payload: dict[str, JsonValue]) -> None:
        snapshot.pid = _int_value(payload.get("pid"), snapshot.pid)
        snapshot.clock = _int_value(payload.get("clock"), snapshot.clock)
        snapshot.freq = _float_value(payload.get("freq"), snapshot.freq)
        snapshot.active = _int_value(payload.get("active"), snapshot.active)
        snapshot.processed = _int_value(payload.get("processed"), snapshot.processed)
        snapshot.loadavg = _float_tuple(payload.get("loadavg"), snapshot.loadavg)
        snapshot.sw_ident = _string_value(payload.get("sw_ident"), snapshot.sw_ident)
        snapshot.sw_ver = _string_value(payload.get("sw_ver"), snapshot.sw_ver)
        snapshot.sw_sys = _string_value(payload.get("sw_sys"), snapshot.sw_sys)


def _int_value(value: JsonValue | None, current: int | None) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else current


def _float_value(value: JsonValue | None, current: float | None) -> float | None:
    if isinstance(value, bool):
        return current
    if isinstance(value, (int, float)):
        return float(value)
    return current


def _float_tuple(value: JsonValue | None, current: tuple[float, ...]) -> tuple[float, ...]:
    if not isinstance(value, list):
        return current
    items: list[float] = []
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            items.append(float(item))
    return tuple(items) if items else current


def _string_value(value: JsonValue | None, current: str | None) -> str | None:
    return value if isinstance(value, str) else current


def _mark_online(snapshot: WorkerSnapshot, captured_at: str) -> None:
    snapshot.state = WORKER_STATE_ONLINE
    snapshot.online_at = captured_at
    snapshot.offline_at = None


def _mark_offline(snapshot: WorkerSnapshot, captured_at: str) -> None:
    snapshot.state = WORKER_STATE_OFFLINE
    snapshot.offline_at = captured_at


def _apply_heartbeat(snapshot: WorkerSnapshot, captured_at: str) -> None:
    snapshot.last_heartbeat_at = captured_at
    if snapshot.state != WORKER_STATE_OFFLINE:
        snapshot.state = WORKER_STATE_ONLINE


_TRANSITION_HANDLERS = {
    WORKER_EVENT_ONLINE: _mark_online,
    WORKER_EVENT_HEARTBEAT: _apply_heartbeat,
    WORKER_EVENT_OFFLINE: _mark_offline,
}

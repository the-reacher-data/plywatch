"""Worker projection models used by Plywatch."""

from __future__ import annotations

import msgspec
from loom.core.model import LoomStruct
from loom.core.response import Response

from plywatch.worker.constants import WorkerStateName

WorkerState = WorkerStateName


class WorkerSnapshot(LoomStruct, kw_only=True):
    """Consolidated worker state derived from Celery worker events."""

    hostname: str
    state: WorkerState = "online"
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_heartbeat_at: str | None = None
    online_at: str | None = None
    offline_at: str | None = None
    pid: int | None = None
    clock: int | None = None
    freq: float | None = None
    active: int | None = None
    processed: int | None = None
    loadavg: tuple[float, ...] = msgspec.field(default_factory=tuple)
    sw_ident: str | None = None
    sw_ver: str | None = None
    sw_sys: str | None = None


class WorkerSummaryView(Response, frozen=True, kw_only=True):
    """Public summary view for one tracked Celery worker."""

    hostname: str
    state: str
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_heartbeat_at: str | None = None
    online_at: str | None = None
    offline_at: str | None = None
    pid: int | None = None
    clock: int | None = None
    freq: float | None = None
    active: int | None = None
    processed: int | None = None
    loadavg: tuple[float, ...] = ()
    sw_ident: str | None = None
    sw_ver: str | None = None
    sw_sys: str | None = None


class WorkersResponse(Response, frozen=True, kw_only=True):
    """Response containing tracked worker snapshots."""

    items: tuple[WorkerSummaryView, ...]
    count: int
    limit: int


def to_summary_view(snapshot: WorkerSnapshot) -> WorkerSummaryView:
    """Convert one worker snapshot into its public summary representation."""
    return WorkerSummaryView(
        hostname=snapshot.hostname,
        state=snapshot.state,
        first_seen_at=snapshot.first_seen_at,
        last_seen_at=snapshot.last_seen_at,
        last_heartbeat_at=snapshot.last_heartbeat_at,
        online_at=snapshot.online_at,
        offline_at=snapshot.offline_at,
        pid=snapshot.pid,
        clock=snapshot.clock,
        freq=snapshot.freq,
        active=snapshot.active,
        processed=snapshot.processed,
        loadavg=snapshot.loadavg,
        sw_ident=snapshot.sw_ident,
        sw_ver=snapshot.sw_ver,
        sw_sys=snapshot.sw_sys,
    )

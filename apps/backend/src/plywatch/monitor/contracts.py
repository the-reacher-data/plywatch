"""Public monitor response contracts."""

from __future__ import annotations

from loom.core.response import Response

from plywatch.shared.raw_events import JsonValue


class OverviewResponse(Response, frozen=True, kw_only=True):
    """High-level monitor runtime overview."""

    product: str
    version: str
    config_path: str
    broker_url: str
    raw_event_limit: int
    raw_event_count: int
    buffered_event_count: int
    total_event_count: int
    heartbeat_event_count: int
    task_count: int
    worker_count: int
    queue_count: int
    max_tasks: int
    max_age_seconds: int
    mode: str


class RawEventView(Response, frozen=True, kw_only=True):
    """Public raw Celery event view."""

    captured_at: str
    event_type: str
    payload: dict[str, JsonValue]
    uuid: str | None = None
    hostname: str | None = None


class RawEventsResponse(Response, frozen=True, kw_only=True):
    """Response containing recent raw Celery events."""

    items: tuple[RawEventView, ...]
    count: int
    limit: int

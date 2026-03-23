"""Queue projection models used by Plywatch."""

from __future__ import annotations

import msgspec
from loom.core.model import LoomStruct
from loom.core.response import Response


class QueueSnapshot(LoomStruct, kw_only=True):
    """Consolidated queue state derived from observed task events."""

    name: str
    routing_keys: list[str] = msgspec.field(default_factory=list)
    first_seen_at: str = ""
    last_seen_at: str = ""
    total_tasks: int = 0
    sent_count: int = 0
    active_count: int = 0
    retrying_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    historical_total_seen: int = 0
    historical_succeeded_count: int = 0
    historical_failed_count: int = 0
    historical_retried_count: int = 0
    queue_wait_total_ms: int = 0
    queue_wait_sample_count: int = 0
    start_delay_total_ms: int = 0
    start_delay_sample_count: int = 0
    run_duration_total_ms: int = 0
    run_duration_sample_count: int = 0
    end_to_end_total_ms: int = 0
    end_to_end_sample_count: int = 0


class QueueSummaryView(Response, frozen=True, kw_only=True):
    """Public summary view for one tracked queue."""

    name: str
    routing_keys: tuple[str, ...] = ()
    first_seen_at: str = ""
    last_seen_at: str = ""
    total_tasks: int = 0
    sent_count: int = 0
    active_count: int = 0
    retrying_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    historical_total_seen: int = 0
    historical_succeeded_count: int = 0
    historical_failed_count: int = 0
    historical_retried_count: int = 0
    avg_queue_wait_ms: int | None = None
    queue_wait_sample_count: int = 0
    avg_start_delay_ms: int | None = None
    start_delay_sample_count: int = 0
    avg_run_duration_ms: int | None = None
    run_duration_sample_count: int = 0
    avg_end_to_end_ms: int | None = None
    end_to_end_sample_count: int = 0


class QueuesResponse(Response, frozen=True, kw_only=True):
    """Response containing tracked queue snapshots."""

    items: tuple[QueueSummaryView, ...]
    count: int
    limit: int


def to_summary_view(snapshot: QueueSnapshot) -> QueueSummaryView:
    """Convert one queue snapshot into its public summary representation."""
    return QueueSummaryView(
        name=snapshot.name,
        routing_keys=tuple(snapshot.routing_keys),
        first_seen_at=snapshot.first_seen_at,
        last_seen_at=snapshot.last_seen_at,
        total_tasks=snapshot.total_tasks,
        sent_count=snapshot.sent_count,
        active_count=snapshot.active_count,
        retrying_count=snapshot.retrying_count,
        succeeded_count=snapshot.succeeded_count,
        failed_count=snapshot.failed_count,
        historical_total_seen=snapshot.historical_total_seen,
        historical_succeeded_count=snapshot.historical_succeeded_count,
        historical_failed_count=snapshot.historical_failed_count,
        historical_retried_count=snapshot.historical_retried_count,
        avg_queue_wait_ms=_average_ms(
            snapshot.queue_wait_total_ms,
            snapshot.queue_wait_sample_count,
        ),
        queue_wait_sample_count=snapshot.queue_wait_sample_count,
        avg_start_delay_ms=_average_ms(
            snapshot.start_delay_total_ms,
            snapshot.start_delay_sample_count,
        ),
        start_delay_sample_count=snapshot.start_delay_sample_count,
        avg_run_duration_ms=_average_ms(
            snapshot.run_duration_total_ms,
            snapshot.run_duration_sample_count,
        ),
        run_duration_sample_count=snapshot.run_duration_sample_count,
        avg_end_to_end_ms=_average_ms(
            snapshot.end_to_end_total_ms,
            snapshot.end_to_end_sample_count,
        ),
        end_to_end_sample_count=snapshot.end_to_end_sample_count,
    )


def _average_ms(total_ms: int, sample_count: int) -> int | None:
    if sample_count <= 0:
        return None
    return round(total_ms / sample_count)

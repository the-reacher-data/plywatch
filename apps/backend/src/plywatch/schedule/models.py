"""Schedule-oriented response models derived from observed task events."""

from __future__ import annotations

from collections.abc import Iterable

from loom.core.response import Response

from plywatch.schedule.repository import ScheduleRunSnapshot
from plywatch.shared.raw_events import JsonValue
from plywatch.task.models import TaskSummaryView, to_task_summary_payload
from plywatch.task.policies import is_future_scheduled_task, is_scheduled_task


class ScheduleSummaryView(Response, frozen=True, kw_only=True):
    """Public summary for one observed schedule and its recent executions."""

    schedule_id: str
    schedule_name: str
    schedule_pattern: str | None = None
    queue: str | None = None
    total_runs: int = 0
    pending_runs: int = 0
    queued_runs: int = 0
    running_runs: int = 0
    succeeded_runs: int = 0
    failed_runs: int = 0
    last_scheduled_for: str | None = None
    last_run_at: str | None = None
    pending_run_items: tuple[TaskSummaryView, ...] = ()
    recent_runs: tuple[TaskSummaryView, ...] = ()


class SchedulesResponse(Response, frozen=True, kw_only=True):
    """Response containing observed schedules and their recent runs."""

    items: tuple[ScheduleSummaryView, ...]
    count: int
    limit: int


def build_schedule_summaries(
    snapshots: list[ScheduleRunSnapshot],
    *,
    limit: int = 25,
) -> tuple[ScheduleSummaryView, ...]:
    """Group observed scheduled task runs by schedule source."""

    grouped: dict[str, list[TaskSnapshot]] = {}
    for snapshot in snapshots:
        if not is_scheduled_task(snapshot) or snapshot.schedule_name is None:
            continue
        grouped.setdefault(snapshot.schedule_id, []).append(snapshot)  # type: ignore[arg-type]

    summaries: list[ScheduleSummaryView] = []
    for schedule_id, items in grouped.items():
        ordered = sorted(items, key=_schedule_sort_key, reverse=True)
        pending_items = [item for item in ordered if is_future_scheduled_task(item)]
        visible_runs = [item for item in ordered if not is_future_scheduled_task(item)]
        pending_runs = len(pending_items)
        queued_runs = sum(
            1
            for item in items
            if item.state == "sent" and not is_future_scheduled_task(item)
        )
        running_runs = sum(
            1
            for item in items
            if item.state in {"received", "started", "retrying"} and not is_future_scheduled_task(item)
        )
        succeeded_runs = sum(1 for item in items if item.state == "succeeded")
        failed_runs = sum(1 for item in items if item.state in {"failed", "lost"})
        most_recent = ordered[0]
        summaries.append(
            ScheduleSummaryView(
                schedule_id=schedule_id,
                schedule_name=most_recent.schedule_name or schedule_id,
                schedule_pattern=most_recent.schedule_pattern,
                queue=most_recent.queue,
                total_runs=len(items),
                pending_runs=pending_runs,
                queued_runs=queued_runs,
                running_runs=running_runs,
                succeeded_runs=succeeded_runs,
                failed_runs=failed_runs,
                last_scheduled_for=_latest_iso(item.scheduled_for for item in items),
                last_run_at=_latest_iso(item.last_seen_at for item in visible_runs),
                pending_run_items=tuple(_to_schedule_run_summary_view(item) for item in pending_items[:12]),
                recent_runs=tuple(_to_schedule_run_summary_view(item) for item in visible_runs[:12]),
            )
        )

    summaries.sort(
        key=lambda summary: (summary.last_scheduled_for or summary.last_run_at or "", summary.schedule_id),
        reverse=True,
    )
    return tuple(summaries[:limit])


def to_schedule_summary_payload(summary: ScheduleSummaryView) -> dict[str, JsonValue]:
    """Convert one schedule summary into the frontend payload shape."""

    return {
        "scheduleId": summary.schedule_id,
        "scheduleName": summary.schedule_name,
        "schedulePattern": summary.schedule_pattern,
        "queue": summary.queue,
        "totalRuns": summary.total_runs,
        "pendingRuns": summary.pending_runs,
        "queuedRuns": summary.queued_runs,
        "runningRuns": summary.running_runs,
        "succeededRuns": summary.succeeded_runs,
        "failedRuns": summary.failed_runs,
        "lastScheduledFor": summary.last_scheduled_for,
        "lastRunAt": summary.last_run_at,
        "pendingRunItems": [to_task_summary_payload(run) for run in summary.pending_run_items],
        "recentRuns": [to_task_summary_payload(run) for run in summary.recent_runs],
    }


def _schedule_sort_key(snapshot: ScheduleRunSnapshot) -> tuple[str, str]:
    return (snapshot.scheduled_for or snapshot.last_seen_at, snapshot.uuid)


def _latest_iso(values: Iterable[str | None]) -> str | None:
    cleaned = [value for value in values if isinstance(value, str)]
    return max(cleaned, default=None)


def _to_schedule_run_summary_view(snapshot: ScheduleRunSnapshot) -> TaskSummaryView:
    return TaskSummaryView(
        uuid=snapshot.uuid,
        name=snapshot.name,
        kind=snapshot.kind,
        state=snapshot.state,
        queue=snapshot.queue,
        routing_key=snapshot.routing_key,
        root_id=snapshot.root_id,
        parent_id=snapshot.parent_id,
        children_ids=tuple(snapshot.children_ids),
        retries=snapshot.retries,
        first_seen_at=snapshot.first_seen_at,
        last_seen_at=snapshot.last_seen_at,
        sent_at=snapshot.sent_at,
        received_at=snapshot.received_at,
        started_at=snapshot.started_at,
        finished_at=snapshot.finished_at,
        worker_hostname=snapshot.worker_hostname,
        result_preview=snapshot.result_preview,
        exception_preview=snapshot.exception_preview,
        canvas_kind=snapshot.canvas_kind,
        canvas_id=snapshot.canvas_id,
        canvas_role=snapshot.canvas_role,
        schedule_id=snapshot.schedule_id,
        schedule_name=snapshot.schedule_name,
        schedule_pattern=snapshot.schedule_pattern,
        scheduled_for=snapshot.scheduled_for,
    )

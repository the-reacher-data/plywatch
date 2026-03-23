"""Policy helpers for task classification and scheduled runs."""

from __future__ import annotations

from typing import Protocol
from datetime import UTC, datetime, timedelta

from plywatch.shared.in_memory_projection_repository import _parse_iso8601
from plywatch.task.constants import COMPLETED_TASK_STATES


class ScheduledTaskLike(Protocol):
    """Minimal task shape needed for schedule-origin policies."""

    schedule_id: str | None
    scheduled_for: str | None
    state: str
    last_seen_at: str


class RunningTaskLike(Protocol):
    """Minimal task shape needed for liveness policies."""

    uuid: str
    state: str
    received_at: str | None
    started_at: str | None
    worker_hostname: str | None


def is_scheduled_task(task: ScheduledTaskLike) -> bool:
    """Return whether a task originated from an observed schedule."""

    return task.schedule_id is not None


def is_future_eta(*, scheduled_for: str | None, reference_at: str) -> bool:
    """Return whether an ETA still points to the future at the reference instant."""

    if scheduled_for is None:
        return False
    return _parse_iso8601(scheduled_for) > _parse_iso8601(reference_at)


def is_future_scheduled_task(task: ScheduledTaskLike) -> bool:
    """Return whether a scheduled task is still waiting for its future ETA."""

    if task.schedule_id is None:
        return False
    if task.state in COMPLETED_TASK_STATES:
        return False
    return is_future_eta(scheduled_for=task.scheduled_for, reference_at=task.last_seen_at)


def is_future_live_eta(*, scheduled_for: str | None, reference_at: str) -> bool:
    """Return whether one observed queue item still belongs to the future workload window."""

    return is_future_eta(scheduled_for=scheduled_for, reference_at=reference_at)


def is_lost_candidate(
    task: RunningTaskLike,
    *,
    reference_at: datetime,
    lost_after_seconds: int,
) -> bool:
    """Return whether a running task should be reconciled against the worker."""

    if lost_after_seconds <= 0:
        return False
    if task.state not in {"received", "started"}:
        return False
    if task.worker_hostname is None:
        return False

    observed_at = task.started_at or task.received_at
    if observed_at is None:
        return False

    return _parse_iso8601(observed_at) <= (reference_at - timedelta(seconds=lost_after_seconds))


def current_utc() -> datetime:
    """Provide a patchable current UTC instant for reconciliation logic."""

    return datetime.now(UTC)

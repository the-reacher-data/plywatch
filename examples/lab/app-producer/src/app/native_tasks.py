"""Native Celery tasks used to observe non-Loom execution graphs."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from typing import Any

from celery import Celery, chord, chain, group
from celery.result import AsyncResult, GroupResult, ResultSet

from app.schedules import SCHEDULE_MARKER_KEY, build_schedule_stamp

StampedMetadata = dict[str, Any] | None


def register_native_tasks(celery_app: Celery) -> None:
    """Register native Celery tasks on the shared lab app.

    Args:
        celery_app: Celery application used by both producer and worker.
    """

    @celery_app.task(name="lab.native.echo")
    def native_echo(
        message: str,
        __plywatch_canvas: StampedMetadata = None,
        __plywatch_schedule: StampedMetadata = None,
    ) -> dict[str, Any]:
        """Return a small success payload."""
        return {"kind": "native", "message": message}

    @celery_app.task(name="lab.native.fail")
    def native_fail(
        message: str,
        __plywatch_canvas: StampedMetadata = None,
        __plywatch_schedule: StampedMetadata = None,
    ) -> None:
        """Raise an error for failure-path inspection."""
        raise RuntimeError(f"native failure: {message}")

    @celery_app.task(name="lab.native.slow_echo")
    def native_slow_echo(
        message: str,
        delay_seconds: int,
        __plywatch_canvas: StampedMetadata = None,
        __plywatch_schedule: StampedMetadata = None,
    ) -> dict[str, Any]:
        """Sleep for a short interval and then succeed."""
        time.sleep(max(delay_seconds, 1))
        return {"kind": "native", "message": message, "delaySeconds": delay_seconds}

    @celery_app.task(name="lab.native.collect")
    def native_collect(
        results: list[dict[str, Any]],
        __plywatch_canvas: StampedMetadata = None,
        __plywatch_schedule: StampedMetadata = None,
    ) -> dict[str, Any]:
        """Collect group or chord header results into one payload."""
        return {"kind": "native", "count": len(results), "results": results}

    @celery_app.task(name="lab.native.followup")
    def native_followup(
        previous: dict[str, Any],
        message: str,
        __plywatch_canvas: StampedMetadata = None,
        __plywatch_schedule: StampedMetadata = None,
    ) -> dict[str, Any]:
        """Attach a second stage to a native chain."""
        return {"kind": "native", "previous": previous, "message": message}


def dispatch_native_success(celery_app: Celery, message: str, count: int) -> list[str]:
    """Dispatch one or more standalone native success tasks."""
    handles = [
        celery_app.signature("lab.native.echo", kwargs={"message": f"{message} #{index}"}).apply_async()
        for index in range(max(count, 1))
    ]
    return [handle.id for handle in handles]


def dispatch_scheduled_runs(
    celery_app: Celery,
    message: str,
    count: int,
    *,
    delay_seconds: int,
    queue: str = "default",
) -> dict[str, Any]:
    """Dispatch future ETA runs stamped as coming from one observed schedule."""

    schedule = build_schedule_stamp(message, delay_seconds)
    now = datetime.now(UTC)
    handles = []
    for index in range(max(count, 1)):
        eta = now + timedelta(seconds=delay_seconds * (index + 1))
        handle = celery_app.signature(
            "lab.native.echo",
            kwargs={
                "message": f"{message} run-{index + 1}",
                SCHEDULE_MARKER_KEY: schedule.as_kwargs_value(),
            },
            queue=queue,
            routing_key=queue,
        ).apply_async(eta=eta)
        handles.append({"id": handle.id, "eta": eta.isoformat()})
    return {
        "schedule_id": schedule.schedule_id,
        "schedule_name": schedule.schedule_name,
        "schedule_pattern": schedule.schedule_pattern,
        "job_ids": [item["id"] for item in handles],
        "etas": [item["eta"] for item in handles],
    }


def dispatch_native_chain(celery_app: Celery, message: str) -> str | None:
    """Dispatch a native chain and return the terminal async result id."""
    canvas_id = str(uuid4())
    flow = chain(
        celery_app.signature(
            "lab.native.echo",
            kwargs={
                "message": f"{message} step-1",
                "__plywatch_canvas": {"kind": "chain", "id": canvas_id, "role": "head"},
            },
        ),
        celery_app.signature(
            "lab.native.followup",
            kwargs={
                "message": f"{message} step-2",
                "__plywatch_canvas": {"kind": "chain", "id": canvas_id, "role": "tail"},
            },
        ),
    )
    result = flow.apply_async()
    return result.id


def dispatch_native_group(celery_app: Celery, message: str, count: int) -> list[str]:
    """Dispatch a native group and return child task ids."""
    canvas_id = str(uuid4())
    header = group(
        celery_app.signature(
            "lab.native.echo",
            kwargs={
                "message": f"{message} #{index}",
                "__plywatch_canvas": {
                    "kind": "group",
                    "id": canvas_id,
                    "role": "member",
                    "index": index,
                },
            },
        )
        for index in range(max(count, 1))
    )
    result = header.apply_async()
    return _extract_result_ids(result)


def dispatch_native_chord(celery_app: Celery, message: str, count: int) -> dict[str, Any]:
    """Dispatch a native chord and return header/body identifiers."""
    canvas_id = str(uuid4())
    header = group(
        celery_app.signature(
            "lab.native.echo",
            kwargs={
                "message": f"{message} #{index}",
                "__plywatch_canvas": {
                    "kind": "chord",
                    "id": canvas_id,
                    "role": "header",
                    "index": index,
                },
            },
        )
        for index in range(max(count, 1))
    )
    body = celery_app.signature(
        "lab.native.collect",
        kwargs={
            "__plywatch_canvas": {
                "kind": "chord",
                "id": canvas_id,
                "role": "body",
            },
        },
    )
    result = chord(header)(body)

    header_ids = _extract_result_ids(result.parent)
    return {"body_id": result.id, "header_ids": header_ids}


def _extract_result_ids(result: AsyncResult | GroupResult | ResultSet | None) -> list[str]:
    """Normalize async result containers into a flat list of task ids."""
    if result is None:
        return []
    if isinstance(result, GroupResult):
        return [item.id for item in result.results if item.id is not None]
    if isinstance(result, ResultSet):
        return [item.id for item in result.results if item.id is not None]
    return [result.id] if result.id is not None else []

"""Celery-backed task presence gateway used by the liveness reconciler."""

from __future__ import annotations

from typing import Any

from celery import Celery
from loom.core.model import LoomStruct

from plywatch.task.liveness import TaskExecutionPresenceGateway, TaskExecutionPresenceSnapshot


class CeleryTaskExecutionPresenceSnapshot(LoomStruct, frozen=True, kw_only=True):
    """Immutable live-task lookup built from Celery inspect calls."""

    task_ids_by_worker: dict[str, frozenset[str]]

    def contains(self, *, worker_hostname: str, task_id: str) -> bool:
        return task_id in self.task_ids_by_worker.get(worker_hostname, frozenset())


class CeleryTaskExecutionPresenceGateway(TaskExecutionPresenceGateway):
    """Read active/reserved/scheduled task UUIDs from Celery workers."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def capture(self) -> TaskExecutionPresenceSnapshot:
        inspect = self._celery_app.control.inspect(timeout=1.0)
        task_ids_by_worker: dict[str, set[str]] = {}
        for payload in (inspect.active() or {}, inspect.reserved() or {}, inspect.scheduled() or {}):
            self._merge_payload(task_ids_by_worker, payload)
        return CeleryTaskExecutionPresenceSnapshot(
            task_ids_by_worker={worker: frozenset(task_ids) for worker, task_ids in task_ids_by_worker.items()}
        )

    def _merge_payload(self, target: dict[str, set[str]], payload: dict[str, Any]) -> None:
        for worker_hostname, items in payload.items():
            worker_ids = target.setdefault(worker_hostname, set())
            for item in items or ():
                task_id = _extract_task_id(item)
                if task_id is not None:
                    worker_ids.add(task_id)


def _extract_task_id(item: Any) -> str | None:
    if isinstance(item, dict):
        if isinstance(item.get("id"), str):
            return item["id"]
        request = item.get("request")
        if isinstance(request, dict) and isinstance(request.get("id"), str):
            return request["id"]
    return None

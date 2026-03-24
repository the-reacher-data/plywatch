"""Helpers to derive frontend SSE payloads from raw monitor events."""

from __future__ import annotations

from enum import StrEnum

from plywatch.shared.raw_events import RawCeleryEvent
from plywatch.task.constants import TASK_EVENT_LOST, TASK_EVENT_PREFIX
from plywatch.task.repository import TaskSnapshotRepository
from plywatch.worker.constants import WORKER_EVENT_PREFIX
from plywatch.worker.repository import WorkerSnapshotRepository


class FrontendEventType(StrEnum):
    TASK_UPDATED = "task.updated"
    TASK_CREATED = "task.created"
    QUEUE_UPDATED = "queue.updated"
    WORKER_UPDATED = "worker.updated"
    WORKER_CREATED = "worker.created"
    RAW_EVENT = "raw.event"


class FrontendEventField(StrEnum):
    TYPE = "type"
    EVENT_TYPE = "eventType"
    TASK_ID = "taskId"
    WORKER_HOSTNAME = "workerHostname"
    QUEUE_NAME = "queueName"
    CAPTURED_AT = "capturedAt"
    TASK_NAME = "taskName"


def task_exists_before_event(event: RawCeleryEvent, task_repository: TaskSnapshotRepository) -> bool:
    """Return whether the task targeted by the event already existed."""
    return bool(
        event.uuid is not None
        and event.event_type.startswith(TASK_EVENT_PREFIX)
        and task_repository.get(event.uuid) is not None
    )


def worker_exists_before_event(event: RawCeleryEvent, worker_repository: WorkerSnapshotRepository) -> bool:
    """Return whether the worker targeted by the event already existed."""
    return bool(
        event.hostname is not None
        and event.event_type.startswith(WORKER_EVENT_PREFIX)
        and worker_repository.get(event.hostname) is not None
    )


def task_lost_message(task_id: str) -> dict[str, object]:
    """Build the SSE payload for one task marked as lost."""
    return {
        FrontendEventField.TYPE.value: FrontendEventType.TASK_UPDATED.value,
        FrontendEventField.EVENT_TYPE.value: TASK_EVENT_LOST,
        FrontendEventField.TASK_ID.value: task_id,
        FrontendEventField.WORKER_HOSTNAME.value: None,
        FrontendEventField.QUEUE_NAME.value: None,
        FrontendEventField.CAPTURED_AT.value: None,
        FrontendEventField.TASK_NAME.value: None,
    }


def build_frontend_events(
    event: RawCeleryEvent,
    *,
    task_exists_before: bool,
    worker_exists_before: bool,
    task_repository: TaskSnapshotRepository,
) -> tuple[dict[str, object], ...]:
    """Convert one raw monitor event into frontend-oriented SSE messages."""
    event_type = event.event_type
    task_id = event.uuid
    queue_name = _payload_string(event, "queue")
    task_name = _payload_string(event, "name")

    if event_type.startswith(TASK_EVENT_PREFIX) and task_id is not None:
        snapshot = task_repository.get(task_id)
        if snapshot is not None:
            queue_name = snapshot.queue or queue_name
            task_name = snapshot.name or task_name
        return (
            _event_payload(
                event_kind=FrontendEventType.TASK_UPDATED if task_exists_before else FrontendEventType.TASK_CREATED,
                event_type=event_type,
                task_id=task_id,
                worker_hostname=event.hostname,
                queue_name=queue_name,
                captured_at=event.captured_at,
                task_name=task_name,
            ),
            _event_payload(
                event_kind=FrontendEventType.QUEUE_UPDATED,
                event_type=event_type,
                task_id=task_id,
                worker_hostname=event.hostname,
                queue_name=queue_name,
                captured_at=event.captured_at,
                task_name=task_name,
            ),
        )

    if event_type.startswith(WORKER_EVENT_PREFIX):
        return (
            _event_payload(
                event_kind=FrontendEventType.WORKER_UPDATED if worker_exists_before else FrontendEventType.WORKER_CREATED,
                event_type=event_type,
                task_id=task_id,
                worker_hostname=event.hostname,
                queue_name=queue_name,
                captured_at=event.captured_at,
                task_name=task_name,
            ),
        )

    return (
        _event_payload(
            event_kind=FrontendEventType.RAW_EVENT,
            event_type=event_type,
            task_id=task_id,
            worker_hostname=event.hostname,
            queue_name=queue_name,
            captured_at=event.captured_at,
            task_name=task_name,
        ),
    )


def _payload_string(event: RawCeleryEvent, key: str) -> str | None:
    value = event.payload.get(key)
    return value if isinstance(value, str) else None


def _event_payload(
    *,
    event_kind: FrontendEventType,
    event_type: str,
    task_id: str | None,
    worker_hostname: str | None,
    queue_name: str | None,
    captured_at: str | None,
    task_name: str | None,
) -> dict[str, object]:
    return {
        FrontendEventField.TYPE.value: event_kind.value,
        FrontendEventField.EVENT_TYPE.value: event_type,
        FrontendEventField.TASK_ID.value: task_id,
        FrontendEventField.WORKER_HOSTNAME.value: worker_hostname,
        FrontendEventField.QUEUE_NAME.value: queue_name,
        FrontendEventField.CAPTURED_AT.value: captured_at,
        FrontendEventField.TASK_NAME.value: task_name,
    }

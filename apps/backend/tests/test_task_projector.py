from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plywatch.shared.raw_events import build_raw_event
from plywatch.task.projector import TaskProjector
from plywatch.task.repository import InMemoryTaskSnapshotRepository


def test_task_projector_builds_consolidated_snapshot() -> None:
    repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=3600)
    projector = TaskProjector(repository)
    task_id = "task-1"

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": task_id,
                "name": "loom.job.HelloSuccessJob",
                "queue": "default",
                "routing_key": "default",
                "root_id": task_id,
                "parent_id": None,
                "kwargs": "{'payload': {'message': 'hello'}}",
            }
        )
    )
    projector.apply(build_raw_event({"type": "task-received", "uuid": task_id, "name": "loom.job.HelloSuccessJob"}))
    projector.apply(build_raw_event({"type": "task-started", "uuid": task_id}))
    projector.apply(
        build_raw_event(
            {
                "type": "task-succeeded",
                "uuid": task_id,
                "result": "{'scenario': 'success'}",
            }
        )
    )

    snapshot = repository.get(task_id)
    assert snapshot is not None
    assert snapshot.uuid == task_id
    assert snapshot.name == "loom.job.HelloSuccessJob"
    assert snapshot.kind == "job"
    assert snapshot.state == "succeeded"
    assert snapshot.queue == "default"
    assert snapshot.routing_key == "default"
    assert snapshot.root_id == task_id
    assert snapshot.retries == 0
    assert snapshot.sent_at is not None
    assert snapshot.received_at is not None
    assert snapshot.started_at is not None
    assert snapshot.finished_at is not None
    assert snapshot.result_preview == "{'scenario': 'success'}"
    assert len(snapshot.events) == 4


def test_task_projector_links_callback_children_to_parent() -> None:
    repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=3600)
    projector = TaskProjector(repository)

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "parent-1",
                "name": "loom.job.HelloRetryJob",
                "root_id": "parent-1",
                "parent_id": None,
            }
        )
    )
    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "child-1",
                "name": "loom.callback_error.RecordFailureCallback",
                "root_id": "parent-1",
                "parent_id": "parent-1",
            }
        )
    )

    parent = repository.get("parent-1")
    child = repository.get("child-1")
    assert parent is not None
    assert child is not None
    assert child.kind == "callback_error"
    assert child.parent_id == "parent-1"
    assert parent.children_ids == ["child-1"]


def test_repository_prunes_oldest_tasks_when_limit_is_exceeded() -> None:
    repository = InMemoryTaskSnapshotRepository(max_tasks=2, max_age_seconds=3600)
    projector = TaskProjector(repository)
    base = datetime.now(UTC)

    for index in range(3):
        projector.apply(
            build_raw_event(
                {
                    "type": "task-sent",
                    "uuid": f"task-{index}",
                    "name": "loom.job.HelloSuccessJob",
                    "timestamp": (base + timedelta(seconds=index)).timestamp(),
                }
            )
        )

    assert repository.count() == 2
    assert repository.get("task-0") is None
    assert repository.get("task-1") is not None
    assert repository.get("task-2") is not None


def test_repository_lists_tasks_by_root() -> None:
    repository = InMemoryTaskSnapshotRepository(max_tasks=10, max_age_seconds=3600)
    projector = TaskProjector(repository)

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "root-1",
                "name": "loom.job.HelloSuccessJob",
                "root_id": "root-1",
            }
        )
    )
    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "child-1",
                "name": "loom.callback.RecordSuccessCallback",
                "root_id": "root-1",
                "parent_id": "root-1",
            }
        )
    )
    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": "other-1",
                "name": "loom.job.HelloSuccessJob",
                "root_id": "other-1",
            }
        )
    )

    items = repository.list_by_root("root-1")

    assert [item.uuid for item in items] == ["root-1", "child-1"]


def test_task_projector_clears_retry_exception_after_success() -> None:
    repository = InMemoryTaskSnapshotRepository(max_tasks=100, max_age_seconds=3600)
    projector = TaskProjector(repository)
    task_id = "retry-success-1"

    projector.apply(
        build_raw_event(
            {
                "type": "task-sent",
                "uuid": task_id,
                "name": "loom.job.HelloRetrySuccessJob",
                "root_id": task_id,
                "kwargs": "{'payload': {'message': 'retry then success'}}",
            }
        )
    )
    projector.apply(build_raw_event({"type": "task-received", "uuid": task_id}))
    projector.apply(build_raw_event({"type": "task-started", "uuid": task_id}))
    projector.apply(
        build_raw_event(
            {
                "type": "task-retried",
                "uuid": task_id,
                "exception": "RuntimeError('temporary failure')",
            }
        )
    )
    projector.apply(build_raw_event({"type": "task-started", "uuid": task_id}))
    projector.apply(
        build_raw_event(
            {
                "type": "task-succeeded",
                "uuid": task_id,
                "result": "{'scenario': 'retry_success'}",
            }
        )
    )

    snapshot = repository.get(task_id)

    assert snapshot is not None
    assert snapshot.state == "succeeded"
    assert snapshot.retries == 1
    assert snapshot.result_preview == "{'scenario': 'retry_success'}"
    assert snapshot.exception_preview is None

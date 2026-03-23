from __future__ import annotations

from plywatch.shared.raw_events import build_raw_event
from plywatch.worker.projector import WorkerProjector
from plywatch.worker.repository import InMemoryWorkerSnapshotRepository


def test_worker_projector_builds_online_snapshot() -> None:
    repository = InMemoryWorkerSnapshotRepository(max_age_seconds=3600, stale_after_seconds=15)
    projector = WorkerProjector(repository)

    projector.apply(
        build_raw_event(
            {
                "type": "worker-online",
                "hostname": "celery@worker-1",
                "pid": 1,
                "freq": 2.0,
                "active": 0,
                "processed": 3,
                "loadavg": [0.1, 0.2, 0.3],
                "sw_ident": "py-celery",
                "sw_ver": "5.6.2",
                "sw_sys": "Linux",
            }
        )
    )

    snapshot = repository.get("celery@worker-1")
    assert snapshot is not None
    assert snapshot.hostname == "celery@worker-1"
    assert snapshot.state == "online"
    assert snapshot.online_at is not None
    assert snapshot.pid == 1
    assert snapshot.processed == 3
    assert snapshot.loadavg == (0.1, 0.2, 0.3)


def test_worker_projector_marks_worker_offline() -> None:
    repository = InMemoryWorkerSnapshotRepository(max_age_seconds=3600, stale_after_seconds=15)
    projector = WorkerProjector(repository)

    projector.apply(build_raw_event({"type": "worker-online", "hostname": "celery@worker-1"}))
    projector.apply(build_raw_event({"type": "worker-offline", "hostname": "celery@worker-1"}))

    snapshot = repository.get("celery@worker-1")
    assert snapshot is not None
    assert snapshot.state == "offline"
    assert snapshot.offline_at is not None

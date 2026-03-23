from __future__ import annotations

from celery import Celery

from app.native_tasks import dispatch_scheduled_runs, register_native_tasks


def build_celery_app() -> Celery:
    app = Celery("plywatch-lab-test", broker="memory://", backend="cache+memory://")
    app.conf.task_always_eager = True
    app.conf.task_store_eager_result = False
    return app


def test_dispatch_scheduled_runs_accepts_schedule_metadata() -> None:
    app = build_celery_app()
    register_native_tasks(app)

    info = dispatch_scheduled_runs(
        app,
        "scheduled validation",
        2,
        delay_seconds=5,
    )

    assert info["schedule_id"] == "schedule:scheduled-validation"
    assert info["schedule_name"] == "Schedule scheduled validation"
    assert info["schedule_pattern"] == "every 5s"
    assert len(info["job_ids"]) == 2
    assert len(info["etas"]) == 2

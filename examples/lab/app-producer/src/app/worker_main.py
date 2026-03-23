"""Celery worker entrypoint for the lab producer app."""

from __future__ import annotations

from typing import Any

from celery.signals import worker_process_init, worker_process_shutdown
from loom.celery.auto import create_app as create_worker_app
from loom.celery.event_loop import WorkerEventLoop

from app.callbacks import RecordFailureCallback, RecordSuccessCallback
from app.celery_app import configure_lab_queues
from app.config_paths import WORKER_CONFIG_PATHS
from app.jobs import HelloFailureJob, HelloRetryJob, HelloRetrySuccessJob, HelloSlowJob, HelloSuccessJob
from app.native_tasks import register_native_tasks

celery_app = create_worker_app(
    *WORKER_CONFIG_PATHS,
    jobs=[HelloSuccessJob, HelloFailureJob, HelloRetryJob, HelloRetrySuccessJob, HelloSlowJob],
    callbacks=[RecordSuccessCallback, RecordFailureCallback],
)
configure_lab_queues(celery_app)
celery_app.conf.task_send_sent_event = True
celery_app.conf.task_track_started = True
celery_app.conf.worker_send_task_events = True
register_native_tasks(celery_app)


@worker_process_init.connect(weak=False)
def _init_worker_event_loop(**kwargs: Any) -> None:
    """Initialize the Loom worker event loop for pure-job lab workers."""
    WorkerEventLoop.initialize()


@worker_process_shutdown.connect(weak=False)
def _shutdown_worker_event_loop(**kwargs: Any) -> None:
    """Shut down the Loom worker event loop on worker child exit."""
    WorkerEventLoop.shutdown()

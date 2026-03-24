"""Shared Celery application wiring for the lab producer."""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue
from loom.celery.config import CeleryConfig, create_celery_app
from loom.core.config.loader import load_config, section

from app.config_paths import WORKER_CONFIG_PATHS


LAB_EXCHANGE = Exchange("lab", type="direct")


def configure_lab_queues(celery_app: Celery) -> Celery:
    """Attach explicit queue topology for the lab producer.

    Celery's implicit queue creation binds unknown queues with the default
    routing key, which collapses `slow` traffic back into `default` from the
    monitor's perspective. Declaring the queues here keeps both workers and
    task-sent events aligned on the same routing.
    """
    celery_app.conf.task_default_exchange = LAB_EXCHANGE.name
    celery_app.conf.task_default_exchange_type = LAB_EXCHANGE.type
    celery_app.conf.task_default_queue = "default"
    celery_app.conf.task_default_routing_key = "default"
    celery_app.conf.task_create_missing_queues = False
    celery_app.conf.task_queues = (
        Queue("default", exchange=LAB_EXCHANGE, routing_key="default"),
        Queue("slow", exchange=LAB_EXCHANGE, routing_key="slow"),
    )
    return celery_app


def build_celery_app() -> Celery:
    """Build the shared Celery app used by the lab producer.

    Returns:
        A configured Celery application with task events enabled.
    """
    raw = load_config(*WORKER_CONFIG_PATHS)
    cfg = section(raw, "celery", CeleryConfig)
    celery_app = create_celery_app(cfg)
    configure_lab_queues(celery_app)
    celery_app.conf.task_send_sent_event = True
    celery_app.conf.task_track_started = True
    celery_app.conf.worker_send_task_events = True
    return celery_app

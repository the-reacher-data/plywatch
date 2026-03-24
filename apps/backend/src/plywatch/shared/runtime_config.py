"""Runtime configuration helpers for Plywatch."""

from __future__ import annotations

from dataclasses import dataclass

import msgspec
from loom.celery.config import CeleryConfig
from loom.core.config.loader import load_config, section
from loom.core.logger import LoggerConfig

from plywatch.config_paths import API_CONFIG_PATHS


class RestConfig(msgspec.Struct, kw_only=True):
    """REST settings loaded from YAML."""

    title: str = "Plywatch API"
    version: str = "0.1.0"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"


class AppConfig(msgspec.Struct, kw_only=True):
    """Application settings loaded from YAML."""

    name: str = "plywatch"
    rest: RestConfig = msgspec.field(default_factory=RestConfig)


class MetricsConfig(msgspec.Struct, kw_only=True):
    """Metrics feature settings loaded from YAML."""

    enabled: bool = False
    path: str = "/metrics"
    adapters: tuple[str, ...] = ("prometheus",)


class TraceConfig(msgspec.Struct, kw_only=True):
    """Trace feature settings loaded from YAML."""

    enabled: bool = True
    header: str = "x-request-id"


class MonitorConfig(msgspec.Struct, kw_only=True):
    """Monitor retention and liveness settings loaded from YAML."""

    raw_event_limit: int = 500
    raw_event_buffer_excluded_types: tuple[str, ...] = ("worker-heartbeat",)
    max_tasks: int = 2000
    max_completed_tasks: int = 20000
    max_schedule_runs: int = 5000
    max_age_seconds: int = 21600
    worker_stale_after_seconds: int = 15
    task_lost_after_seconds: int = 1800
    task_liveness_reconcile_interval_seconds: int = 30


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings for the Plywatch backend."""

    config_paths: tuple[str, ...]
    app: AppConfig
    logger: LoggerConfig
    metrics: MetricsConfig
    trace: TraceConfig
    celery: CeleryConfig
    raw_event_limit: int
    raw_event_buffer_excluded_types: tuple[str, ...]
    max_tasks: int
    max_completed_tasks: int
    max_schedule_runs: int
    max_age_seconds: int
    worker_stale_after_seconds: int
    task_lost_after_seconds: int
    task_liveness_reconcile_interval_seconds: int


def load_runtime_settings() -> RuntimeSettings:
    """Load runtime settings from YAML and environment variables."""
    raw_config = load_config(*API_CONFIG_PATHS)
    metrics = section(raw_config, "metrics", MetricsConfig)
    monitor = section(raw_config, "monitor", MonitorConfig)

    return RuntimeSettings(
        config_paths=API_CONFIG_PATHS,
        app=section(raw_config, "app", AppConfig),
        logger=section(raw_config, "logger", LoggerConfig),
        metrics=metrics,
        trace=section(raw_config, "trace", TraceConfig),
        celery=section(raw_config, "celery", CeleryConfig),
        raw_event_limit=monitor.raw_event_limit,
        raw_event_buffer_excluded_types=monitor.raw_event_buffer_excluded_types,
        max_tasks=monitor.max_tasks,
        max_completed_tasks=monitor.max_completed_tasks,
        max_schedule_runs=monitor.max_schedule_runs,
        max_age_seconds=monitor.max_age_seconds,
        worker_stale_after_seconds=monitor.worker_stale_after_seconds,
        task_lost_after_seconds=monitor.task_lost_after_seconds,
        task_liveness_reconcile_interval_seconds=monitor.task_liveness_reconcile_interval_seconds,
    )

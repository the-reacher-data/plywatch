"""Runtime configuration helpers for Plywatch."""

from __future__ import annotations

import os
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
    adapters_override = os.getenv("PLYWATCH_METRICS_ADAPTERS")
    metrics_adapters = (
        tuple(item.strip() for item in adapters_override.split(",") if item.strip())
        if adapters_override is not None
        else metrics.adapters
    )

    raw_event_buffer_excluded_types = _parse_csv_env(
        "PLYWATCH_RAW_EVENT_BUFFER_EXCLUDED_TYPES",
        default=("worker-heartbeat",),
    )

    return RuntimeSettings(
        config_paths=API_CONFIG_PATHS,
        app=section(raw_config, "app", AppConfig),
        logger=section(raw_config, "logger", LoggerConfig),
        metrics=MetricsConfig(
            enabled=metrics.enabled,
            path=metrics.path,
            adapters=metrics_adapters,
        ),
        trace=section(raw_config, "trace", TraceConfig),
        celery=section(raw_config, "celery", CeleryConfig),
        raw_event_limit=int(os.getenv("PLYWATCH_RAW_EVENT_LIMIT", "500")),
        raw_event_buffer_excluded_types=raw_event_buffer_excluded_types,
        max_tasks=int(os.getenv("PLYWATCH_MAX_TASKS", "2000")),
        max_completed_tasks=int(os.getenv("PLYWATCH_MAX_COMPLETED_TASKS", "20000")),
        max_schedule_runs=int(os.getenv("PLYWATCH_MAX_SCHEDULE_RUNS", "5000")),
        max_age_seconds=int(os.getenv("PLYWATCH_MAX_AGE_SECONDS", "21600")),
        worker_stale_after_seconds=int(os.getenv("PLYWATCH_WORKER_STALE_AFTER_SECONDS", "15")),
        task_lost_after_seconds=int(os.getenv("PLYWATCH_TASK_LOST_AFTER_SECONDS", "1800")),
        task_liveness_reconcile_interval_seconds=int(os.getenv("PLYWATCH_TASK_LIVENESS_RECONCILE_INTERVAL_SECONDS", "30")),
    )


def _parse_csv_env(name: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items if items else ()

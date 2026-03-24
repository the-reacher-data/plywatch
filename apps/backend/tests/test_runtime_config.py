from __future__ import annotations

from plywatch.shared.runtime_config import load_runtime_settings


def test_load_runtime_settings_reads_monitor_limits_from_env(monkeypatch) -> None:
    monkeypatch.setenv("PLYWATCH_RAW_EVENT_LIMIT", "321")
    monkeypatch.setenv(
        "PLYWATCH_RAW_EVENT_BUFFER_EXCLUDED_TYPES",
        '["worker-heartbeat","task-sent"]',
    )
    monkeypatch.setenv("PLYWATCH_MAX_TASKS", "111")
    monkeypatch.setenv("PLYWATCH_MAX_COMPLETED_TASKS", "222")
    monkeypatch.setenv("PLYWATCH_MAX_SCHEDULE_RUNS", "333")
    monkeypatch.setenv("PLYWATCH_MAX_AGE_SECONDS", "444")
    monkeypatch.setenv("PLYWATCH_WORKER_STALE_AFTER_SECONDS", "55")
    monkeypatch.setenv("PLYWATCH_TASK_LOST_AFTER_SECONDS", "66")
    monkeypatch.setenv("PLYWATCH_TASK_LIVENESS_RECONCILE_INTERVAL_SECONDS", "77")

    settings = load_runtime_settings()

    assert settings.raw_event_limit == 321
    assert settings.raw_event_buffer_excluded_types == ("worker-heartbeat", "task-sent")
    assert settings.max_tasks == 111
    assert settings.max_completed_tasks == 222
    assert settings.max_schedule_runs == 333
    assert settings.max_age_seconds == 444
    assert settings.worker_stale_after_seconds == 55
    assert settings.task_lost_after_seconds == 66
    assert settings.task_liveness_reconcile_interval_seconds == 77


def test_load_runtime_settings_reads_rest_metrics_and_trace_from_env(monkeypatch) -> None:
    monkeypatch.setenv("PLYWATCH_REST_TITLE", "Plywatch Hardened")
    monkeypatch.setenv("PLYWATCH_REST_DOCS_URL", "null")
    monkeypatch.setenv("PLYWATCH_REST_REDOC_URL", "null")
    monkeypatch.setenv("PLYWATCH_METRICS_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_METRICS_ADAPTERS", '["prometheus"]')
    monkeypatch.setenv("PLYWATCH_METRICS_FLOWER_COMPAT_ENABLED", "false")
    monkeypatch.setenv("PLYWATCH_TRACE_HEADER", "x-correlation-id")

    settings = load_runtime_settings()

    assert settings.app.rest.title == "Plywatch Hardened"
    assert settings.app.rest.docs_url is None
    assert settings.app.rest.redoc_url is None
    assert settings.metrics.enabled is False
    assert settings.metrics.adapters == ("prometheus",)
    assert settings.metrics.flower_compat_enabled is False
    assert settings.trace.header == "x-correlation-id"

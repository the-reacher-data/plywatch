"""Producer service helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from loom.celery.service import CeleryJobService
from loom.core.job.context import flush_pending_dispatches

from app.callbacks import RecordFailureCallback, RecordSuccessCallback
from app.celery_app import build_celery_app
from app.jobs import HelloFailureJob, HelloRetryJob, HelloRetrySuccessJob, HelloSlowJob, HelloSuccessJob
from app.native_tasks import (
    dispatch_scheduled_runs,
    dispatch_native_chain,
    dispatch_native_chord,
    dispatch_native_group,
    dispatch_native_success,
    register_native_tasks,
)
from app.schemas import EmitRequest, EmitSuiteRequest

NativeScenarioEmitter = Callable[[Any, EmitRequest], dict[str, Any]]
AsyncScenarioEmitter = Callable[[Any, CeleryJobService, EmitRequest], Awaitable[dict[str, Any]]]

_JOB_SCENARIOS = {
    "success": HelloSuccessJob,
    "failure": HelloFailureJob,
    "retry": HelloRetryJob,
    "retry_success": HelloRetrySuccessJob,
    "slow": HelloSlowJob,
}


async def emit_scenario(request: EmitRequest) -> dict[str, Any]:
    """Dispatch one lab scenario and flush pending Celery sends."""
    celery_app = build_celery_app()
    register_native_tasks(celery_app)
    jobs = CeleryJobService(celery_app)
    on_success = RecordSuccessCallback if request.with_callbacks else None
    on_failure = RecordFailureCallback if request.with_callbacks else None
    handler = _SCENARIO_HANDLERS[request.scenario]
    return await handler(celery_app, jobs, request, on_success=on_success, on_failure=on_failure)


async def emit_suite(request: EmitSuiteRequest) -> dict[str, Any]:
    """Dispatch one predefined lab suite for richer monitor inspection.

    Args:
        request: Suite selection and timing parameters.

    Returns:
        Summary of the launched scenarios and their task identifiers.
    """

    suite_requests = _build_suite_requests(request)
    launched: list[dict[str, Any]] = []
    for scenario_request in suite_requests:
        launched.append(await emit_scenario(scenario_request))

    total_jobs = 0
    for item in launched:
        total_jobs += len(item.get("job_ids", []))
        total_jobs += len(item.get("header_ids", []))

    return {
        "suite": request.suite,
        "message": request.message,
        "delay_seconds": request.delay_seconds,
        "launched": launched,
        "scenario_count": len(launched),
        "job_count": total_jobs,
    }


def _build_suite_requests(request: EmitSuiteRequest) -> list[EmitRequest]:
    """Build the scenario requests for one named lab suite."""
    return _SUITE_BUILDERS[request.suite](request)


async def _emit_native_success(
    celery_app: Any,
    _jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    job_ids = dispatch_native_success(celery_app, request.message, request.count)
    return {"scenario": request.scenario, "job_ids": job_ids, "count": len(job_ids)}


async def _emit_native_chain(
    celery_app: Any,
    _jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    job_id = dispatch_native_chain(celery_app, request.message)
    return {"scenario": request.scenario, "job_ids": [job_id] if job_id is not None else [], "count": 1}


async def _emit_native_group(
    celery_app: Any,
    _jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    job_ids = dispatch_native_group(celery_app, request.message, request.count)
    return {"scenario": request.scenario, "job_ids": job_ids, "count": len(job_ids)}


async def _emit_native_chord(
    celery_app: Any,
    _jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    info = dispatch_native_chord(celery_app, request.message, request.count)
    return {
        "scenario": request.scenario,
        "job_ids": [info["body_id"]],
        "header_ids": info["header_ids"],
        "count": len(info["header_ids"]),
    }


async def _emit_parallel(
    _celery_app: Any,
    jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    group = jobs.dispatch_parallel(
        [(HelloSuccessJob, {"message": f"{request.message} #{index}"}) for index in range(request.count)]
    )
    await flush_pending_dispatches()
    return {
        "scenario": request.scenario,
        "job_ids": [handle.job_id for handle in group.handles],
        "count": len(group.handles),
    }


async def _emit_scheduled(
    celery_app: Any,
    _jobs: CeleryJobService,
    request: EmitRequest,
    **_: Any,
) -> dict[str, Any]:
    info = dispatch_scheduled_runs(
        celery_app,
        request.message,
        request.count,
        delay_seconds=request.delay_seconds,
    )
    return {
        "scenario": request.scenario,
        "schedule_id": info["schedule_id"],
        "schedule_name": info["schedule_name"],
        "schedule_pattern": info["schedule_pattern"],
        "etas": info["etas"],
        "job_ids": info["job_ids"],
        "count": len(info["job_ids"]),
    }


async def _emit_job_scenario(
    _celery_app: Any,
    jobs: CeleryJobService,
    request: EmitRequest,
    *,
    on_success: Any,
    on_failure: Any,
) -> dict[str, Any]:
    job_type = _JOB_SCENARIOS[request.scenario]
    handles = [
        jobs.dispatch(
            job_type,
            payload={
                "scenario": request.scenario,
                "count": request.count,
                "with_callbacks": request.with_callbacks,
                "delay_seconds": request.delay_seconds,
                "message": request.message,
            },
            on_success=on_success,
            on_failure=on_failure,
        )
        for _ in range(max(request.count, 1))
    ]
    await flush_pending_dispatches()
    return {
        "scenario": request.scenario,
        "job_ids": [handle.job_id for handle in handles],
        "count": len(handles),
    }


def _build_loom_long_suite(request: EmitSuiteRequest) -> list[EmitRequest]:
    return [
        EmitRequest(scenario="success", count=4, message=f"{request.message} / success"),
        EmitRequest(scenario="failure", count=2, message=f"{request.message} / failure"),
        EmitRequest(scenario="retry", count=2, message=f"{request.message} / retry"),
        EmitRequest(
            scenario="slow",
            count=4,
            delay_seconds=request.delay_seconds,
            message=f"{request.message} / slow",
        ),
    ]


def _build_native_graph_suite(request: EmitSuiteRequest) -> list[EmitRequest]:
    return [
        EmitRequest(scenario="native_success", count=3, message=f"{request.message} / native-success"),
        EmitRequest(scenario="native_chain", count=1, message=f"{request.message} / native-chain"),
        EmitRequest(scenario="native_group", count=4, message=f"{request.message} / native-group"),
        EmitRequest(scenario="native_chord", count=4, message=f"{request.message} / native-chord"),
    ]


def _build_observe_all_suite(request: EmitSuiteRequest) -> list[EmitRequest]:
    return [
        EmitRequest(scenario="success", count=3, message=f"{request.message} / success"),
        EmitRequest(scenario="retry_success", count=2, message=f"{request.message} / retry-success"),
        EmitRequest(
            scenario="scheduled",
            count=3,
            delay_seconds=max(request.delay_seconds // 3, 5),
            message=f"{request.message} / scheduled",
            with_callbacks=False,
        ),
        EmitRequest(
            scenario="slow",
            count=3,
            delay_seconds=request.delay_seconds,
            message=f"{request.message} / slow",
        ),
        EmitRequest(scenario="parallel", count=4, message=f"{request.message} / parallel"),
        EmitRequest(scenario="native_chain", count=1, message=f"{request.message} / native-chain"),
        EmitRequest(scenario="native_group", count=4, message=f"{request.message} / native-group"),
        EmitRequest(scenario="native_chord", count=4, message=f"{request.message} / native-chord"),
    ]


_SCENARIO_HANDLERS: dict[str, AsyncScenarioEmitter] = {
    "native_success": _emit_native_success,
    "native_chain": _emit_native_chain,
    "native_group": _emit_native_group,
    "native_chord": _emit_native_chord,
    "parallel": _emit_parallel,
    "scheduled": _emit_scheduled,
    "success": _emit_job_scenario,
    "failure": _emit_job_scenario,
    "retry": _emit_job_scenario,
    "retry_success": _emit_job_scenario,
    "slow": _emit_job_scenario,
}


_SUITE_BUILDERS: dict[str, Callable[[EmitSuiteRequest], list[EmitRequest]]] = {
    "loom_long": _build_loom_long_suite,
    "native_graphs": _build_native_graph_suite,
    "observe_all": _build_observe_all_suite,
}

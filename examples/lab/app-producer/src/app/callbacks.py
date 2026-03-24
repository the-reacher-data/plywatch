"""Callbacks used by the producer lab app."""

from __future__ import annotations

from typing import Any

from loom.core.job.callback import JobCallback


class RecordSuccessCallback(JobCallback):
    """No-op success callback for generating callback tasks."""

    def on_success(self, job_id: str, result: Any, **context: Any) -> None:
        print("lab.success_callback", {"job_id": job_id, "result": result, "context": context})

    def on_failure(self, job_id: str, exc_type: str, exc_msg: str, **context: Any) -> None:
        print(
            "lab.success_callback.unexpected_failure",
            {"job_id": job_id, "exc_type": exc_type, "exc_msg": exc_msg, "context": context},
        )


class RecordFailureCallback(JobCallback):
    """No-op failure callback for generating callback tasks."""

    def on_success(self, job_id: str, result: Any, **context: Any) -> None:
        print(
            "lab.failure_callback.unexpected_success",
            {"job_id": job_id, "result": result, "context": context},
        )

    def on_failure(self, job_id: str, exc_type: str, exc_msg: str, **context: Any) -> None:
        print("lab.failure_callback", {"job_id": job_id, "exc_type": exc_type, "exc_msg": exc_msg})

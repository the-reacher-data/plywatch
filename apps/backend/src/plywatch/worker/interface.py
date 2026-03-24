"""REST interface for worker monitoring endpoints."""

from __future__ import annotations

from loom.rest.model import RestInterface, RestRoute

from plywatch.worker.models import WorkerSummaryView
from plywatch.worker.use_cases import ListWorkersUseCase


class WorkerRestInterface(RestInterface[WorkerSummaryView]):
    """Expose consolidated worker monitoring routes."""

    prefix = "/api/workers"
    tags = ("Workers",)
    routes = (
        RestRoute(
            use_case=ListWorkersUseCase,
            method="GET",
            path="/",
            summary="List workers",
            description="Returns consolidated Celery worker snapshots.",
        ),
    )

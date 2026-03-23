"""REST interface for monitor endpoints."""

from __future__ import annotations

from loom.rest.model import RestInterface, RestRoute

from plywatch.monitor.contracts import OverviewResponse
from plywatch.monitor.use_cases import GetOverviewUseCase, ListRawEventsUseCase


class MonitorRestInterface(RestInterface[OverviewResponse]):
    """Expose monitor overview and raw event routes."""

    prefix = "/api"
    tags = ("Monitor",)
    routes = (
        RestRoute(
            use_case=GetOverviewUseCase,
            method="GET",
            path="/overview",
            summary="Get monitor overview",
            description="Returns a compact overview of the monitor runtime.",
        ),
        RestRoute(
            use_case=ListRawEventsUseCase,
            method="GET",
            path="/events/raw",
            summary="List raw events",
            description="Returns recent raw Celery events retained in memory.",
        ),
    )

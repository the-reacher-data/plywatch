"""REST interface for observed schedule monitoring endpoints."""

from __future__ import annotations

from loom.rest.model import RestInterface, RestRoute

from plywatch.schedule.models import ScheduleSummaryView
from plywatch.schedule.use_cases import ListSchedulesUseCase


class ScheduleRestInterface(RestInterface[ScheduleSummaryView]):
    """Expose observed schedule summaries derived from task events."""

    prefix = "/api/schedules"
    tags = ("Schedules",)
    routes = (
        RestRoute(
            use_case=ListSchedulesUseCase,
            method="GET",
            path="",
            summary="List observed schedules",
            description="Returns schedule-origin task runs grouped from observed Celery events.",
        ),
    )

"""REST interface for task monitoring endpoints."""

from __future__ import annotations

from loom.core.repository.abc.query import PaginationMode
from loom.rest.model import RestInterface, RestRoute

from plywatch.task.models import TaskSummaryView
from plywatch.task.use_cases import (
    GetTaskGraphUseCase,
    GetTaskTimelineUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
)


class TaskRestInterface(RestInterface[TaskSummaryView]):
    """Expose consolidated task monitoring routes."""

    prefix = "/api/tasks"
    tags = ("Tasks",)
    pagination_mode = PaginationMode.CURSOR
    allow_pagination_override = False
    routes = (
        RestRoute(
            use_case=ListTasksUseCase,
            method="GET",
            path="/",
            summary="List recent tasks",
            description="Returns consolidated task snapshots for the monitor table.",
            pagination_mode=PaginationMode.CURSOR,
            allow_pagination_override=False,
        ),
        RestRoute(
            use_case=GetTaskUseCase,
            method="GET",
            path="/{task_id}",
            summary="Get task detail",
            description="Returns one consolidated task snapshot for drill-down views.",
        ),
        RestRoute(
            use_case=GetTaskTimelineUseCase,
            method="GET",
            path="/{task_id}/events",
            summary="Get task timeline",
            description="Returns retained lifecycle events for one task.",
        ),
        RestRoute(
            use_case=GetTaskGraphUseCase,
            method="GET",
            path="/{task_id}/graph",
            summary="Get task graph",
            description="Returns the workflow graph for one tracked task root.",
        ),
    )

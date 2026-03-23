"""REST interface for task section aggregate endpoints."""

from __future__ import annotations

from loom.rest.model import RestInterface, RestRoute

from plywatch.task.models import TaskSectionCountsView
from plywatch.task.use_cases import ListTaskSectionsUseCase


class TaskSectionsRestInterface(RestInterface[TaskSectionCountsView]):
    """Expose aggregate counters for the tasks page sections."""

    prefix = "/api"
    tags = ("Tasks",)
    routes = (
        RestRoute(
            use_case=ListTaskSectionsUseCase,
            method="GET",
            path="/task-sections",
            summary="Get task section counts",
            description="Returns total counters for the tasks page under the current filters.",
        ),
    )

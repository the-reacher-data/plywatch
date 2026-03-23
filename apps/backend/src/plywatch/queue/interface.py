"""REST interface for queue monitoring endpoints."""

from __future__ import annotations

from loom.rest.model import RestInterface, RestRoute

from plywatch.queue.models import QueueSummaryView
from plywatch.queue.use_cases import ListQueuesUseCase


class QueueRestInterface(RestInterface[QueueSummaryView]):
    """Expose consolidated queue monitoring routes."""

    prefix = "/api/queues"
    tags = ("Queues",)
    routes = (
        RestRoute(
            use_case=ListQueuesUseCase,
            method="GET",
            path="/",
            summary="List queues",
            description="Returns consolidated queue snapshots derived from task events.",
        ),
    )

"""Queue read use cases exposed by the Plywatch API."""

from __future__ import annotations

from loom.core.repository.abc.query import QuerySpec
from loom.core.use_case.use_case import UseCase

from plywatch.queue.models import QueueSnapshot, QueuesResponse, to_summary_view
from plywatch.queue.repository import QueueSnapshotRepository


class ListQueuesUseCase(UseCase[QueueSnapshot, QueuesResponse, QueueSnapshotRepository]):
    """Return tracked queues for the monitor runtime view."""

    read_only = True

    async def execute(self, query: QuerySpec) -> QueuesResponse:
        """Return recent queue snapshots.

        Args:
            query: Query options resolved from the request.

        Returns:
            A compact queue listing response.
        """
        limit = query.limit if query.limit is not None else 50
        items = self.main_repo.list_recent(limit)
        return QueuesResponse(
            items=tuple(to_summary_view(item) for item in items),
            count=self.main_repo.count(),
            limit=limit,
        )

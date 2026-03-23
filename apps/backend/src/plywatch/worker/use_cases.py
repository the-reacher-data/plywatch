"""Worker read use cases exposed by the Plywatch API."""

from __future__ import annotations

from loom.core.repository.abc.query import QuerySpec
from loom.core.use_case.use_case import UseCase

from plywatch.worker.models import WorkerSnapshot, WorkersResponse, to_summary_view
from plywatch.worker.repository import WorkerSnapshotRepository


class ListWorkersUseCase(UseCase[WorkerSnapshot, WorkersResponse, WorkerSnapshotRepository]):
    """Return tracked workers for the monitor runtime view."""

    read_only = True

    async def execute(self, query: QuerySpec) -> WorkersResponse:
        """Return recent worker snapshots.

        Args:
            query: Query options resolved from the request.

        Returns:
            A compact worker listing response.
        """
        limit = query.limit if query.limit is not None else 50
        items = self.main_repo.list_recent(limit)
        return WorkersResponse(
            items=tuple(to_summary_view(item) for item in items),
            count=self.main_repo.count(),
            limit=limit,
        )

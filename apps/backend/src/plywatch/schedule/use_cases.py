"""Schedule read use cases exposed by the Plywatch API."""

from __future__ import annotations

from loom.core.repository.abc.query import QuerySpec
from loom.core.use_case.use_case import UseCase

from plywatch.schedule.models import SchedulesResponse, build_schedule_summaries
from plywatch.schedule.repository import ScheduleRunSnapshot, ScheduleRunSnapshotRepository


class ListSchedulesUseCase(UseCase[ScheduleRunSnapshot, SchedulesResponse, ScheduleRunSnapshotRepository]):
    """Return observed schedules grouped from task lifecycle events."""

    read_only = True

    async def execute(self, query: QuerySpec) -> SchedulesResponse:
        """Return schedule summaries for the current task query filters."""

        limit = query.limit if query.limit is not None else 25
        snapshots = self.main_repo.list_all()
        items = build_schedule_summaries(snapshots, limit=limit)
        return SchedulesResponse(items=items, count=len(items), limit=limit)

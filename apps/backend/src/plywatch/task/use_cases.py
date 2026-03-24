"""Task read use cases exposed by the Plywatch API."""

from __future__ import annotations

from loom.core.errors import NotFound
from loom.core.repository.abc.query import CursorResult, FilterGroup, FilterSpec, FilterOp, QuerySpec
from loom.core.use_case.use_case import UseCase

from plywatch.task.constants import (
    CANVAS_KINDS,
    TASK_SECTION_FAILED,
    TASK_SECTION_QUEUED,
    TASK_SECTION_RUNNING,
    TASK_SECTION_SUCCEEDED,
    TaskSectionName,
)
from plywatch.task.families import build_section_counts, build_section_page
from plywatch.task.graph_builder import TaskGraphBuilder
from plywatch.task.read_repository import TaskReadRepository
from plywatch.task.models import (
    TaskSnapshot,
    TaskDetailView,
    TaskGraphResponse,
    TaskSectionCountsView,
    TaskSummaryView,
    TaskTimelineResponse,
    to_detail_view,
    to_summary_view,
    to_timeline_event_view,
)

_TASK_GRAPH_BUILDER = TaskGraphBuilder()
_TASK_SECTIONS: frozenset[TaskSectionName] = frozenset({
    TASK_SECTION_QUEUED,
    TASK_SECTION_RUNNING,
    TASK_SECTION_SUCCEEDED,
    TASK_SECTION_FAILED,
})
_SECTION_NAMES: dict[str, TaskSectionName] = {
    TASK_SECTION_QUEUED: TASK_SECTION_QUEUED,
    TASK_SECTION_RUNNING: TASK_SECTION_RUNNING,
    TASK_SECTION_SUCCEEDED: TASK_SECTION_SUCCEEDED,
    TASK_SECTION_FAILED: TASK_SECTION_FAILED,
}


class ListTasksUseCase(UseCase[TaskSnapshot, CursorResult[TaskSummaryView]]):
    """Return recent consolidated tasks for the main monitor table."""

    read_only = True

    def __init__(self, task_read_repository: TaskReadRepository) -> None:
        self._task_read_repository = task_read_repository

    async def execute(self, query: QuerySpec) -> CursorResult[TaskSummaryView]:
        """Return recent task snapshots.

        Args:
            query: Query options resolved from the request.

        Returns:
            A cursor-paginated task listing response.
        """
        section, repository_query = _split_section_filter(query)
        limit = repository_query.limit if repository_query.limit is not None else 50
        if section is not None:
            page = build_section_page(
                self._task_read_repository.list_all(query=repository_query),
                section=section,
                limit=limit,
                cursor=repository_query.cursor,
            )
            return CursorResult(
                items=tuple(to_summary_view(item) for item in page.items),
                next_cursor=page.next_cursor,
                has_next=page.has_next,
            )

        items, next_cursor, has_next = self._task_read_repository.list_recent_cursor(query=repository_query)
        return CursorResult(
            items=tuple(to_summary_view(item) for item in items),
            next_cursor=next_cursor,
            has_next=has_next,
        )


class GetTaskUseCase(UseCase[TaskSnapshot, TaskDetailView]):
    """Return one consolidated task with detail fields for drill-down."""

    read_only = True

    def __init__(self, task_read_repository: TaskReadRepository) -> None:
        self._task_read_repository = task_read_repository

    async def execute(self, task_id: str) -> TaskDetailView:
        """Return one task detail view.

        Args:
            task_id: Celery task UUID.

        Returns:
            A detailed task view.

        Raises:
            NotFound: If the task UUID is not tracked.
        """
        snapshot = self._task_read_repository.get(task_id)
        if snapshot is None:
            raise NotFound("TaskSnapshot", id=task_id)
        return to_detail_view(snapshot)


class GetTaskTimelineUseCase(UseCase[TaskSnapshot, TaskTimelineResponse]):
    """Return the retained timeline for one consolidated task."""

    read_only = True

    def __init__(self, task_read_repository: TaskReadRepository) -> None:
        self._task_read_repository = task_read_repository

    async def execute(self, task_id: str) -> TaskTimelineResponse:
        """Return one task timeline response.

        Args:
            task_id: Celery task UUID.

        Returns:
            The retained task event timeline.

        Raises:
            NotFound: If the task UUID is not tracked.
        """
        snapshot = self._task_read_repository.get(task_id)
        if snapshot is None:
            raise NotFound("TaskSnapshot", id=task_id)
        return TaskTimelineResponse(
            task_id=task_id,
            items=tuple(to_timeline_event_view(event) for event in snapshot.events),
            count=len(snapshot.events),
        )


class GetTaskGraphUseCase(UseCase[TaskSnapshot, TaskGraphResponse]):
    """Return the execution graph for one tracked task workflow."""

    read_only = True

    def __init__(self, task_read_repository: TaskReadRepository) -> None:
        self._task_read_repository = task_read_repository

    async def execute(self, task_id: str) -> TaskGraphResponse:
        """Return the graph around one tracked task.

        Args:
            task_id: Celery task UUID.

        Returns:
            The workflow graph rooted at the task execution root.

        Raises:
            NotFound: If the task UUID is not tracked.
        """
        snapshot = self._task_read_repository.get(task_id)
        if snapshot is None:
            raise NotFound("TaskSnapshot", id=task_id)
        items = (
            self._task_read_repository.list_by_canvas_id(snapshot.canvas_id)
            if snapshot.canvas_id is not None and snapshot.canvas_kind in CANVAS_KINDS
            else self._task_read_repository.list_by_root(snapshot.root_id or snapshot.uuid)
        )
        return _TASK_GRAPH_BUILDER.build(task_id=task_id, snapshot=snapshot, items=items)


class ListTaskSectionsUseCase(UseCase[TaskSnapshot, TaskSectionCountsView]):
    """Return aggregate counters for the tasks page sections."""

    read_only = True

    def __init__(self, task_read_repository: TaskReadRepository) -> None:
        self._task_read_repository = task_read_repository

    async def execute(self, query: QuerySpec) -> TaskSectionCountsView:
        """Return task section counts under the current filters."""

        _section, repository_query = _split_section_filter(query)
        return build_section_counts(self._task_read_repository.list_all(query=repository_query))


def _split_section_filter(query: QuerySpec) -> tuple[TaskSectionName | None, QuerySpec]:
    if query.filters is None or not query.filters.filters:
        return None, query

    section: TaskSectionName | None = None
    passthrough_filters: list[FilterSpec] = []
    for filter_spec in query.filters.filters:
        if filter_spec.field == "section" and filter_spec.op is FilterOp.EQ and isinstance(filter_spec.value, str):
            matched_section = _parse_section_name(filter_spec.value)
            if matched_section is not None:
                section = matched_section
            continue
        passthrough_filters.append(filter_spec)

    filters = FilterGroup(filters=tuple(passthrough_filters), op=query.filters.op) if passthrough_filters else None
    return section, QuerySpec(
        filters=filters,
        sort=query.sort,
        pagination=query.pagination,
        limit=query.limit,
        page=query.page,
        cursor=query.cursor,
    )


def _parse_section_name(value: str) -> TaskSectionName | None:
    return _SECTION_NAMES.get(value)

"""Task family aggregation rules shared by API sections and UI semantics."""

from __future__ import annotations

import base64
import json
from datetime import datetime

from loom.core.model import LoomStruct

from plywatch.task.constants import (
    CANVAS_ROOT_PREFIX,
    COMPLETED_TASK_STATES,
    HIDDEN_ROOT_TASK_KINDS,
    QUEUED_TASK_STATES,
    RUNNING_TASK_STATES,
    TASK_KIND_CALLBACK_ERROR,
    TASK_KIND_JOB,
    TASK_SECTION_FAILED,
    TASK_SECTION_QUEUED,
    TASK_SECTION_RUNNING,
    TASK_SECTION_SUCCEEDED,
    TASK_STATE_LOST,
    TASK_STATE_FAILED,
    TASK_STATE_SENT,
    TASK_STATE_STARTED,
    TASK_STATE_SUCCEEDED,
    TaskSectionName,
)
from plywatch.task.models import TaskSectionCountsView, TaskSnapshot, TaskState
from plywatch.task.policies import is_future_scheduled_task

_SECTION_TO_AGGREGATE_STATE: dict[TaskSectionName, TaskState] = {
    TASK_SECTION_QUEUED: TASK_STATE_SENT,
    TASK_SECTION_RUNNING: TASK_STATE_STARTED,
    TASK_SECTION_SUCCEEDED: TASK_STATE_SUCCEEDED,
    TASK_SECTION_FAILED: TASK_STATE_FAILED,
}


class TaskFamilyAggregate(LoomStruct, frozen=True, kw_only=True):
    aggregate_state: TaskState
    completed_count: int
    total_count: int
    has_visible_root: bool


class TaskFamily(LoomStruct, frozen=True, kw_only=True):
    key: str
    root: TaskSnapshot
    items: tuple[TaskSnapshot, ...]


class TaskFamilyPage(LoomStruct, frozen=True, kw_only=True):
    items: tuple[TaskSnapshot, ...]
    next_cursor: str | None
    has_next: bool


class TaskFamilyClassifier:
    """Encapsulate workflow-family grouping and state aggregation rules."""

    def build_families(self, snapshots: list[TaskSnapshot]) -> list[TaskFamily]:
        grouped = self._group_by_family_key(snapshots)
        families: list[TaskFamily] = []
        for key, family_items in grouped.items():
            families.extend(self._split_family(key=key, items=family_items))
        return [family for family in families if self._has_visible_root(family.items)]

    def to_aggregate(self, family: TaskFamily) -> TaskFamilyAggregate:
        aggregate_state = self._aggregate_state(family)
        completed_count = sum(1 for item in family.items if item.state in COMPLETED_TASK_STATES)
        return TaskFamilyAggregate(
            aggregate_state=aggregate_state,
            completed_count=completed_count,
            total_count=len(family.items),
            has_visible_root=self._has_visible_root(family.items),
        )

    def family_key_for(self, snapshot: TaskSnapshot) -> str:
        if snapshot.canvas_id is not None:
            return f"{CANVAS_ROOT_PREFIX}{snapshot.canvas_id}"
        return snapshot.root_id or snapshot.uuid

    def family_last_seen_at(self, family: TaskFamily) -> str:
        return max(item.last_seen_at for item in family.items)

    def _group_by_family_key(self, snapshots: list[TaskSnapshot]) -> dict[str, list[TaskSnapshot]]:
        grouped: dict[str, list[TaskSnapshot]] = {}
        for snapshot in snapshots:
            grouped.setdefault(self.family_key_for(snapshot), []).append(snapshot)
        return grouped

    def _split_family(self, *, key: str, items: list[TaskSnapshot]) -> list[TaskFamily]:
        root = self._pick_root(key=key, items=items)
        detached_items = self._detached_queued_children(root=root, items=items)
        detached_ids = {item.uuid for item in detached_items}
        primary_items = tuple(item for item in items if item.uuid not in detached_ids)

        families: list[TaskFamily] = []
        if primary_items:
            families.append(TaskFamily(key=key, root=self._pick_root(key=key, items=list(primary_items)), items=primary_items))
        for detached_item in sorted(detached_items, key=self._snapshot_order_key):
            families.append(TaskFamily(key=detached_item.uuid, root=detached_item, items=(detached_item,)))
        return families

    def _detached_queued_children(self, *, root: TaskSnapshot, items: list[TaskSnapshot]) -> list[TaskSnapshot]:
        if root.state in QUEUED_TASK_STATES:
            return []
        return [
            item
            for item in items
            if item.uuid != root.uuid and item.parent_id is not None and item.state in QUEUED_TASK_STATES
        ]

    def _aggregate_state(self, family: TaskFamily) -> TaskState:
        if self._all_items_queued(family.items):
            return TASK_STATE_SENT
        if self._has_running_item(family.items):
            return TASK_STATE_STARTED
        if self._is_failed_family(family):
            return TASK_STATE_FAILED
        return TASK_STATE_SUCCEEDED

    def _all_items_queued(self, items: tuple[TaskSnapshot, ...]) -> bool:
        return all(item.state in QUEUED_TASK_STATES for item in items)

    def _has_running_item(self, items: tuple[TaskSnapshot, ...]) -> bool:
        return any(item.state in RUNNING_TASK_STATES for item in items)

    def _is_failed_family(self, family: TaskFamily) -> bool:
        if family.root.state == TASK_STATE_FAILED:
            return True
        if family.root.state == TASK_STATE_LOST:
            return True
        if family.root.kind == TASK_KIND_CALLBACK_ERROR:
            return True
        return any(item.kind == TASK_KIND_JOB and item.state in {TASK_STATE_FAILED, TASK_STATE_LOST} for item in family.items)

    def _pick_root(self, *, key: str, items: list[TaskSnapshot]) -> TaskSnapshot:
        ids = {item.uuid for item in items}
        parent_ids = {item.parent_id for item in items if item.parent_id is not None and item.parent_id in ids}
        ordered = sorted(items, key=self._snapshot_order_key)
        candidate_groups = (
            (
                item
                for item in items
                if self._is_visible_root_kind(item.kind) and item.uuid == key and item.parent_id != item.uuid
            ),
            (item for item in items if self._is_visible_root_kind(item.kind) and item.parent_id is None),
            (item for item in items if self._is_visible_root_kind(item.kind) and item.uuid in parent_ids),
            (item for item in items if item.uuid == key and item.parent_id != item.uuid),
            (item for item in items if item.parent_id is None),
            (item for item in items if item.uuid in parent_ids),
            (item for item in items if item.uuid == key),
        )
        for candidates in candidate_groups:
            match = next(candidates, None)
            if match is not None:
                return match
        return ordered[0]

    def _has_visible_root(self, items: tuple[TaskSnapshot, ...] | list[TaskSnapshot]) -> bool:
        return any(self._is_visible_root_kind(item.kind) for item in items)

    def _is_visible_root_kind(self, kind: str) -> bool:
        return kind not in HIDDEN_ROOT_TASK_KINDS

    def _snapshot_order_key(self, snapshot: TaskSnapshot) -> tuple[str, str]:
        return (snapshot.first_seen_at, snapshot.uuid)


def build_section_counts(snapshots: list[TaskSnapshot]) -> TaskSectionCountsView:
    """Return section counters matching the frontend family grouping rules."""

    history_snapshots = [snapshot for snapshot in snapshots if not is_future_scheduled_task(snapshot)]
    classifier = TaskFamilyClassifier()
    aggregates = [classifier.to_aggregate(family) for family in classifier.build_families(history_snapshots)]
    return TaskSectionCountsView(
        queued_families=sum(1 for family in aggregates if family.aggregate_state == TASK_STATE_SENT),
        running_families=sum(1 for family in aggregates if family.aggregate_state == TASK_STATE_STARTED),
        succeeded_families=sum(1 for family in aggregates if family.aggregate_state == TASK_STATE_SUCCEEDED),
        failed_families=sum(1 for family in aggregates if family.aggregate_state == TASK_STATE_FAILED),
        family_count=len(aggregates),
        execution_count=len(history_snapshots),
        completed_executions=sum(family.completed_count for family in aggregates),
        total_executions=sum(family.total_count for family in aggregates),
    )


def build_section_page(
    snapshots: list[TaskSnapshot],
    *,
    section: TaskSectionName,
    limit: int,
    cursor: str | None,
) -> TaskFamilyPage:
    """Return one cursor page of task snapshots grouped by logical section families."""

    history_snapshots = [snapshot for snapshot in snapshots if not is_future_scheduled_task(snapshot)]
    classifier = TaskFamilyClassifier()
    families = classifier.build_families(history_snapshots)
    families = [family for family in families if _matches_section(classifier, family, section)]
    families.sort(key=lambda family: (_parse_iso8601(classifier.family_last_seen_at(family)), family.key), reverse=True)

    anchor = _decode_family_cursor(cursor) if cursor is not None else None
    if anchor is not None:
        families = [
            family
            for family in families
            if (_parse_iso8601(classifier.family_last_seen_at(family)), family.key) < anchor
        ]

    page_families = families[:limit]
    has_next = len(families) > limit
    next_cursor = None
    if has_next and page_families:
        last_family = page_families[-1]
        next_cursor = _encode_family_cursor(classifier.family_last_seen_at(last_family), last_family.key)

    items = tuple(item for family in page_families for item in family.items)
    return TaskFamilyPage(items=items, next_cursor=next_cursor, has_next=has_next)


def _matches_section(
    classifier: TaskFamilyClassifier,
    family: TaskFamily,
    section: TaskSectionName,
) -> bool:
    aggregate_state = classifier.to_aggregate(family).aggregate_state
    return aggregate_state == _SECTION_TO_AGGREGATE_STATE[section]


def _encode_family_cursor(last_seen_at: str, family_key: str) -> str:
    payload = {"last_seen_at": last_seen_at, "family_key": family_key}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    return encoded.decode("utf-8")


def _decode_family_cursor(cursor: str) -> tuple[datetime, str]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
    return _parse_iso8601(str(payload["last_seen_at"])), str(payload["family_key"])


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value)

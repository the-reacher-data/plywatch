from __future__ import annotations

from plywatch.task.models import (
    TaskSnapshot,
    _public_parent_id,
    classify_task_kind,
    to_detail_view,
    to_summary_view,
)
from plywatch.task.graph_builder import TaskGraphBuilder

_GRAPH_BUILDER = TaskGraphBuilder()


def test_classify_task_kind_covers_supported_prefixes_and_fallbacks() -> None:
    assert classify_task_kind(None) == "unknown"
    assert classify_task_kind("loom.callback_error.RecordFailureCallback") == "callback_error"
    assert classify_task_kind("loom.callback.RecordSuccessCallback") == "callback"
    assert classify_task_kind("loom.job.HelloSuccessJob") == "job"
    assert classify_task_kind("other.namespace.Task") == "unknown"


def test_public_parent_id_returns_parent_for_non_canvas_tasks() -> None:
    snapshot = TaskSnapshot(uuid="task-1", parent_id="parent-1")

    assert _public_parent_id(snapshot) == "parent-1"
    assert to_summary_view(snapshot).parent_id == "parent-1"
    assert to_detail_view(snapshot).parent_id == "parent-1"


def test_public_parent_id_hides_group_and_chord_members() -> None:
    for canvas_kind in ("group", "chord"):
        snapshot = TaskSnapshot(
            uuid=f"{canvas_kind}-task",
            parent_id="parent-1",
            canvas_kind=canvas_kind,
            canvas_id=f"{canvas_kind}-canvas",
        )

        assert _public_parent_id(snapshot) is None
        assert to_summary_view(snapshot).parent_id is None
        assert to_detail_view(snapshot).parent_id is None


def test_public_parent_id_hides_chain_head_but_keeps_chain_tail_parent() -> None:
    head = TaskSnapshot(
        uuid="chain-head",
        parent_id="parent-1",
        canvas_kind="chain",
        canvas_id="canvas-1",
        canvas_role="head",
    )
    tail = TaskSnapshot(
        uuid="chain-tail",
        parent_id="parent-1",
        canvas_kind="chain",
        canvas_id="canvas-1",
        canvas_role="tail",
    )

    assert _public_parent_id(head) is None
    assert to_summary_view(head).parent_id is None
    assert to_detail_view(head).parent_id is None

    assert _public_parent_id(tail) == "parent-1"
    assert to_summary_view(tail).parent_id == "parent-1"
    assert to_detail_view(tail).parent_id == "parent-1"


def test_relation_for_matches_task_kind() -> None:
    assert _GRAPH_BUILDER.relation_for(TaskSnapshot(uuid="task-job", kind="job")) == "child"
    assert _GRAPH_BUILDER.relation_for(TaskSnapshot(uuid="task-callback", kind="callback")) == "callback"
    assert _GRAPH_BUILDER.relation_for(TaskSnapshot(uuid="task-callback-error", kind="callback_error")) == "callback_error"

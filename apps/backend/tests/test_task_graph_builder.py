from __future__ import annotations

from plywatch.task.graph_builder import TaskGraphBuilder
from plywatch.task.models import TaskSnapshot


def test_graph_builder_builds_root_graph_for_parent_and_callback() -> None:
    builder = TaskGraphBuilder()
    parent = TaskSnapshot(
        uuid="parent-1",
        kind="job",
        state="succeeded",
        root_id="parent-1",
        first_seen_at="2026-03-19T00:00:01+00:00",
    )
    child = TaskSnapshot(
        uuid="child-1",
        kind="callback",
        state="succeeded",
        root_id="parent-1",
        parent_id="parent-1",
        first_seen_at="2026-03-19T00:00:02+00:00",
    )

    graph = builder.build(task_id="child-1", snapshot=child, items=[parent, child])

    assert graph.root_id == "parent-1"
    assert {node.uuid for node in graph.nodes} == {"parent-1", "child-1"}
    assert [(edge.source, edge.target, edge.relation) for edge in graph.edges] == [
        ("parent-1", "child-1", "callback")
    ]


def test_graph_builder_builds_group_canvas_with_canvas_root() -> None:
    builder = TaskGraphBuilder()
    header = TaskSnapshot(
        uuid="member-1",
        kind="unknown",
        state="started",
        queue="default",
        canvas_kind="group",
        canvas_id="canvas-1",
        canvas_role="member",
        first_seen_at="2026-03-19T00:00:01+00:00",
    )
    member = TaskSnapshot(
        uuid="member-2",
        kind="unknown",
        state="sent",
        queue="default",
        canvas_kind="group",
        canvas_id="canvas-1",
        canvas_role="member",
        first_seen_at="2026-03-19T00:00:02+00:00",
    )

    graph = builder.build(task_id="member-1", snapshot=header, items=[header, member])

    assert graph.root_id == "canvas:canvas-1"
    assert graph.nodes[0].uuid == "canvas:canvas-1"
    assert graph.nodes[0].kind == "canvas"
    assert graph.nodes[0].state == "started"
    assert [(edge.source, edge.target, edge.relation) for edge in graph.edges] == [
        ("canvas:canvas-1", "member-1", "member"),
        ("canvas:canvas-1", "member-2", "member"),
    ]


def test_graph_builder_builds_chain_with_head_to_tail_edge() -> None:
    builder = TaskGraphBuilder()
    head = TaskSnapshot(
        uuid="head-1",
        kind="unknown",
        state="succeeded",
        queue="default",
        canvas_kind="chain",
        canvas_id="chain-1",
        canvas_role="head",
        first_seen_at="2026-03-19T00:00:01+00:00",
    )
    tail = TaskSnapshot(
        uuid="tail-1",
        kind="unknown",
        state="succeeded",
        queue="default",
        canvas_kind="chain",
        canvas_id="chain-1",
        canvas_role="tail",
        first_seen_at="2026-03-19T00:00:02+00:00",
    )

    graph = builder.build(task_id="tail-1", snapshot=tail, items=[head, tail])

    assert graph.root_id == "canvas:chain-1"
    assert [(edge.source, edge.target, edge.relation) for edge in graph.edges] == [
        ("canvas:chain-1", "head-1", "head"),
        ("head-1", "tail-1", "chain"),
    ]
    node_by_id = {node.uuid: node for node in graph.nodes}
    assert node_by_id["head-1"].parent_id == "canvas:chain-1"
    assert node_by_id["tail-1"].parent_id == "head-1"

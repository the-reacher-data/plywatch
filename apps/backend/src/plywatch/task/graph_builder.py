"""Builders for public task graph responses."""

from __future__ import annotations

from plywatch.task.constants import (
    CANVAS_ROOT_PREFIX,
    RUNNING_TASK_STATES,
    TASK_KIND_CALLBACK,
    TASK_KIND_CALLBACK_ERROR,
    TASK_RELATION_CALLBACK,
    TASK_RELATION_CALLBACK_ERROR,
    TASK_RELATION_CHILD,
    TASK_STATE_FAILED,
    TASK_STATE_STARTED,
    TASK_STATE_SUCCEEDED,
)
from plywatch.task.models import (
    TaskGraphEdgeView,
    TaskGraphNodeView,
    TaskGraphResponse,
    TaskSnapshot,
    to_graph_node_view,
)


class TaskGraphBuilder:
    """Build public graph responses from consolidated task snapshots."""

    def build(self, *, task_id: str, snapshot: TaskSnapshot, items: list[TaskSnapshot]) -> TaskGraphResponse:
        if snapshot.canvas_id is not None and snapshot.canvas_kind in {"chain", "group", "chord"}:
            return self._build_canvas_graph(task_id=task_id, snapshot=snapshot, items=items)
        return self._build_root_graph(task_id=task_id, snapshot=snapshot, items=items)

    def relation_for(self, item: TaskSnapshot) -> str:
        if item.kind == TASK_KIND_CALLBACK:
            return TASK_RELATION_CALLBACK
        if item.kind == TASK_KIND_CALLBACK_ERROR:
            return TASK_RELATION_CALLBACK_ERROR
        return TASK_RELATION_CHILD

    def canvas_root_id_for(self, canvas_id: str | None) -> str:
        return f"{CANVAS_ROOT_PREFIX}{canvas_id}" if canvas_id is not None else f"{CANVAS_ROOT_PREFIX}unknown"

    def _build_root_graph(
        self,
        *,
        task_id: str,
        snapshot: TaskSnapshot,
        items: list[TaskSnapshot],
    ) -> TaskGraphResponse:
        root_id = snapshot.root_id or snapshot.uuid
        by_id = {item.uuid: item for item in items}
        edges: list[TaskGraphEdgeView] = []
        for item in items:
            if item.parent_id is None or item.parent_id not in by_id:
                continue
            edges.append(
                TaskGraphEdgeView(
                    source=item.parent_id,
                    target=item.uuid,
                    relation=self.relation_for(item),
                )
            )
        return TaskGraphResponse(
            task_id=task_id,
            root_id=root_id,
            nodes=tuple(to_graph_node_view(item) for item in items),
            edges=tuple(edges),
        )

    def _build_canvas_graph(
        self,
        *,
        task_id: str,
        snapshot: TaskSnapshot,
        items: list[TaskSnapshot],
    ) -> TaskGraphResponse:
        if snapshot.canvas_kind == "chain":
            return self._build_chain_graph(task_id=task_id, snapshot=snapshot, items=items)

        canvas_root_id = self.canvas_root_id_for(snapshot.canvas_id)
        edges = tuple(
            TaskGraphEdgeView(
                source=canvas_root_id,
                target=item.uuid,
                relation=item.canvas_role or "member",
            )
            for item in items
        )
        nodes = (
            self._build_canvas_root_node(canvas_root_id=canvas_root_id, canvas_kind=snapshot.canvas_kind or "native", items=items),
            *(
                TaskGraphNodeView(
                    uuid=item.uuid,
                    name=item.name,
                    kind=item.kind,
                    state=item.state,
                    root_id=canvas_root_id,
                    parent_id=canvas_root_id,
                    queue=item.queue,
                    worker_hostname=item.worker_hostname,
                )
                for item in items
            ),
        )
        return TaskGraphResponse(
            task_id=task_id,
            root_id=canvas_root_id,
            nodes=nodes,
            edges=edges,
        )

    def _build_chain_graph(
        self,
        *,
        task_id: str,
        snapshot: TaskSnapshot,
        items: list[TaskSnapshot],
    ) -> TaskGraphResponse:
        canvas_root_id = self.canvas_root_id_for(snapshot.canvas_id)
        ordered_items = sorted(items, key=lambda item: (item.first_seen_at, item.uuid))
        head = next((item for item in ordered_items if item.canvas_role == "head"), ordered_items[0])
        tail = next((item for item in ordered_items if item.canvas_role == "tail"), ordered_items[-1])

        nodes: list[TaskGraphNodeView] = [self._build_canvas_root_node(canvas_root_id=canvas_root_id, canvas_kind="chain", items=ordered_items)]
        for item in ordered_items:
            parent_id = canvas_root_id
            if item.uuid == tail.uuid and item.uuid != head.uuid:
                parent_id = head.uuid
            nodes.append(
                TaskGraphNodeView(
                    uuid=item.uuid,
                    name=item.name,
                    kind=item.kind,
                    state=item.state,
                    root_id=canvas_root_id,
                    parent_id=parent_id,
                    queue=item.queue,
                    worker_hostname=item.worker_hostname,
                )
            )

        edges = [TaskGraphEdgeView(source=canvas_root_id, target=head.uuid, relation="head")]
        if tail.uuid != head.uuid:
            edges.append(TaskGraphEdgeView(source=head.uuid, target=tail.uuid, relation="chain"))

        return TaskGraphResponse(
            task_id=task_id,
            root_id=canvas_root_id,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )

    def _build_canvas_root_node(
        self,
        *,
        canvas_root_id: str,
        canvas_kind: str,
        items: list[TaskSnapshot],
    ) -> TaskGraphNodeView:
        return TaskGraphNodeView(
            uuid=canvas_root_id,
            name=f"native {canvas_kind}",
            kind="canvas",
            state=self._canvas_state(items),
            root_id=canvas_root_id,
            parent_id=None,
            queue=self._shared_queue(items),
            worker_hostname=None,
        )

    def _canvas_state(self, items: list[TaskSnapshot]) -> str:
        if any(item.state == TASK_STATE_FAILED for item in items):
            return TASK_STATE_FAILED
        if any(item.state in RUNNING_TASK_STATES for item in items):
            return TASK_STATE_STARTED
        return TASK_STATE_SUCCEEDED

    def _shared_queue(self, items: list[TaskSnapshot]) -> str | None:
        queues = {item.queue for item in items if item.queue is not None}
        if len(queues) == 1:
            return next(iter(queues))
        return None

import type { TaskDetail, TaskGraph, TaskSummary, TaskState } from '$lib/core/contracts/monitor';

export interface FamilyTreeNode {
  id: string;
  name: string | null;
  state: TaskState;
  retries: number;
  startedAt: string | null;
  finishedAt: string | null;
  sentAt: string | null;
  depth: number;
  isLastChild: boolean;
  children: FamilyTreeNode[];
}

function buildChildrenIndex(graph: TaskGraph): Map<string, string[]> {
  const index = new Map<string, string[]>();

  // Primary: parentId on each node — reliable for standard task chains.
  // Guards:
  //   • root is never a child (Celery chords can set parentId on the root itself)
  //   • skip self-referential parentId (node pointing to itself)
  const coveredByParentId = new Set<string>();
  for (const node of graph.nodes) {
    if (node.parentId === null) continue;
    if (node.id === graph.rootId) continue;
    if (node.id === node.parentId) continue;
    const list = index.get(node.parentId) ?? [];
    if (!list.includes(node.id)) list.push(node.id);
    index.set(node.parentId, list);
    coveredByParentId.add(node.id);
  }

  // Supplemental: edges for nodes NOT covered by parentId.
  // Callbacks (link/link_error) and errbacks have parentId=null but appear in edges.
  // Guards: root is never a child; self-loops are skipped.
  for (const edge of graph.edges) {
    if (coveredByParentId.has(edge.target)) continue;
    if (edge.target === graph.rootId) continue;
    if (edge.target === edge.source) continue;
    const list = index.get(edge.source) ?? [];
    if (!list.includes(edge.target)) list.push(edge.target);
    index.set(edge.source, list);
  }

  return index;
}

function buildNode(
  nodeId: string,
  graph: TaskGraph,
  byId: Map<string, TaskSummary>,
  childrenIndex: Map<string, string[]>,
  depth: number,
  isLastChild: boolean,
  visited: Set<string>
): FamilyTreeNode {
  const graphNode = graph.nodes.find((n) => n.id === nodeId);
  const summary = byId.get(nodeId);

  const nextVisited = new Set([...visited, nodeId]);
  const childIds = (childrenIndex.get(nodeId) ?? []).filter((id) => !visited.has(id));
  const children = childIds.map((childId, idx) =>
    buildNode(childId, graph, byId, childrenIndex, depth + 1, idx === childIds.length - 1, nextVisited)
  );

  return {
    id: nodeId,
    name: graphNode?.name ?? summary?.name ?? null,
    state: graphNode?.state ?? summary?.state ?? 'sent',
    retries: summary?.retries ?? 0,
    startedAt: summary?.startedAt ?? null,
    finishedAt: summary?.finishedAt ?? null,
    sentAt: summary?.sentAt ?? null,
    depth,
    isLastChild,
    children
  };
}

/**
 * Builds a recursive family tree always rooted at `graph.rootId`.
 *
 * The selected task (TaskDetail) provides richer timing than TaskSummary and is
 * injected into the lookup before building. If the root task is not the selected
 * one, root timing comes from `byId` (allTasks) or falls back to null.
 *
 * Callback / errback nodes that have `parentId === null` are picked up via graph
 * edges so they always appear in the tree.
 */
export function buildFamilyTree(
  selectedTask: TaskDetail,
  graph: TaskGraph,
  byId: Map<string, TaskSummary>
): FamilyTreeNode {
  const childrenIndex = buildChildrenIndex(graph);

  // Inject selected task detail into lookup — it has more accurate timing than TaskSummary.
  const enrichedById = new Map(byId);
  enrichedById.set(selectedTask.id, selectedTask);

  // Always root at the graph's declared root. If rootId is missing from nodes
  // (rare edge case), fall back to selectedTask.
  const rootId = graph.nodes.some((n) => n.id === graph.rootId)
    ? graph.rootId
    : selectedTask.id;

  return buildNode(rootId, graph, enrichedById, childrenIndex, 0, true, new Set());
}

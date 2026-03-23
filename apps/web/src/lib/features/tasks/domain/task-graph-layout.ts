import type {
  TaskDetail,
  TaskGraph,
  TaskGraphEdge,
  TaskGraphNode,
  TaskSummary,
} from '$lib/core/contracts/monitor';

export interface DagLayoutNode {
  id: string;
  name: string | null;
  state: string;
  queue: string | null;
  workerHostname: string | null;
  retries: number;
  startedAt: string | null;
  finishedAt: string | null;
  sentAt: string | null;
  phase: number;
  role: string | null;
}

export interface DagPhase {
  key: string;
  index: number;
  label: string;
  nodes: DagLayoutNode[];
}

export interface DagStats {
  total: number;
  done: number;
  running: number;
  queued: number;
  failed: number;
  maxPhaseSize: number;
  hasParallelism: boolean;
  hasJoin: boolean;
  isCanvasRooted: boolean;
}

export interface DagLayout {
  phases: DagPhase[];
  stats: DagStats;
}

function resolveTask(
  taskId: string,
  root: TaskDetail,
  byId: Map<string, TaskSummary>,
): TaskSummary | TaskDetail | undefined {
  return taskId === root.id ? root : byId.get(taskId);
}

function roleBaseRank(role: string | null, isCanvasRooted: boolean): number {
  if (role === 'head' || role === 'header' || role === 'member') return 0;
  if (role === 'tail' || role === 'body') return 1;
  return isCanvasRooted ? 1 : 0;
}

function buildNodeView(
  graphNode: TaskGraphNode,
  root: TaskDetail,
  byId: Map<string, TaskSummary>,
  phase: number,
): DagLayoutNode {
  const task = resolveTask(graphNode.id, root, byId);
  return {
    id: graphNode.id,
    name: graphNode.name ?? task?.name ?? graphNode.id,
    state: graphNode.state ?? task?.state ?? 'sent',
    queue: graphNode.queue ?? task?.queue ?? null,
    workerHostname: graphNode.workerHostname ?? task?.workerHostname ?? null,
    retries: task?.retries ?? 0,
    startedAt: task?.startedAt ?? null,
    finishedAt: task?.finishedAt ?? null,
    sentAt: task?.sentAt ?? null,
    phase,
    role: task?.canvasRole ?? null,
  };
}

function buildStats(nodes: DagLayoutNode[]): DagStats {
  const maxPhaseSize = nodes.reduce((max, node) => Math.max(max, node.phase + 1), 0);
  return {
    total: nodes.length,
    done: nodes.filter((node) => node.state === 'succeeded' || node.state === 'failed' || node.state === 'lost').length,
    running: nodes.filter((node) => node.state === 'started' || node.state === 'received' || node.state === 'retrying')
      .length,
    queued: nodes.filter((node) => node.state === 'sent').length,
    failed: nodes.filter((node) => node.state === 'failed' || node.state === 'lost').length,
    maxPhaseSize,
    hasParallelism: false,
    hasJoin: false,
    isCanvasRooted: false,
  };
}

function phaseLabel(phaseIndex: number): string {
  return `Stage ${phaseIndex + 1}`;
}

function relevantEdges(
  edges: TaskGraphEdge[],
  nodeIds: Set<string>,
  rootId: string,
): TaskGraphEdge[] {
  return edges.filter(
    (edge) =>
      (edge.source === rootId || nodeIds.has(edge.source)) &&
      nodeIds.has(edge.target) &&
      edge.source !== edge.target,
  );
}

export function buildTaskDagLayout(
  root: TaskDetail,
  graph: TaskGraph,
  byId: Map<string, TaskSummary>,
): DagLayout {
  const isCanvasRooted = graph.nodes.some((node) => node.id === graph.rootId && node.kind === 'canvas');
  const contentNodes = graph.nodes.filter((node) => !(node.id === graph.rootId && node.kind === 'canvas'));
  const nodeIds = new Set(contentNodes.map((node) => node.id));
  const rankById = new Map<string, number>();

  for (const node of contentNodes) {
    const task = resolveTask(node.id, root, byId);
    rankById.set(node.id, roleBaseRank(task?.canvasRole ?? null, isCanvasRooted));
  }

  const edges = relevantEdges(graph.edges, nodeIds, graph.rootId);
  for (let i = 0; i < contentNodes.length; i++) {
    let changed = false;
    for (const edge of edges) {
      const targetRank = rankById.get(edge.target) ?? 0;
      const sourceRank =
        edge.source === graph.rootId && isCanvasRooted
          ? -1
          : (rankById.get(edge.source) ?? 0);
      const nextRank = Math.max(targetRank, sourceRank + 1);
      if (nextRank !== targetRank) {
        rankById.set(edge.target, nextRank);
        changed = true;
      }
    }
    if (!changed) break;
  }

  const nodes = contentNodes.map((node) => buildNodeView(node, root, byId, rankById.get(node.id) ?? 0));
  const phasesMap = new Map<number, DagLayoutNode[]>();
  for (const node of nodes) {
    phasesMap.set(node.phase, [...(phasesMap.get(node.phase) ?? []), node]);
  }

  const phases = Array.from(phasesMap.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([phaseIndex, phaseNodes]) => {
      return {
        key: `phase-${phaseIndex}`,
        index: phaseIndex,
        label: phaseLabel(phaseIndex),
        nodes: phaseNodes.sort((left, right) => {
          const leftName = left.name ?? left.id;
          const rightName = right.name ?? right.id;
          return leftName.localeCompare(rightName);
        }),
      } satisfies DagPhase;
    });

  const stats = buildStats(nodes);
  stats.maxPhaseSize = phases.reduce((max, phase) => Math.max(max, phase.nodes.length), 0);
  stats.hasParallelism = phases.some((phase) => phase.nodes.length > 1);
  const incomingEdgeCountByTarget = new Map<string, number>();
  for (const edge of edges) {
    incomingEdgeCountByTarget.set(edge.target, (incomingEdgeCountByTarget.get(edge.target) ?? 0) + 1);
  }
  stats.hasJoin = Array.from(incomingEdgeCountByTarget.values()).some((count) => count > 1);
  stats.isCanvasRooted = isCanvasRooted;

  return {
    phases,
    stats,
  };
}

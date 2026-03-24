import { describe, expect, it } from 'vitest';

import type { TaskDetail, TaskGraph, TaskGraphEdge, TaskGraphNode, TaskSummary } from '$lib/core/contracts/monitor';
import { buildTaskDagLayout } from '$lib/features/tasks/domain/task-graph-layout';

function buildTask(overrides: Partial<TaskSummary> & { id: string }): TaskSummary {
  return {
    id: overrides.id,
    name: overrides.name ?? overrides.id,
    kind: overrides.kind ?? 'job',
    state: overrides.state ?? 'succeeded',
    queue: overrides.queue ?? 'default',
    routingKey: overrides.routingKey ?? 'default',
    rootId: overrides.rootId ?? overrides.id,
    parentId: overrides.parentId ?? null,
    childrenIds: overrides.childrenIds ?? [],
    retries: overrides.retries ?? 0,
    firstSeenAt: overrides.firstSeenAt ?? '2026-03-14T10:00:00+00:00',
    lastSeenAt: overrides.lastSeenAt ?? '2026-03-14T10:00:00+00:00',
    sentAt: overrides.sentAt ?? '2026-03-14T10:00:00+00:00',
    receivedAt: overrides.receivedAt ?? null,
    startedAt: overrides.startedAt ?? '2026-03-14T10:00:01+00:00',
    finishedAt: overrides.finishedAt ?? '2026-03-14T10:00:02+00:00',
    workerHostname: overrides.workerHostname ?? 'worker-a',
    resultPreview: overrides.resultPreview ?? null,
    exceptionPreview: overrides.exceptionPreview ?? null,
    canvasKind: overrides.canvasKind ?? null,
    canvasId: overrides.canvasId ?? null,
    canvasRole: overrides.canvasRole ?? null,
    scheduleId: overrides.scheduleId ?? null,
    scheduleName: overrides.scheduleName ?? null,
    schedulePattern: overrides.schedulePattern ?? null,
    scheduledFor: overrides.scheduledFor ?? null,
  };
}

function asDetail(task: TaskSummary): TaskDetail {
  return {
    ...task,
    argsPreview: null,
    kwargsPreview: null,
  };
}

function buildNode(overrides: Partial<TaskGraphNode> & { id: string }): TaskGraphNode {
  return {
    id: overrides.id,
    name: overrides.name ?? overrides.id,
    kind: overrides.kind ?? 'job',
    state: overrides.state ?? 'succeeded',
    rootId: overrides.rootId ?? overrides.id,
    parentId: overrides.parentId ?? null,
    queue: overrides.queue ?? 'default',
    workerHostname: overrides.workerHostname ?? 'worker-a',
  };
}

function buildEdge(source: string, target: string, relation = 'child'): TaskGraphEdge {
  return { source, target, relation };
}

function layoutFrom(
  root: TaskDetail,
  graph: TaskGraph,
  tasks: TaskSummary[],
) {
  return buildTaskDagLayout(root, graph, new Map(tasks.map((task) => [task.id, task])));
}

describe('buildTaskDagLayout', () => {
  it('keeps sequential chain steps in separate phases', () => {
    const root = asDetail(buildTask({ id: 'a', name: 'step-a', canvasKind: 'chain', canvasRole: 'head' }));
    const second = buildTask({ id: 'b', name: 'step-b', rootId: 'canvas:chain-1', parentId: 'a', canvasKind: 'chain', canvasId: 'chain-1', canvasRole: 'tail' });
    const graph: TaskGraph = {
      taskId: 'a',
      rootId: 'canvas:chain-1',
      nodes: [
        buildNode({ id: 'canvas:chain-1', kind: 'canvas', state: 'started', rootId: 'canvas:chain-1' }),
        buildNode({ id: 'a', name: 'step-a', rootId: 'canvas:chain-1', queue: 'default' }),
        buildNode({ id: 'b', name: 'step-b', rootId: 'canvas:chain-1', parentId: 'a', queue: 'default' }),
      ],
      edges: [buildEdge('canvas:chain-1', 'a', 'head'), buildEdge('a', 'b', 'chain')],
    };

    const layout = layoutFrom(root, graph, [root, second]);

    expect(layout.phases).toHaveLength(2);
    expect(layout.phases[0]?.nodes.map((node) => node.id)).toEqual(['a']);
    expect(layout.phases[1]?.nodes.map((node) => node.id)).toEqual(['b']);
  });

  it('groups parallel members into the same phase', () => {
    const root = asDetail(buildTask({ id: 'member-1', rootId: 'canvas:grp-1', canvasKind: 'group', canvasId: 'grp-1', canvasRole: 'member' }));
    const member2 = buildTask({ id: 'member-2', rootId: 'canvas:grp-1', canvasKind: 'group', canvasId: 'grp-1', canvasRole: 'member' });
    const member3 = buildTask({ id: 'member-3', rootId: 'canvas:grp-1', canvasKind: 'group', canvasId: 'grp-1', canvasRole: 'member' });
    const graph: TaskGraph = {
      taskId: 'member-1',
      rootId: 'canvas:grp-1',
      nodes: [
        buildNode({ id: 'canvas:grp-1', kind: 'canvas', state: 'started', rootId: 'canvas:grp-1' }),
        buildNode({ id: 'member-1', rootId: 'canvas:grp-1' }),
        buildNode({ id: 'member-2', rootId: 'canvas:grp-1' }),
        buildNode({ id: 'member-3', rootId: 'canvas:grp-1' }),
      ],
      edges: [
        buildEdge('canvas:grp-1', 'member-1', 'member'),
        buildEdge('canvas:grp-1', 'member-2', 'member'),
        buildEdge('canvas:grp-1', 'member-3', 'member'),
      ],
    };

    const layout = layoutFrom(root, graph, [root, member2, member3]);

    expect(layout.phases).toHaveLength(1);
    expect(layout.phases[0]?.nodes.map((node) => node.id)).toEqual(['member-1', 'member-2', 'member-3']);
  });

  it('builds multiple chord phases for a complex join structure', () => {
    const root = asDetail(buildTask({
      id: 'header-1',
      rootId: 'canvas:chord-1',
      canvasKind: 'chord',
      canvasId: 'chord-1',
      canvasRole: 'header',
      state: 'started',
    }));
    const header2 = buildTask({
      id: 'header-2',
      rootId: 'canvas:chord-1',
      canvasKind: 'chord',
      canvasId: 'chord-1',
      canvasRole: 'header',
      state: 'succeeded',
    });
    const joinA = buildTask({
      id: 'join-a',
      rootId: 'canvas:chord-1',
      canvasKind: 'chord',
      canvasId: 'chord-1',
      canvasRole: 'body',
      state: 'sent',
    });
    const joinB = buildTask({
      id: 'join-b',
      rootId: 'canvas:chord-1',
      canvasKind: 'chord',
      canvasId: 'chord-1',
      canvasRole: 'body',
      state: 'sent',
    });
    const finalize = buildTask({
      id: 'finalize',
      rootId: 'canvas:chord-1',
      canvasKind: 'chord',
      canvasId: 'chord-1',
      canvasRole: 'body',
      state: 'sent',
    });
    const graph: TaskGraph = {
      taskId: 'header-1',
      rootId: 'canvas:chord-1',
      nodes: [
        buildNode({ id: 'canvas:chord-1', kind: 'canvas', state: 'started', rootId: 'canvas:chord-1' }),
        buildNode({ id: 'header-1', rootId: 'canvas:chord-1', state: 'started' }),
        buildNode({ id: 'header-2', rootId: 'canvas:chord-1', state: 'succeeded' }),
        buildNode({ id: 'join-a', rootId: 'canvas:chord-1', state: 'sent' }),
        buildNode({ id: 'join-b', rootId: 'canvas:chord-1', state: 'sent' }),
        buildNode({ id: 'finalize', rootId: 'canvas:chord-1', state: 'sent' }),
      ],
      edges: [
        buildEdge('canvas:chord-1', 'header-1', 'header'),
        buildEdge('canvas:chord-1', 'header-2', 'header'),
        buildEdge('header-1', 'join-a', 'body'),
        buildEdge('header-2', 'join-a', 'body'),
        buildEdge('header-2', 'join-b', 'body'),
        buildEdge('join-a', 'finalize', 'body'),
        buildEdge('join-b', 'finalize', 'body'),
      ],
    };

    const layout = layoutFrom(root, graph, [root, header2, joinA, joinB, finalize]);

    expect(layout.phases).toHaveLength(3);
    expect(layout.phases[0]?.nodes.map((node) => node.id)).toEqual(['header-1', 'header-2']);
    expect(layout.phases[1]?.nodes.map((node) => node.id)).toEqual(['join-a', 'join-b']);
    expect(layout.phases[2]?.nodes.map((node) => node.id)).toEqual(['finalize']);
    expect(layout.phases[1]?.label).toBe('Stage 2');
  });

  it('falls back to a general DAG for non-canvas branched graphs', () => {
    const root = asDetail(buildTask({ id: 'root-1', name: 'root-1', rootId: 'root-1', state: 'started' }));
    const branchA = buildTask({ id: 'branch-a', rootId: 'root-1', parentId: 'root-1', state: 'started' });
    const branchB = buildTask({ id: 'branch-b', rootId: 'root-1', parentId: 'root-1', state: 'started' });
    const merge = buildTask({ id: 'merge', rootId: 'root-1', parentId: 'branch-a', state: 'sent' });
    const graph: TaskGraph = {
      taskId: 'root-1',
      rootId: 'root-1',
      nodes: [
        buildNode({ id: 'root-1', rootId: 'root-1', state: 'started' }),
        buildNode({ id: 'branch-a', rootId: 'root-1', parentId: 'root-1', state: 'started' }),
        buildNode({ id: 'branch-b', rootId: 'root-1', parentId: 'root-1', state: 'started' }),
        buildNode({ id: 'merge', rootId: 'root-1', parentId: 'branch-a', state: 'sent' }),
      ],
      edges: [
        buildEdge('root-1', 'branch-a'),
        buildEdge('root-1', 'branch-b'),
        buildEdge('branch-a', 'merge'),
        buildEdge('branch-b', 'merge'),
      ],
    };

    const layout = layoutFrom(root, graph, [root, branchA, branchB, merge]);

    expect(layout.phases).toHaveLength(3);
    expect(layout.phases[0]?.nodes.map((node) => node.id)).toEqual(['root-1']);
    expect(layout.phases[1]?.nodes.map((node) => node.id)).toEqual(['branch-a', 'branch-b']);
    expect(layout.phases[2]?.nodes.map((node) => node.id)).toEqual(['merge']);
  });

  it('marks simple parent-child trees as non-DAG detail candidates', () => {
    const root = asDetail(buildTask({ id: 'root-1', name: 'root-1', rootId: 'root-1', state: 'started' }));
    const child = buildTask({ id: 'child-1', rootId: 'root-1', parentId: 'root-1', state: 'sent' });
    const graph: TaskGraph = {
      taskId: 'root-1',
      rootId: 'root-1',
      nodes: [
        buildNode({ id: 'root-1', rootId: 'root-1', state: 'started' }),
        buildNode({ id: 'child-1', rootId: 'root-1', parentId: 'root-1', state: 'sent' }),
      ],
      edges: [buildEdge('root-1', 'child-1')],
    };

    const layout = layoutFrom(root, graph, [root, child]);

    expect(layout.stats.isCanvasRooted).toBe(false);
    expect(layout.stats.hasParallelism).toBe(false);
    expect(layout.stats.hasJoin).toBe(false);
    expect(layout.stats.maxPhaseSize).toBe(1);
  });
});

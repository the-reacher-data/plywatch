import { describe, expect, it } from 'vitest';

import type { TaskDetail, TaskGraph, TaskSummary } from '$lib/core/contracts/monitor';
import { buildFamilyTree } from '$lib/features/tasks/domain/family-tree';

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
    workerHostname: overrides.workerHostname ?? null,
    resultPreview: overrides.resultPreview ?? null,
    exceptionPreview: overrides.exceptionPreview ?? null,
    canvasKind: overrides.canvasKind ?? null,
    canvasId: overrides.canvasId ?? null,
    canvasRole: overrides.canvasRole ?? null,
    scheduleId: overrides.scheduleId ?? null,
    scheduleName: overrides.scheduleName ?? null,
    schedulePattern: overrides.schedulePattern ?? null,
    scheduledFor: overrides.scheduledFor ?? null
  };
}

function asDetail(task: TaskSummary): TaskDetail {
  return {
    ...task,
    argsPreview: null,
    kwargsPreview: null
  };
}

describe('buildFamilyTree', () => {
  it('uses graph edges to attach callbacks without parentId', () => {
    const root = asDetail(buildTask({ id: 'root-1', rootId: 'root-1', name: 'Root' }));
    const callback = buildTask({
      id: 'callback-1',
      kind: 'callback',
      rootId: 'root-1',
      parentId: null,
      name: 'Notify'
    });
    const graph: TaskGraph = {
      taskId: 'root-1',
      rootId: 'root-1',
      nodes: [
        { id: 'root-1', name: 'Root', kind: 'job', state: 'succeeded', rootId: 'root-1', parentId: null, queue: 'default', workerHostname: null },
        { id: 'callback-1', name: 'Notify', kind: 'callback', state: 'succeeded', rootId: 'root-1', parentId: null, queue: 'default', workerHostname: null }
      ],
      edges: [{ source: 'root-1', target: 'callback-1', relation: 'callback' }]
    };

    const tree = buildFamilyTree(root, graph, new Map([[callback.id, callback]]));

    expect(tree.id).toBe('root-1');
    expect(tree.children).toHaveLength(1);
    expect(tree.children[0]?.id).toBe('callback-1');
  });

  it('falls back to the selected task when the declared root is missing from graph nodes', () => {
    const selected = asDetail(buildTask({ id: 'task-1', rootId: 'missing-root', name: 'Selected task' }));
    const child = buildTask({
      id: 'child-1',
      rootId: 'missing-root',
      parentId: 'task-1',
      name: 'Child task'
    });
    const graph: TaskGraph = {
      taskId: 'task-1',
      rootId: 'missing-root',
      nodes: [
        { id: 'task-1', name: 'Selected task', kind: 'job', state: 'succeeded', rootId: 'missing-root', parentId: null, queue: 'default', workerHostname: null },
        { id: 'child-1', name: 'Child task', kind: 'job', state: 'succeeded', rootId: 'missing-root', parentId: 'task-1', queue: 'default', workerHostname: null }
      ],
      edges: [{ source: 'task-1', target: 'child-1', relation: 'child' }]
    };

    const tree = buildFamilyTree(selected, graph, new Map([[child.id, child]]));

    expect(tree.id).toBe('task-1');
    expect(tree.name).toBe('Selected task');
    expect(tree.children[0]?.id).toBe('child-1');
  });

  it('ignores duplicate parent and edge links for the same child', () => {
    const root = asDetail(buildTask({ id: 'root-1', rootId: 'root-1' }));
    const child = buildTask({
      id: 'child-1',
      rootId: 'root-1',
      parentId: 'root-1'
    });
    const graph: TaskGraph = {
      taskId: 'root-1',
      rootId: 'root-1',
      nodes: [
        { id: 'root-1', name: 'root-1', kind: 'job', state: 'succeeded', rootId: 'root-1', parentId: null, queue: 'default', workerHostname: null },
        { id: 'child-1', name: 'child-1', kind: 'job', state: 'succeeded', rootId: 'root-1', parentId: 'root-1', queue: 'default', workerHostname: null }
      ],
      edges: [{ source: 'root-1', target: 'child-1', relation: 'child' }]
    };

    const tree = buildFamilyTree(root, graph, new Map([[child.id, child]]));

    expect(tree.children).toHaveLength(1);
    expect(tree.children[0]?.id).toBe('child-1');
  });
});

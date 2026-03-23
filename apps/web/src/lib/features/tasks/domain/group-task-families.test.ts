import { describe, expect, it } from 'vitest';

import type { TaskSummary } from '$lib/core/contracts/monitor';
import { buildTaskFamilies } from '$lib/features/tasks/domain/group-task-families';
import { filterTaskHistoryItems } from '$lib/features/tasks/domain/task-history-visibility';

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
    sentAt: overrides.sentAt ?? null,
    receivedAt: overrides.receivedAt ?? null,
    startedAt: overrides.startedAt ?? null,
    finishedAt: overrides.finishedAt ?? null,
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

describe('buildTaskFamilies', () => {
  it('groups callbacks and subtasks under the root task', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'succeeded',
      lastSeenAt: '2026-03-14T10:00:03+00:00',
      childrenIds: ['child-1']
    });
    const child = buildTask({
      id: 'child-1',
      kind: 'callback',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'succeeded',
      lastSeenAt: '2026-03-14T10:00:02+00:00'
    });

    const families = buildTaskFamilies([child, parent]);

    expect(families).toHaveLength(1);
    expect(families[0]?.root.id).toBe('root-1');
    expect(families[0]?.children.map((item) => item.id)).toEqual(['child-1']);
  });

  it('keeps top-level unknown tasks visible as standalone families', () => {
    const first = buildTask({
      id: 'native-1',
      kind: 'unknown',
      name: 'lab.native.echo',
    });
    const second = buildTask({
      id: 'native-2',
      kind: 'unknown',
      name: 'lab.native.echo',
    });

    const families = buildTaskFamilies([first, second]);

    expect(families).toHaveLength(2);
    expect(families.map((family) => family.root.id)).toEqual(['native-1', 'native-2']);
  });

  it('keeps the family on the root outcome when only a callback descendant fails', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'succeeded',
      childrenIds: ['child-1']
    });
    const child = buildTask({
      id: 'child-1',
      kind: 'callback_error',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'failed'
    });

    const families = buildTaskFamilies([parent, child]);

    expect(families[0]?.aggregateState).toBe('succeeded');
  });

  it('marks the family as failed when the root job fails', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'failed',
      childrenIds: ['child-1']
    });
    const child = buildTask({
      id: 'child-1',
      kind: 'callback',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'succeeded'
    });

    const families = buildTaskFamilies([parent, child]);

    expect(families[0]?.aggregateState).toBe('failed');
  });

  it('treats a lost root as a failed family for section placement', () => {
    const parent = buildTask({
      id: 'root-lost',
      state: 'lost',
    });

    const families = buildTaskFamilies([parent]);

    expect(families[0]?.aggregateState).toBe('failed');
    expect(families[0]?.completedCount).toBe(1);
  });

  it('marks the root family as running while any descendant is still active', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'succeeded',
      childrenIds: ['child-1']
    });
    const child = buildTask({
      id: 'child-1',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'started'
    });

    const families = buildTaskFamilies([parent, child]);

    expect(families[0]?.aggregateState).toBe('started');
  });

  it('shows queued descendants as their own visible families while the parent stays grouped', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'started',
      childrenIds: ['child-queued', 'child-done'],
      firstSeenAt: '2026-03-14T10:00:00+00:00',
      lastSeenAt: '2026-03-14T10:00:05+00:00'
    });
    const queuedChild = buildTask({
      id: 'child-queued',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'sent',
      firstSeenAt: '2026-03-14T10:00:01+00:00',
      lastSeenAt: '2026-03-14T10:00:04+00:00'
    });
    const doneChild = buildTask({
      id: 'child-done',
      kind: 'callback',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'succeeded',
      firstSeenAt: '2026-03-14T10:00:02+00:00',
      lastSeenAt: '2026-03-14T10:00:03+00:00'
    });

    const families = buildTaskFamilies([parent, queuedChild, doneChild]);

    expect(families).toHaveLength(2);
    expect(families[0]?.root.id).toBe('root-1');
    expect(families[0]?.children.map((item) => item.id)).toEqual(['child-done']);
    expect(families[0]?.aggregateState).toBe('started');
    expect(families[1]?.root.id).toBe('child-queued');
    expect(families[1]?.children).toEqual([]);
    expect(families[1]?.aggregateState).toBe('sent');
  });

  it('keeps queued roots grouped instead of detaching them', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'sent',
      childrenIds: ['child-queued'],
      firstSeenAt: '2026-03-14T10:00:00+00:00',
      lastSeenAt: '2026-03-14T10:00:02+00:00'
    });
    const queuedChild = buildTask({
      id: 'child-queued',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'received',
      firstSeenAt: '2026-03-14T10:00:01+00:00',
      lastSeenAt: '2026-03-14T10:00:01+00:00'
    });

    const families = buildTaskFamilies([parent, queuedChild]);

    expect(families).toHaveLength(1);
    expect(families[0]?.root.id).toBe('root-1');
    expect(families[0]?.children.map((item) => item.id)).toEqual(['child-queued']);
    expect(families[0]?.aggregateState).toBe('sent');
  });

  it('tracks subtree completion counts for progress rendering', () => {
    const parent = buildTask({
      id: 'root-1',
      state: 'started',
      childrenIds: ['child-1', 'child-2']
    });
    const child1 = buildTask({
      id: 'child-1',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'succeeded'
    });
    const child2 = buildTask({
      id: 'child-2',
      rootId: 'root-1',
      parentId: 'root-1',
      state: 'started'
    });

    const families = buildTaskFamilies([parent, child1, child2]);

    expect(families[0]?.completedCount).toBe(1);
    expect(families[0]?.totalCount).toBe(3);
  });

  it('keeps a self-parent retry task as the visible family root and sorts descendants oldest first', () => {
    const retryRoot = buildTask({
      id: 'retry-root',
      rootId: 'retry-root',
      parentId: 'retry-root',
      state: 'retrying',
      retries: 2,
      firstSeenAt: '2026-03-14T10:00:00+00:00',
      lastSeenAt: '2026-03-14T10:00:03+00:00'
    });
    const callback = buildTask({
      id: 'callback-1',
      kind: 'callback_error',
      rootId: 'retry-root',
      parentId: 'retry-root',
      state: 'failed',
      firstSeenAt: '2026-03-14T10:00:01+00:00',
      lastSeenAt: '2026-03-14T10:00:04+00:00'
    });
    const callback2 = buildTask({
      id: 'callback-2',
      kind: 'callback',
      rootId: 'retry-root',
      parentId: 'retry-root',
      state: 'succeeded',
      firstSeenAt: '2026-03-14T10:00:02+00:00',
      lastSeenAt: '2026-03-14T10:00:05+00:00'
    });

    const families = buildTaskFamilies([callback2, retryRoot, callback]);

    expect(families[0]?.root.id).toBe('retry-root');
    expect(families[0]?.children.map((item) => item.id)).toEqual(['callback-1', 'callback-2']);
  });

  it('hides isolated callback-only families from the main list', () => {
    const callbackError = buildTask({
      id: 'cb-failure',
      kind: 'callback_error',
      state: 'succeeded',
      rootId: 'root-missing',
      parentId: 'root-missing'
    });

    const families = buildTaskFamilies([callbackError]);

    expect(families).toHaveLength(0);
  });

  it('groups canvas members under one structural family with progress', () => {
    const head = buildTask({
      id: 'canvas-head',
      name: 'lab.task.head',
      rootId: 'canvas:grp-1',
      state: 'succeeded',
      canvasKind: 'group',
      canvasId: 'grp-1',
      canvasRole: 'member'
    });
    const second = buildTask({
      id: 'canvas-second',
      name: 'lab.task.second',
      rootId: 'canvas:grp-1',
      state: 'started',
      canvasKind: 'group',
      canvasId: 'grp-1',
      canvasRole: 'member'
    });

    const families = buildTaskFamilies([head, second]);

    expect(families).toHaveLength(1);
    expect(families[0]?.displayName).toBe('lab.task.head');
    expect(families[0]?.progressValue).toBe(1);
    expect(families[0]?.progressTotal).toBe(2);
  });

  it('filters future scheduled sent tasks out of the main task history', () => {
    const scheduledFuture = buildTask({
      id: 'scheduled-future',
      state: 'sent',
      scheduleId: 'schedule:test',
      scheduledFor: '2026-03-19T12:30:00Z',
    });
    const regularQueued = buildTask({
      id: 'regular-queued',
      state: 'sent',
      firstSeenAt: '2026-03-19T12:01:00Z',
      lastSeenAt: '2026-03-19T12:01:00Z',
    });

    const visibleItems = filterTaskHistoryItems(
      [scheduledFuture, regularQueued],
      new Date('2026-03-19T12:00:00Z').getTime(),
    );
    const families = buildTaskFamilies(visibleItems);

    expect(families).toHaveLength(1);
    expect(families[0]?.root.id).toBe('regular-queued');
  });
});

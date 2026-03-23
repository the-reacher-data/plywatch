import { describe, expect, it } from 'vitest';
import { get } from 'svelte/store';

import type {
  CursorPage,
  QueueSummary,
  StreamEvent,
  TaskDetail,
  TaskGraph,
  TaskSectionCounts,
  TaskSummary,
  TaskTimeline,
  WorkerSummary
} from '$lib/core/contracts/monitor';
import type { MonitorClient, TaskHistorySection } from '$lib/core/ports/monitor-client';
import { createTaskStore } from '$lib/features/tasks/domain/task-store';

function buildTask(id: string, state: TaskSummary['state'], lastSeenAt: string): TaskSummary {
  return {
    id,
    name: `task.${id}`,
    kind: 'job',
    state,
    queue: 'default',
    routingKey: 'default',
    rootId: id,
    parentId: null,
    childrenIds: [],
    retries: 0,
    firstSeenAt: lastSeenAt,
    lastSeenAt,
    sentAt: null,
    receivedAt: null,
    startedAt: null,
    finishedAt: null,
    workerHostname: null,
    resultPreview: null,
    exceptionPreview: null,
    canvasKind: null,
    canvasId: null,
    canvasRole: null,
    scheduleId: null,
    scheduleName: null,
    schedulePattern: null,
    scheduledFor: null,
  };
}

function buildSectionCounts(): TaskSectionCounts {
  return {
    queuedFamilies: 1,
    runningFamilies: 1,
    succeededFamilies: 1,
    failedFamilies: 1,
    familyCount: 4,
    executionCount: 4,
    completedExecutions: 2,
    totalExecutions: 4,
  };
}

function emptyPage(): CursorPage<TaskSummary> {
  return { items: [], nextCursor: null, hasNext: false };
}

function buildClient(
  overrides: Partial<MonitorClient> = {},
): MonitorClient {
  return {
    async getOverview() {
      throw new Error('not used');
    },
    async listTasks(): Promise<CursorPage<TaskSummary>> {
      return emptyPage();
    },
    async getTaskSectionCounts(): Promise<TaskSectionCounts> {
      return buildSectionCounts();
    },
    async resetMonitor() {
      return { removedTasks: 0, removedWorkers: 0, removedQueues: 0, removedRawEvents: 0 };
    },
    async removeTaskRows() {
      return { removedCount: 0, removedIds: [] };
    },
    async removeSchedules() {
      return { removedCount: 0, removedIds: [] };
    },
    async getTask(taskId: string): Promise<TaskDetail> {
      const task = buildTask(taskId, 'succeeded', '2026-03-13T08:00:00+00:00');
      return { ...task, argsPreview: null, kwargsPreview: null };
    },
    async getTaskTimeline(): Promise<TaskTimeline> {
      return { taskId: 'task-1', items: [], count: 0 };
    },
    async getTaskGraph(): Promise<TaskGraph> {
      return { taskId: 'task-1', rootId: 'task-1', nodes: [], edges: [] };
    },
    async listWorkers(): Promise<WorkerSummary[]> {
      return [];
    },
    async listQueues(): Promise<QueueSummary[]> {
      return [];
    },
    async listSchedules() {
      return [];
    },
    async listRawEvents() {
      return { items: [], count: 0, limit: 120 };
    },
    createStream(_onEvent: (event: StreamEvent) => void) {
      return { close() {} };
    },
    ...overrides,
  };
}

describe('createTaskStore', () => {
  it('refreshes each tasks section with its own query and merges the visible items', async () => {
    const calls: Array<{ section?: TaskHistorySection; queue?: string }> = [];
    const sectionItems: Record<TaskHistorySection, CursorPage<TaskSummary>> = {
      queued: { items: [buildTask('queued-1', 'sent', '2026-03-13T08:00:04+00:00')], nextCursor: null, hasNext: false },
      running: { items: [buildTask('running-1', 'started', '2026-03-13T08:00:03+00:00')], nextCursor: null, hasNext: false },
      succeeded: { items: [buildTask('succeeded-1', 'succeeded', '2026-03-13T08:00:02+00:00')], nextCursor: null, hasNext: false },
      failed: { items: [buildTask('failed-1', 'failed', '2026-03-13T08:00:01+00:00')], nextCursor: null, hasNext: false },
    };

    const client = buildClient({
      async listTasks(_limit, _cursor, query): Promise<CursorPage<TaskSummary>> {
        calls.push({ section: query?.section, queue: query?.queue });
        return sectionItems[query?.section ?? 'queued'];
      },
    });

    const store = createTaskStore(client);
    await store.setQuery({ queue: 'default' });

    expect(calls).toEqual([
      { section: 'queued', queue: 'default' },
      { section: 'running', queue: 'default' },
      { section: 'succeeded', queue: 'default' },
      { section: 'failed', queue: 'default' },
    ]);

    const snapshot = get(store);
    expect(snapshot.sections.queued.items[0]?.id).toBe('queued-1');
    expect(snapshot.sections.failed.items[0]?.id).toBe('failed-1');
    expect(snapshot.items.map((item) => item.id)).toEqual([
      'queued-1',
      'running-1',
      'succeeded-1',
      'failed-1',
    ]);
  });

  it('loads more for one section without disturbing the other sections', async () => {
    const runningFirst = buildTask('running-1', 'started', '2026-03-13T08:00:04+00:00');
    const runningSecond = buildTask('running-2', 'started', '2026-03-13T08:00:03+00:00');

    const client = buildClient({
      async listTasks(_limit, cursor, query): Promise<CursorPage<TaskSummary>> {
        if (query?.section === 'running') {
          if (cursor === undefined) {
            return { items: [runningFirst], nextCursor: 'next-running', hasNext: true };
          }
          return { items: [runningSecond], nextCursor: null, hasNext: false };
        }
        return emptyPage();
      },
    });

    const store = createTaskStore(client);
    await store.refresh();
    await store.loadMore('running');

    const snapshot = get(store);
    expect(snapshot.sections.running.items.map((item) => item.id)).toEqual(['running-1', 'running-2']);
    expect(snapshot.sections.queued.items).toEqual([]);
    expect(snapshot.sections.running.hasNext).toBe(false);
  });

  it('keeps task detail selection independent from section pagination', async () => {
    const client = buildClient({
      async listTasks(): Promise<CursorPage<TaskSummary>> {
        return emptyPage();
      },
      async getTask(): Promise<TaskDetail> {
        const task = buildTask('task-1', 'succeeded', '2026-03-13T08:00:00+00:00');
        return { ...task, argsPreview: null, kwargsPreview: '{"foo":"bar"}' };
      },
    });

    const store = createTaskStore(client);
    await store.select('task-1');

    expect(get(store).selectedTaskId).toBe('task-1');
    store.clearSelection();
    expect(get(store).selectedTaskId).toBeNull();
  });
});

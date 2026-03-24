import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

import type {
  CursorPage,
  Overview,
  QueueSummary,
  RawEvent,
  TaskDetail,
  TaskSectionCounts,
  TaskGraph,
  TaskSummary,
  TaskTimeline,
  WorkerSummary
} from '$lib/core/contracts/monitor';
import type { MonitorClient, MonitorStream } from '$lib/core/ports/monitor-client';
import { createWorkersStore } from '$lib/features/workers/workers-store';

function buildWorker(hostname: string): WorkerSummary {
  return {
    hostname,
    state: 'online',
    firstSeenAt: '2026-03-14T16:00:00Z',
    lastSeenAt: '2026-03-14T16:10:00Z',
    lastHeartbeatAt: '2026-03-14T16:10:00Z',
    onlineAt: '2026-03-14T16:00:00Z',
    offlineAt: null,
    pid: 123,
    clock: 1,
    freq: 2,
    active: 1,
    processed: 5,
    loadavg: [],
    swIdent: 'celery',
    swVer: '5.6',
    swSys: 'linux'
  };
}

function buildTask(id: string, workerHostname: string): TaskSummary {
  return {
    id,
    name: `task.${id}`,
    kind: 'job',
    state: 'started',
    queue: 'default',
    routingKey: 'default',
    rootId: id,
    parentId: null,
    childrenIds: [],
    retries: 0,
    firstSeenAt: '2026-03-14T16:00:00Z',
    lastSeenAt: '2026-03-14T16:10:00Z',
    sentAt: null,
    receivedAt: null,
    startedAt: null,
    finishedAt: null,
    workerHostname,
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

function buildEvent(hostname: string): RawEvent {
  return {
    capturedAt: '2026-03-14T16:10:00Z',
    eventType: 'worker-heartbeat',
    payload: {},
    uuid: null,
    hostname
  };
}

function makeClient(overrides: Partial<MonitorClient> = {}): MonitorClient {
  return {
    async getOverview(): Promise<Overview> {
      throw new Error('not used');
    },
    async listTasks(): Promise<CursorPage<TaskSummary>> {
      return { items: [buildTask('task-1', 'worker-a')], nextCursor: null, hasNext: false };
    },
    async getTaskSectionCounts(): Promise<TaskSectionCounts> {
      return {
        queuedFamilies: 0,
        runningFamilies: 1,
        succeededFamilies: 0,
        failedFamilies: 0,
        familyCount: 1,
        executionCount: 1,
        completedExecutions: 0,
        totalExecutions: 1,
      };
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
    async getTask(): Promise<TaskDetail> {
      throw new Error('not used');
    },
    async getTaskTimeline(): Promise<TaskTimeline> {
      throw new Error('not used');
    },
    async getTaskGraph(): Promise<TaskGraph> {
      throw new Error('not used');
    },
    async listWorkers(): Promise<WorkerSummary[]> {
      return [buildWorker('worker-a')];
    },
    async listQueues(): Promise<QueueSummary[]> {
      return [];
    },
    async listSchedules() {
      return [];
    },
    async listRawEvents() {
      return { items: [buildEvent('worker-a')], count: 1, limit: 200 };
    },
    createStream(): MonitorStream {
      return { close() {} };
    },
    ...overrides
  };
}

describe('createWorkersStore', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads workers, tasks and events together', async () => {
    const store = createWorkersStore(makeClient());

    await store.refresh();

    const snapshot = get(store);
    expect(snapshot.items).toHaveLength(1);
    expect(snapshot.tasks).toHaveLength(1);
    expect(snapshot.events).toHaveLength(1);
    expect(snapshot.error).toBeNull();
  });

  it('captures loading errors', async () => {
    const store = createWorkersStore(
      makeClient({
        async listWorkers(): Promise<WorkerSummary[]> {
          throw new Error('boom');
        }
      })
    );

    await store.refresh();

    const snapshot = get(store);
    expect(snapshot.loading).toBe(false);
    expect(snapshot.error).toBe('boom');
  });

  it('retries quickly after a startup failure while no workers are loaded', async () => {
    let calls = 0;
    const store = createWorkersStore(
      makeClient({
        async listWorkers(): Promise<WorkerSummary[]> {
          calls += 1;
          if (calls === 1) {
            throw new Error('backend starting');
          }
          return [buildWorker('worker-a')];
        }
      })
    );

    await store.refresh();
    expect(get(store).items).toHaveLength(0);
    expect(get(store).error).toBe('backend starting');

    await vi.advanceTimersByTimeAsync(2_000);

    expect(get(store).items).toHaveLength(1);
    expect(get(store).error).toBeNull();
  });
});

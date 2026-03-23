import { describe, expect, it } from 'vitest';
import { get } from 'svelte/store';

import type {
  CursorPage,
  Overview,
  QueueSummary,
  RawEvent,
  ScheduleSummary,
  TaskDetail,
  TaskGraph,
  TaskSectionCounts,
  TaskSummary,
  TaskTimeline,
  WorkerSummary,
} from '$lib/core/contracts/monitor';
import type { MonitorClient, MonitorStream } from '$lib/core/ports/monitor-client';
import { createOverviewStore } from '$lib/features/overview/overview-store';

function makeClient(overrides: Partial<MonitorClient> = {}): MonitorClient {
  return {
    async getOverview(): Promise<Overview> {
      return {
        product: 'plywatch',
        configPath: 'config/base.yaml',
        brokerUrl: 'redis://redis:6379/0',
        rawEventLimit: 500,
        rawEventCount: 2,
        bufferedEventCount: 2,
        totalEventCount: 20,
        heartbeatEventCount: 4,
        taskCount: 3,
        workerCount: 1,
        queueCount: 1,
        maxTasks: 2000,
        maxAgeSeconds: 21600,
        mode: 'monitor-backend',
      };
    },
    async listWorkers(): Promise<WorkerSummary[]> {
      return [{
        hostname: 'worker-a',
        state: 'online',
        firstSeenAt: '2026-03-21T09:00:00Z',
        lastSeenAt: '2026-03-21T09:01:00Z',
        lastHeartbeatAt: '2026-03-21T09:01:00Z',
        onlineAt: '2026-03-21T09:00:00Z',
        offlineAt: null,
        pid: 1,
        clock: 1,
        freq: 2,
        active: 1,
        processed: 10,
        loadavg: [],
        swIdent: 'celery',
        swVer: '5.6',
        swSys: 'linux',
      }];
    },
    async listRawEvents(): Promise<{ items: RawEvent[]; count: number; limit: number; }> {
      return {
        items: [{
          capturedAt: '2026-03-21T09:01:00Z',
          eventType: 'worker-heartbeat',
          payload: {},
          uuid: null,
          hostname: 'worker-a',
        }],
        count: 1,
        limit: 200,
      };
    },
    async listTasks(): Promise<CursorPage<TaskSummary>> {
      return { items: [], nextCursor: null, hasNext: false };
    },
    async getTaskSectionCounts(): Promise<TaskSectionCounts> {
      return {
        queuedFamilies: 0,
        runningFamilies: 0,
        succeededFamilies: 0,
        failedFamilies: 0,
        familyCount: 0,
        executionCount: 0,
        completedExecutions: 0,
        totalExecutions: 0,
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
    async listQueues(): Promise<QueueSummary[]> {
      return [];
    },
    async listSchedules(): Promise<ScheduleSummary[]> {
      return [];
    },
    createStream(): MonitorStream {
      return { close() {} };
    },
    ...overrides,
  };
}

describe('createOverviewStore', () => {
  it('captures startup errors without throwing away the store', async () => {
    const store = createOverviewStore(makeClient({
      async getOverview(): Promise<Overview> {
        throw new Error('backend starting');
      },
    }));

    await expect(store.start()).resolves.toBeUndefined();

    const snapshot = get(store);
    expect(snapshot.snapshot).toBeNull();
    expect(snapshot.loading).toBe(false);
    expect(snapshot.error).toBe('backend starting');
    store.stop();
  });

  it('keeps the last good snapshot when a later refresh fails', async () => {
    let calls = 0;
    const store = createOverviewStore(makeClient({
      async getOverview(): Promise<Overview> {
        calls += 1;
        if (calls === 2) {
          throw new Error('temporary 500');
        }
        return {
          product: 'plywatch',
          configPath: 'config/base.yaml',
          brokerUrl: 'redis://redis:6379/0',
          rawEventLimit: 500,
          rawEventCount: 2,
          bufferedEventCount: 2,
          totalEventCount: 20,
          heartbeatEventCount: 4,
          taskCount: 3,
          workerCount: 1,
          queueCount: 1,
          maxTasks: 2000,
          maxAgeSeconds: 21600,
          mode: 'monitor-backend',
        };
      },
    }));

    await store.refresh();
    await store.refresh();

    const snapshot = get(store);
    expect(snapshot.snapshot?.taskCount).toBe(3);
    expect(snapshot.error).toBe('temporary 500');
  });
});

import { describe, expect, it } from 'vitest';

import type { RawEvent, TaskSummary, WorkerSummary } from '$lib/core/contracts/monitor';
import {
  buildWorkerKpis,
  buildWorkerRecentActivity,
  buildWorkerSlices,
  buildWorkerSlicesFromCounts,
  buildWorkerTimeline,
  eventsForWorker,
  tasksForWorker
} from '$lib/features/workers/workers-domain';

function buildWorker(): WorkerSummary {
  return {
    hostname: 'worker-a',
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

function buildTask(id: string, state: TaskSummary['state']): TaskSummary {
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
    firstSeenAt: '2026-03-14T16:00:00Z',
    lastSeenAt: '2026-03-14T16:10:00Z',
    sentAt: null,
    receivedAt: null,
    startedAt: null,
    finishedAt: null,
    workerHostname: 'worker-a',
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

function buildEvent(eventType: string): RawEvent {
  return {
    capturedAt: '2026-03-14T16:10:00Z',
    eventType,
    payload: {},
    uuid: null,
    hostname: 'worker-a'
  };
}

describe('workers-domain', () => {
  it('filters tasks and events for the selected worker', () => {
    expect(tasksForWorker([buildTask('a', 'started')], 'worker-a')).toHaveLength(1);
    expect(eventsForWorker([buildEvent('worker-heartbeat')], 'worker-a')).toHaveLength(1);
  });

  it('builds worker task slices', () => {
    const slices = buildWorkerSlices([
      buildTask('a', 'started'),
      buildTask('b', 'succeeded'),
      buildTask('c', 'failed'),
      buildTask('d', 'lost')
    ]);

    expect(slices.find((slice) => slice.key === 'running')?.count).toBe(1);
    expect(slices.find((slice) => slice.key === 'succeeded')?.count).toBe(1);
    expect(slices.find((slice) => slice.key === 'failed')?.count).toBe(2);
  });

  it('builds worker task slices from filtered section counts', () => {
    const slices = buildWorkerSlicesFromCounts({
      queuedFamilies: 0,
      runningFamilies: 8,
      succeededFamilies: 468,
      failedFamilies: 302,
      familyCount: 778,
      executionCount: 1591,
      completedExecutions: 1530,
      totalExecutions: 1540,
    });

    expect(slices.find((slice) => slice.key === 'running')?.count).toBe(8);
    expect(slices.find((slice) => slice.key === 'succeeded')?.count).toBe(468);
    expect(slices.find((slice) => slice.key === 'failed')?.count).toBe(302);
  });

  it('excludes future scheduled runs from running slices', () => {
    const slices = buildWorkerSlices([
      {
        ...buildTask('scheduled-future', 'received'),
        scheduleId: 'schedule:test',
        scheduledFor: '2999-03-19T12:30:00Z'
      },
      buildTask('started-real', 'started')
    ]);

    expect(slices.find((slice) => slice.key === 'running')?.count).toBe(1);
  });

  it('builds worker KPIs and timeline', () => {
    const worker = buildWorker();
    const events = [buildEvent('worker-heartbeat'), buildEvent('task-received'), buildEvent('task-started')];
    const kpis = buildWorkerKpis(worker);

    expect(kpis).toHaveLength(3);
    expect(kpis.map((kpi) => kpi.key)).toEqual(['active', 'heartbeats', 'processed']);
    expect(kpis.find((kpi) => kpi.key === 'processed')).toMatchObject({
      label: 'Worker lifetime processed',
      hint: 'raw Celery worker counter',
      tone: 'neutral'
    });
    expect(buildWorkerTimeline(events).some((bucket) => bucket.total > 0)).toBe(true);
    expect(buildWorkerRecentActivity([buildTask('a', 'started')])).toHaveLength(1);
  });
});

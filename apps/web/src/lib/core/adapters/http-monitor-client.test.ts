import { describe, expect, it, vi } from 'vitest';

import { HttpMonitorClient } from '$lib/core/adapters/http-monitor-client';

describe('HttpMonitorClient', () => {
  it('reads cursor task pages from the backend contract', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [
            {
              uuid: 'task-1',
              name: 'loom.job.Hello',
              kind: 'job',
              state: 'succeeded',
              queue: 'default',
              routingKey: 'default',
              rootId: 'task-1',
              parentId: null,
              childrenIds: [],
              retries: 0,
              firstSeenAt: '2026-03-13T08:00:00+00:00',
              lastSeenAt: '2026-03-13T08:00:01+00:00',
              sentAt: null,
              receivedAt: null,
              startedAt: null,
              finishedAt: null,
              workerHostname: null,
              resultPreview: null,
              exceptionPreview: null
            }
          ],
          nextCursor: 'cursor-1',
          hasNext: true
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    const page = await client.listTasks(20);

    expect(fetcher).toHaveBeenCalledWith('http://monitor/api/tasks/?limit=20');
    expect(page.nextCursor).toBe('cursor-1');
    expect(page.items[0]?.id).toBe('task-1');
  });

  it('sends queue, worker and section filters through task list query params', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [],
          nextCursor: null,
          hasNext: false
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    await client.listTasks(20, 'cursor-1', {
      queue: 'slow',
      workerHostname: 'celery@worker-1',
      section: 'failed'
    });

    expect(fetcher).toHaveBeenCalledWith(
      'http://monitor/api/tasks/?limit=20&cursor=cursor-1&queue=slow&workerHostname=celery%40worker-1&section=failed'
    );
  });

  it('forwards abort signal to the underlying fetch call', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({ items: [], nextCursor: null, hasNext: false }),
        { status: 200 }
      )
    );

    const controller = new AbortController();
    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    await client.listTasks(20, undefined, { queue: 'default' }, controller.signal);

    expect(fetcher).toHaveBeenCalledWith(
      'http://monitor/api/tasks/?limit=20&queue=default',
      { signal: controller.signal }
    );
  });

  it('reads task section counts from the backend contract', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          queuedFamilies: 2,
          runningFamilies: 3,
          succeededFamilies: 5,
          failedFamilies: 1,
          familyCount: 11,
          executionCount: 18,
          completedExecutions: 7,
          totalExecutions: 18
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    const counts = await client.getTaskSectionCounts({ queue: 'slow', workerHostname: 'celery@worker-1' });

    expect(fetcher).toHaveBeenCalledWith(
      'http://monitor/api/task-sections?queue=slow&workerHostname=celery%40worker-1'
    );
    expect(counts.failedFamilies).toBe(1);
    expect(counts.familyCount).toBe(11);
  });

  it('sends monitor admin actions to the backend contract', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            removedTasks: 4,
            removedWorkers: 2,
            removedQueues: 1,
            removedRawEvents: 25
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ removedCount: 2, removedIds: ['task-1', 'task-2'] }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ removedCount: 1, removedIds: ['schedule:nightly'] }),
          { status: 200 }
        )
      );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    await client.resetMonitor();
    await client.removeTaskRows(['task-1', 'task-2']);
    await client.removeSchedules(['schedule:nightly']);

    expect(fetcher).toHaveBeenNthCalledWith(1, 'http://monitor/api/monitor/reset', { method: 'POST' });
    expect(fetcher).toHaveBeenNthCalledWith(2, 'http://monitor/api/monitor/tasks', {
      method: 'DELETE',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids: ['task-1', 'task-2'] }),
    });
    expect(fetcher).toHaveBeenNthCalledWith(3, 'http://monitor/api/monitor/schedules', {
      method: 'DELETE',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids: ['schedule:nightly'] }),
    });
  });

  it('reads observed schedules and maps nested runs to frontend task ids', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [
            {
              scheduleId: 'schedule:nightly-report',
              scheduleName: 'Nightly report',
              schedulePattern: '*/15 * * * *',
              queue: 'default',
              totalRuns: 2,
              pendingRuns: 1,
              queuedRuns: 0,
              runningRuns: 0,
              succeededRuns: 1,
              failedRuns: 0,
              lastScheduledFor: '2026-03-18T21:30:00+00:00',
              lastRunAt: '2026-03-18T21:15:00+00:00',
              pendingRunItems: [
                {
                  uuid: 'task-pending-1',
                  name: 'lab.native.echo',
                  kind: 'job',
                  state: 'sent',
                  queue: 'default',
                  routingKey: 'default',
                  rootId: 'task-pending-1',
                  parentId: null,
                  childrenIds: [],
                  retries: 0,
                  firstSeenAt: '2026-03-18T21:10:00+00:00',
                  lastSeenAt: '2026-03-18T21:10:00+00:00',
                  sentAt: '2026-03-18T21:10:00+00:00',
                  receivedAt: null,
                  startedAt: null,
                  finishedAt: null,
                  workerHostname: null,
                  resultPreview: null,
                  exceptionPreview: null,
                  canvasKind: null,
                  canvasId: null,
                  canvasRole: null,
                  scheduleId: 'schedule:nightly-report',
                  scheduleName: 'Nightly report',
                  schedulePattern: '*/15 * * * *',
                  scheduledFor: '2026-03-18T21:30:00+00:00'
                }
              ],
              recentRuns: [
                {
                  uuid: 'task-1',
                  name: 'lab.native.echo',
                  kind: 'job',
                  state: 'sent',
                  queue: 'default',
                  routingKey: 'default',
                  rootId: 'task-1',
                  parentId: null,
                  childrenIds: [],
                  retries: 0,
                  firstSeenAt: '2026-03-18T21:10:00+00:00',
                  lastSeenAt: '2026-03-18T21:10:00+00:00',
                  sentAt: '2026-03-18T21:10:00+00:00',
                  receivedAt: null,
                  startedAt: null,
                  finishedAt: null,
                  workerHostname: null,
                  resultPreview: null,
                  exceptionPreview: null,
                  canvasKind: null,
                  canvasId: null,
                  canvasRole: null,
                  scheduleId: 'schedule:nightly-report',
                  scheduleName: 'Nightly report',
                  schedulePattern: '*/15 * * * *',
                  scheduledFor: '2026-03-18T21:30:00+00:00'
                }
              ]
            }
          ],
          count: 1,
          limit: 25
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    const schedules = await client.listSchedules(25, { queue: 'default' });

    expect(fetcher).toHaveBeenCalledWith('http://monitor/api/schedules?limit=25&queue=default');
    expect(schedules[0]?.scheduleId).toBe('schedule:nightly-report');
    expect(schedules[0]?.pendingRunItems[0]?.id).toBe('task-pending-1');
    expect(schedules[0]?.recentRuns[0]?.id).toBe('task-1');
  });

  it('reads raw events from the backend contract', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          items: [
            {
              capturedAt: '2026-03-13T08:00:01+00:00',
              eventType: 'task-sent',
              payload: { queue: 'default' },
              uuid: 'task-1',
              hostname: 'celery@worker-1'
            }
          ],
          count: 1,
          limit: 50
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    const page = await client.listRawEvents(50);

    expect(fetcher).toHaveBeenCalledWith('http://monitor/api/events/raw?limit=50');
    expect(page.count).toBe(1);
    expect(page.items[0]?.eventType).toBe('task-sent');
  });

  it('maps task graph node uuids to frontend ids', async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          taskId: 'task-1',
          rootId: 'task-1',
          nodes: [
            {
              uuid: 'task-1',
              name: 'loom.job.Hello',
              kind: 'job',
              state: 'succeeded',
              rootId: 'task-1',
              parentId: null,
              queue: 'default',
              workerHostname: 'celery@worker-1'
            }
          ],
          edges: []
        }),
        { status: 200 }
      )
    );

    const client = new HttpMonitorClient('http://monitor', fetcher as typeof fetch);
    const graph = await client.getTaskGraph('task-1');

    expect(fetcher).toHaveBeenCalledWith('http://monitor/api/tasks/task-1/graph');
    expect(graph.nodes[0]?.id).toBe('task-1');
  });
});

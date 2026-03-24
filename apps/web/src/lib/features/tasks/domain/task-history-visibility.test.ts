import { describe, expect, it } from 'vitest';

import type { TaskSummary } from '$lib/core/contracts/monitor';
import { filterTaskHistoryItems, isFutureScheduledTask } from './task-history-visibility';

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
    firstSeenAt: overrides.firstSeenAt ?? '2026-03-19T12:00:00Z',
    lastSeenAt: overrides.lastSeenAt ?? '2026-03-19T12:00:00Z',
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
    scheduledFor: overrides.scheduledFor ?? null,
  };
}

describe('task-history-visibility', () => {
  it('marks future scheduled sent tasks as non-history items', () => {
    const task = buildTask({
      id: 'scheduled-future',
      state: 'sent',
      scheduleId: 'schedule:test',
      scheduledFor: '2026-03-19T12:30:00Z',
    });

    expect(isFutureScheduledTask(task, new Date('2026-03-19T12:00:00Z').getTime())).toBe(true);
  });

  it('marks future scheduled received tasks as non-history items too', () => {
    const task = buildTask({
      id: 'scheduled-received-future',
      state: 'received',
      scheduleId: 'schedule:test',
      scheduledFor: '2026-03-19T12:30:00Z',
    });

    expect(isFutureScheduledTask(task, new Date('2026-03-19T12:00:00Z').getTime())).toBe(true);
  });

  it('keeps non-scheduled queued tasks in history', () => {
    const task = buildTask({
      id: 'queued-now',
      state: 'sent',
      scheduleId: null,
      scheduledFor: null,
    });

    expect(isFutureScheduledTask(task, new Date('2026-03-19T12:00:00Z').getTime())).toBe(false);
  });

  it('filters future scheduled tasks out of task history items', () => {
    const nowMs = new Date('2026-03-19T12:00:00Z').getTime();
    const items = [
      buildTask({
        id: 'scheduled-future',
        state: 'sent',
        scheduleId: 'schedule:test',
        scheduledFor: '2026-03-19T12:30:00Z',
      }),
      buildTask({
        id: 'scheduled-past',
        state: 'succeeded',
        scheduleId: 'schedule:test',
        scheduledFor: '2026-03-19T11:30:00Z',
      }),
      buildTask({
        id: 'regular-queued',
        state: 'sent',
      }),
    ];

    expect(filterTaskHistoryItems(items, nowMs).map((item) => item.id)).toEqual([
      'scheduled-past',
      'regular-queued',
    ]);
  });
});

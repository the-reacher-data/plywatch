import { describe, expect, it } from 'vitest';

import type { ScheduleSummary, TaskSummary } from '$lib/core/contracts/monitor';
import {
  formatObservedAt,
  isScheduleSectionOpenByDefault,
  isFutureScheduledRun,
  lastActivityLabel,
  scheduleSectionId,
  scheduleRunDisplayName,
  scheduleRunLabel,
  scheduleRunRuntimeLabel,
  scheduleRunTimingLabel,
  scheduleCountLabel,
  scheduleStatusSummary,
  timelineRuns,
} from '$lib/features/tasks/components/scheduled-run-list-view';

function buildTaskSummary(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: 'task-1',
    name: 'lab.native.echo',
    kind: 'unknown',
    state: 'sent',
    queue: 'default',
    routingKey: 'default',
    rootId: 'task-1',
    parentId: null,
    childrenIds: [],
    retries: 0,
    firstSeenAt: '2026-03-19T10:00:00Z',
    lastSeenAt: '2026-03-19T10:00:00Z',
    sentAt: '2026-03-19T10:00:00Z',
    receivedAt: null,
    startedAt: null,
    finishedAt: null,
    workerHostname: null,
    resultPreview: null,
    exceptionPreview: null,
    canvasKind: null,
    canvasId: null,
    canvasRole: null,
    scheduleId: 'schedule:nightly',
    scheduleName: 'Nightly report',
    schedulePattern: '*/15 * * * *',
    scheduledFor: '2026-03-19T10:30:00Z',
    ...overrides,
  };
}

function buildScheduleSummary(overrides: Partial<ScheduleSummary> = {}): ScheduleSummary {
  return {
    scheduleId: 'schedule:nightly',
    scheduleName: 'Nightly report',
    schedulePattern: '*/15 * * * *',
    queue: 'default',
    totalRuns: 2,
    pendingRuns: 1,
    queuedRuns: 0,
    runningRuns: 0,
    succeededRuns: 1,
    failedRuns: 0,
    lastScheduledFor: '2026-03-19T10:30:00Z',
    lastRunAt: '2026-03-19T10:15:00Z',
    pendingRunItems: [
      buildTaskSummary({ id: 'task-pending', state: 'sent', scheduledFor: '2026-03-19T10:30:00Z' }),
    ],
    recentRuns: [
      buildTaskSummary({ id: 'task-1', state: 'succeeded', finishedAt: '2026-03-19T10:15:10Z' }),
      buildTaskSummary({ id: 'task-2', state: 'sent', scheduledFor: '2026-03-19T10:30:00Z' }),
    ],
    ...overrides,
  };
}

describe('scheduled-run-list-view', () => {
  it('formats the schedule summary labels', () => {
    const schedule = buildScheduleSummary();
    const nowMs = new Date('2026-03-19T10:20:00Z').getTime();

    expect(scheduleCountLabel(schedule)).toBe('2 runs observed');
    expect(lastActivityLabel(schedule, nowMs)).toBe('5m ago');
  });

  it('builds a compact ordered status summary for header copy', () => {
    const schedule = buildScheduleSummary({
      pendingRuns: 2,
      queuedRuns: 1,
      runningRuns: 1,
      failedRuns: 3,
      succeededRuns: 4,
    });

    expect(scheduleStatusSummary(schedule)).toEqual([
      { key: 'pending', label: '2 pending', tone: 'neutral' },
      { key: 'queued', label: '1 queued', tone: 'queued' },
      { key: 'running', label: '1 running', tone: 'active' },
      { key: 'failed', label: '3 failed', tone: 'danger' },
      { key: 'succeeded', label: '4 ok', tone: 'success' },
    ]);
  });

  it('shows a neutral last activity label when only future runs exist', () => {
    const schedule = buildScheduleSummary({
      lastRunAt: null,
      recentRuns: [buildTaskSummary({ id: 'task-2', state: 'sent', scheduledFor: '2026-03-19T10:30:00Z' })],
    });

    expect(lastActivityLabel(schedule, new Date('2026-03-19T10:20:00Z').getTime())).toBe(
      'not observed yet'
    );
  });

  it('caps the timeline strip to the most recent 18 runs', () => {
    const schedule = buildScheduleSummary({
      recentRuns: Array.from({ length: 24 }, (_, index) =>
        buildTaskSummary({ id: `task-${index}` })
      ),
    });

    expect(timelineRuns(schedule)).toHaveLength(18);
    expect(timelineRuns(schedule)[0]?.id).toBe('task-0');
    expect(timelineRuns(schedule)[17]?.id).toBe('task-17');
  });

  it('formats absolute observed timestamps for execution rows', () => {
    expect(formatObservedAt('2026-03-19T10:30:00Z')).toContain('2026');
  });

  it('shows a fallback when no observed timestamp exists', () => {
    expect(formatObservedAt(null)).toBe('—');
  });

  it('prefers the schedule name over raw task ids for scheduled rows', () => {
    expect(
      scheduleRunDisplayName(
        buildTaskSummary({
          id: '1b7ece7d-258e-48e4-a948-266e7b97789a',
          name: 'lab.native.echo',
          scheduleName: 'Nightly report',
        })
      )
    ).toBe('Nightly report');
  });

  it('classifies future sent runs as pending instead of running', () => {
    const run = buildTaskSummary({ state: 'sent', scheduledFor: '2026-03-19T10:30:00Z' });
    const nowMs = new Date('2026-03-19T10:20:00Z').getTime();

    expect(isFutureScheduledRun(run, nowMs)).toBe(true);
    expect(scheduleRunLabel(run, nowMs)).toBe('pending');
    expect(scheduleRunTimingLabel(run, nowMs)).toBe('in 10m');
  });

  it('classifies due sent runs as queued', () => {
    const run = buildTaskSummary({ state: 'sent', scheduledFor: '2026-03-19T10:10:00Z' });
    const nowMs = new Date('2026-03-19T10:20:00Z').getTime();

    expect(isFutureScheduledRun(run, nowMs)).toBe(false);
    expect(scheduleRunLabel(run, nowMs)).toBe('queued');
  });

  it('does not show runtime for future scheduled runs', () => {
    const run = buildTaskSummary({ state: 'sent', scheduledFor: '2026-03-19T10:30:00Z' });
    const nowMs = new Date('2026-03-19T10:20:00Z').getTime();

    expect(scheduleRunRuntimeLabel(run, () => '10s', nowMs)).toBe('—');
  });

  it('builds stable section ids and default section state', () => {
    expect(scheduleSectionId('schedule:nightly', 'pending')).toBe('schedule:nightly:pending');
    expect(scheduleSectionId('schedule:nightly', 'observed')).toBe('schedule:nightly:observed');
    expect(isScheduleSectionOpenByDefault('pending')).toBe(true);
    expect(isScheduleSectionOpenByDefault('observed')).toBe(false);
  });
});

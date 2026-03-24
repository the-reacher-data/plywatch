import { describe, expect, it } from 'vitest';

import type { TaskDetail, TaskSummary } from '$lib/core/contracts/monitor';
import {
  formatTaskRuntime,
  outcomePreview,
  kwargsPreview,
  stateLabel,
  subtaskMeta
} from '$lib/features/tasks/components/task-family-list-view';

function buildTaskSummary(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: 'root-task',
    name: 'loom.job.RootJob',
    kind: 'job',
    state: 'started',
    queue: 'default',
    routingKey: 'default',
    rootId: null,
    parentId: null,
    childrenIds: [],
    retries: 0,
    firstSeenAt: '2026-03-14T14:00:00Z',
    lastSeenAt: '2026-03-14T14:00:10Z',
    sentAt: '2026-03-14T14:00:00Z',
    receivedAt: '2026-03-14T14:00:01Z',
    startedAt: '2026-03-14T14:00:02Z',
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
    ...overrides
  };
}

function buildTaskDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    ...buildTaskSummary(),
    argsPreview: null,
    kwargsPreview: '{"hello":"world"}',
    ...overrides
  };
}

describe('task-family-list-view', () => {
  it('formats running runtime against a provided clock', () => {
    const task = buildTaskSummary();
    const nowMs = new Date('2026-03-14T14:00:17Z').getTime();
    expect(formatTaskRuntime(task, nowMs)).toBe('15s');
  });

  it('returns explicit kwargs states for unloaded and loaded details', () => {
    expect(kwargsPreview(null, null, 'root-task')).toBe('Click this execution row to load kwargs.');
    expect(kwargsPreview('root-task', null, 'root-task')).toBe('Loading task detail...');
    expect(kwargsPreview('root-task', buildTaskDetail(), 'root-task')).toBe('{"hello":"world"}');
  });

  it('builds compact subtask meta and normalises started to running', () => {
    const task = buildTaskSummary({
      id: 'child-task',
      kind: 'callback',
      retries: 2,
      startedAt: '2026-03-14T14:00:02Z'
    });
    const nowMs = new Date('2026-03-14T14:00:07Z').getTime();
    expect(stateLabel('started')).toBe('running');
    expect(subtaskMeta(task, nowMs)).toBe('callback · running · 5s · 2 retries');
  });

  it('prefers exception preview, falls back to result, and otherwise shows retry count', () => {
    expect(outcomePreview(buildTaskSummary({ exceptionPreview: 'boom' }))).toBe('boom');
    expect(outcomePreview(buildTaskSummary({ resultPreview: '{"ok":true}' }))).toBe('{"ok":true}');
    expect(outcomePreview(buildTaskSummary({ retries: 3 }))).toBe('3 retries');
  });
});

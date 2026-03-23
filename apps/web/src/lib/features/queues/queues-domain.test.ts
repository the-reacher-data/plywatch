import { describe, expect, it } from 'vitest';

import {
  completedFailureRate,
  completedSuccessRate,
  completedTotal,
  resolveSelectedQueueName,
  shouldRefreshQueuesForEvent,
} from '$lib/features/queues/queues-domain';
import type { QueueSummary } from '$lib/core/contracts/monitor';

describe('resolveSelectedQueueName', () => {
  it('keeps the explicit current selection during refreshes', () => {
    expect(resolveSelectedQueueName(['default', 'slow'], 'slow', null, true)).toBe('slow');
  });

  it('uses the query selection once before any explicit selection', () => {
    expect(resolveSelectedQueueName(['default', 'slow'], null, 'slow', false)).toBe('slow');
  });

  it('applies the query selection when queues arrive after an empty initial state', () => {
    expect(resolveSelectedQueueName([], null, 'slow', false)).toBeNull();
    expect(resolveSelectedQueueName(['default', 'slow'], null, 'slow', false)).toBe('slow');
  });

  it('does not let a stale query override an explicit selection after initialization', () => {
    expect(resolveSelectedQueueName(['default', 'slow'], 'slow', 'default', true)).toBe('slow');
  });

  it('falls back to the first queue when the current selection disappears', () => {
    expect(resolveSelectedQueueName(['default', 'slow'], 'missing', null, true)).toBe('default');
  });
});

describe('shouldRefreshQueuesForEvent', () => {
  it('refreshes queue data for task lifecycle events', () => {
    expect(shouldRefreshQueuesForEvent('task.created', null)).toBe(true);
    expect(shouldRefreshQueuesForEvent('task.updated', null)).toBe(true);
  });

  it('refreshes queue data for queue updates with a queue name', () => {
    expect(shouldRefreshQueuesForEvent('queue.updated', 'slow')).toBe(true);
  });

  it('ignores unrelated events', () => {
    expect(shouldRefreshQueuesForEvent('worker.updated', null)).toBe(false);
    expect(shouldRefreshQueuesForEvent('queue.updated', null)).toBe(false);
  });
});

describe('completed queue metrics', () => {
  const baseQueue: QueueSummary = {
    name: 'default',
    routingKeys: ['default'],
    firstSeenAt: '2026-03-20T09:00:00Z',
    lastSeenAt: '2026-03-20T09:00:00Z',
    totalTasks: 5,
    sentCount: 2,
    activeCount: 1,
    retryingCount: 0,
    succeededCount: 1,
    failedCount: 1,
    historicalTotalSeen: 12,
    historicalSucceededCount: 8,
    historicalFailedCount: 2,
    historicalRetriedCount: 1,
    avgQueueWaitMs: null,
    queueWaitSampleCount: 0,
    avgStartDelayMs: null,
    startDelaySampleCount: 0,
    avgRunDurationMs: null,
    runDurationSampleCount: 0,
    avgEndToEndMs: null,
    endToEndSampleCount: 0,
  };

  it('computes completed totals and rates from terminal runs only', () => {
    expect(completedTotal(baseQueue)).toBe(10);
    expect(completedSuccessRate(baseQueue)).toBe(80);
    expect(completedFailureRate(baseQueue)).toBe(20);
  });

  it('returns zero rates when nothing terminal has completed yet', () => {
    const queue = { ...baseQueue, historicalSucceededCount: 0, historicalFailedCount: 0 };
    expect(completedTotal(queue)).toBe(0);
    expect(completedSuccessRate(queue)).toBe(0);
    expect(completedFailureRate(queue)).toBe(0);
  });
});

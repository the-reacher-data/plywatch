import { describe, expect, it } from 'vitest';

import {
  buildScheduledHref,
  buildTasksHref,
  clearTaskQueueFilter,
  clearTaskWorkerFilter,
} from './task-navigation';

describe('task-navigation', () => {
  it('builds an unfiltered tasks href', () => {
    expect(buildTasksHref('/tasks')).toBe('/tasks');
  });

  it('builds a filtered scheduled href', () => {
    expect(buildScheduledHref('/tasks/scheduled', { queue: 'slow', worker: 'worker-1' })).toBe(
      '/tasks/scheduled?queue=slow&worker=worker-1'
    );
  });

  it('clears the queue filter while preserving worker', () => {
    expect(clearTaskQueueFilter('/tasks', { queue: 'slow', worker: 'worker-1' })).toBe(
      '/tasks?worker=worker-1'
    );
  });

  it('clears the worker filter while preserving queue', () => {
    expect(clearTaskWorkerFilter('/tasks/scheduled', { queue: 'slow', worker: 'worker-1' })).toBe(
      '/tasks/scheduled?queue=slow'
    );
  });
});

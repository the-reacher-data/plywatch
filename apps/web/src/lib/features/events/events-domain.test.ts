import { describe, expect, it } from 'vitest';

import type { RawEvent } from '$lib/core/contracts/monitor';
import {
  buildEventGroups,
  buildWorkerLanes,
  categorizeEvent,
  colorForEvent,
  eventKey,
  labelForEvent
} from '$lib/features/events/events-domain';

function buildEvent(overrides: Partial<RawEvent> = {}): RawEvent {
  return {
    capturedAt: '2026-03-16T10:00:00Z',
    eventType: 'task-received',
    payload: {},
    uuid: null,
    hostname: null,
    ...overrides
  };
}

describe('eventKey', () => {
  it('includes all discriminators in the key', () => {
    const event = buildEvent({ uuid: 'abc', hostname: 'worker-a', eventType: 'task-started' });
    expect(eventKey(event)).toBe('2026-03-16T10:00:00Z|task-started|abc|worker-a');
  });

  it('uses empty string for null uuid and hostname', () => {
    const event = buildEvent({ eventType: 'task-received', uuid: null, hostname: null });
    expect(eventKey(event)).toBe('2026-03-16T10:00:00Z|task-received||');
  });

  it('produces distinct keys for different event types even with null uuid/hostname', () => {
    const a = buildEvent({ eventType: 'task-received' });
    const b = buildEvent({ eventType: 'task-succeeded' });
    expect(eventKey(a)).not.toBe(eventKey(b));
  });
});

describe('buildEventGroups', () => {
  it('counts events by type and sorts by count descending', () => {
    const items = [
      buildEvent({ eventType: 'task-started' }),
      buildEvent({ eventType: 'task-started' }),
      buildEvent({ eventType: 'task-received' })
    ];
    const groups = buildEventGroups(items);
    expect(groups[0].eventType).toBe('task-started');
    expect(groups[0].count).toBe(2);
    expect(groups[0].category).toBe('task');
    expect(groups[1].eventType).toBe('task-received');
    expect(groups[1].count).toBe(1);
  });

  it('returns empty array for empty input', () => {
    expect(buildEventGroups([])).toEqual([]);
  });
});

describe('buildWorkerLanes — hostname normalization', () => {
  it('groups gen8@host and gen10@host into a single lane', () => {
    const items = [
      buildEvent({ hostname: 'gen8@c2b045d4a755', eventType: 'task-received' }),
      buildEvent({ hostname: 'gen10@c2b045d4a755', eventType: 'task-succeeded' })
    ];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes).toHaveLength(1);
    expect(lanes[0].hostname).toBe('c2b045d4a755');
    expect(lanes[0].displayName).toBe('c2b045d4a755');
    expect(lanes[0].events).toHaveLength(2);
  });

  it('normalizes celery@hostname to hostname', () => {
    const items = [buildEvent({ hostname: 'celery@my-worker' })];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes[0].hostname).toBe('my-worker');
  });

  it('keeps hostname as-is when no @ separator present', () => {
    const items = [buildEvent({ hostname: 'plain-worker' })];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes[0].hostname).toBe('plain-worker');
  });

  it('groups unattributed events under No worker', () => {
    const items = [buildEvent({ hostname: null })];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes[0].displayName).toBe('No worker');
  });

  it('ignores task-sent producer hostnames when building worker lanes', () => {
    const items = [
      buildEvent({ hostname: 'gen8@producer-host', eventType: 'task-sent' }),
      buildEvent({ hostname: 'celery@worker-host', eventType: 'task-received' }),
    ];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes).toHaveLength(1);
    expect(lanes[0].hostname).toBe('worker-host');
    expect(lanes[0].events).toHaveLength(1);
    expect(lanes[0].events[0]?.eventType).toBe('task-received');
  });
});

describe('buildWorkerLanes — heartbeat handling', () => {
  it('excludes heartbeats from lane events when not in displayItems', () => {
    const heartbeat = buildEvent({ eventType: 'worker-heartbeat', hostname: 'worker-a' });
    const task = buildEvent({ eventType: 'task-received', hostname: 'worker-a' });
    const lanes = buildWorkerLanes([task], [heartbeat, task]);
    expect(lanes[0].events).toHaveLength(1);
    expect(lanes[0].events[0].eventType).toBe('task-received');
  });

  it('counts heartbeats from allItems', () => {
    const hb1 = buildEvent({ eventType: 'worker-heartbeat', hostname: 'worker-a' });
    const hb2 = buildEvent({
      eventType: 'worker-heartbeat',
      hostname: 'worker-a',
      capturedAt: '2026-03-16T10:00:01Z'
    });
    const task = buildEvent({ eventType: 'task-received', hostname: 'worker-a' });
    const lanes = buildWorkerLanes([task], [hb1, hb2, task]);
    expect(lanes[0].heartbeatCount).toBe(2);
  });

  it('derives online status from heartbeat in allItems even when displayItems is empty', () => {
    const heartbeat = buildEvent({ eventType: 'worker-heartbeat', hostname: 'worker-a' });
    const lanes = buildWorkerLanes([], [heartbeat]);
    expect(lanes[0].status).toBe('online');
  });

  it('aggregates heartbeats from normalized hostnames across prefixes', () => {
    const hbGen8 = buildEvent({ eventType: 'worker-heartbeat', hostname: 'gen8@host-x' });
    const hbGen10 = buildEvent({ eventType: 'worker-heartbeat', hostname: 'gen10@host-x' });
    const lanes = buildWorkerLanes([], [hbGen8, hbGen10]);
    expect(lanes).toHaveLength(1);
    expect(lanes[0].heartbeatCount).toBe(2);
  });

  it('sets heartbeatCount to 0 when no heartbeats present', () => {
    const items = [buildEvent({ hostname: 'worker-a', eventType: 'task-received' })];
    const lanes = buildWorkerLanes(items, items);
    expect(lanes[0].heartbeatCount).toBe(0);
  });
});

describe('colorForEvent', () => {
  it('returns danger for task-failed', () => {
    expect(colorForEvent('task-failed')).toBe('var(--event-danger)');
  });

  it('returns success for task-succeeded', () => {
    expect(colorForEvent('task-succeeded')).toBe('var(--event-success)');
  });

  it('returns signal for worker-heartbeat (exact match)', () => {
    expect(colorForEvent('worker-heartbeat')).toBe('var(--event-signal)');
  });

  it('returns neutral for unknown event type', () => {
    expect(colorForEvent('custom-event')).toBe('var(--event-neutral)');
  });
});

describe('labelForEvent', () => {
  it('replaces hyphens with spaces', () => {
    expect(labelForEvent('task-received')).toBe('task received');
  });
});

describe('categorizeEvent', () => {
  it('categorizes task events as task', () => {
    expect(categorizeEvent('task-started')).toBe('task');
  });

  it('categorizes heartbeat as control', () => {
    expect(categorizeEvent('worker-heartbeat')).toBe('control');
  });

  it('categorizes worker lifecycle events as worker', () => {
    expect(categorizeEvent('worker-online')).toBe('worker');
  });
});

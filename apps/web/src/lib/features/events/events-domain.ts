import type { RawEvent } from '$lib/core/contracts/monitor';

export type WorkerStatus = 'online' | 'offline' | 'unknown';
export type EventCategory = 'task' | 'worker' | 'control' | 'other';

export interface EventGroup {
  eventType: string;
  count: number;
  color: string;
  category: EventCategory;
}

export interface WorkerLane {
  hostname: string;
  displayName: string;
  status: WorkerStatus;
  events: RawEvent[];
  groups: EventGroup[];
  lastEventAt: string;
  heartbeatCount: number;
}

const EVENT_COLORS: Record<string, string> = {
  'worker-heartbeat': 'var(--event-signal)',
};

const EVENT_COLOR_PREFIXES: Array<[string, string]> = [
  ['task-failed', 'var(--event-danger)'],
  ['worker-offline', 'var(--event-danger)'],
  ['task-succeeded', 'var(--event-success)'],
  ['worker-online', 'var(--event-success)'],
  ['task-retried', 'var(--event-warn)'],
  ['task-received', 'var(--event-active)'],
  ['task-started', 'var(--event-active)'],
];

export function colorForEvent(eventType: string): string {
  const exact = EVENT_COLORS[eventType];
  if (exact !== undefined) return exact;

  for (const [prefix, color] of EVENT_COLOR_PREFIXES) {
    if (eventType.startsWith(prefix)) return color;
  }

  return 'var(--event-neutral)';
}

export function labelForEvent(eventType: string): string {
  return eventType.replaceAll('-', ' ');
}

export function eventKey(event: RawEvent): string {
  // Include all available discriminators to minimise key collisions.
  // uuid and hostname are both kept (not OR'd) so events that share one
  // field but differ in the other produce distinct keys.
  return [event.capturedAt, event.eventType, event.uuid ?? '', event.hostname ?? ''].join('|');
}

export function previewPayload(event: RawEvent): string {
  const serialized = JSON.stringify(event.payload);
  return serialized.length > 180 ? `${serialized.slice(0, 177)}...` : serialized;
}

export function isTaskEvent(eventType: string): boolean {
  return eventType.startsWith('task-');
}

export function isWorkerEvent(eventType: string): boolean {
  return eventType.startsWith('worker-');
}

export function categorizeEvent(eventType: string): EventCategory {
  if (isTaskEvent(eventType)) return 'task';
  if (eventType === 'worker-heartbeat') return 'control';
  if (isWorkerEvent(eventType)) return 'worker';
  return 'other';
}

function belongsToWorkerLane(event: RawEvent): boolean {
  if (isWorkerEvent(event.eventType)) return true;

  return (
    event.eventType === 'task-received' ||
    event.eventType === 'task-started' ||
    event.eventType === 'task-retried' ||
    event.eventType === 'task-succeeded' ||
    event.eventType === 'task-failed'
  );
}

export function buildEventGroups(items: RawEvent[]): EventGroup[] {
  const counts: Record<string, number> = {};
  for (const event of items) {
    counts[event.eventType] = (counts[event.eventType] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([eventType, count]) => ({
      eventType,
      count,
      color: colorForEvent(eventType),
      category: categorizeEvent(eventType),
    }))
    .sort((a, b) => b.count - a.count || a.eventType.localeCompare(b.eventType));
}

function deriveWorkerStatus(events: RawEvent[]): WorkerStatus {
  const latest = events
    .filter((e) => isWorkerEvent(e.eventType))
    .sort((a, b) => b.capturedAt.localeCompare(a.capturedAt))[0];

  if (latest === undefined) return 'unknown';
  if (latest.eventType === 'worker-online' || latest.eventType === 'worker-heartbeat') return 'online';
  if (latest.eventType === 'worker-offline') return 'offline';
  return 'unknown';
}

function normalizeHostname(hostname: string): string {
  const atIdx = hostname.lastIndexOf('@');
  return atIdx >= 0 ? hostname.slice(atIdx + 1) : hostname;
}

function displayNameFor(hostname: string): string {
  if (hostname === 'unattributed') return 'No worker';
  return hostname;
}

export function buildWorkerLanes(displayItems: RawEvent[], allItems: RawEvent[]): WorkerLane[] {
  const allByHost = new Map<string, RawEvent[]>();
  for (const event of allItems) {
    if (!belongsToWorkerLane(event)) continue;
    const key = normalizeHostname(event.hostname ?? 'unattributed');
    const bucket = allByHost.get(key) ?? [];
    bucket.push(event);
    allByHost.set(key, bucket);
  }

  const displayByHost = new Map<string, RawEvent[]>();
  for (const event of displayItems) {
    if (!belongsToWorkerLane(event)) continue;
    const key = normalizeHostname(event.hostname ?? 'unattributed');
    const bucket = displayByHost.get(key) ?? [];
    bucket.push(event);
    displayByHost.set(key, bucket);
  }

  return Array.from(allByHost.keys())
    .map((hostname) => {
      const all = (allByHost.get(hostname) ?? []).slice().sort((a, b) => a.capturedAt.localeCompare(b.capturedAt));
      const display = (displayByHost.get(hostname) ?? []).slice().sort((a, b) => a.capturedAt.localeCompare(b.capturedAt));
      const heartbeatCount = all.filter((e) => e.eventType === 'worker-heartbeat').length;
      return {
        hostname,
        displayName: displayNameFor(hostname),
        status: deriveWorkerStatus(all),
        events: display,
        groups: buildEventGroups(display),
        lastEventAt: all.at(-1)?.capturedAt ?? '',
        heartbeatCount,
      };
    })
    .sort((a, b) => b.lastEventAt.localeCompare(a.lastEventAt));
}

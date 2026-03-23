import type { QueueSummary, TaskSummary, TaskState } from '$lib/core/contracts/monitor';

export type StateTone = 'neutral' | 'active' | 'retrying' | 'success' | 'danger';

export interface QueueHealthSegment {
  key: string;
  tone: StateTone;
  percent: number;
  count: number;
  label: string;
}

export interface QueueStateSlice {
  key: 'sent' | 'active' | 'retrying' | 'succeeded' | 'failed';
  label: string;
  section: 'current' | 'retained';
  count: number;
  recentTasks: TaskSummary[];
  tone: StateTone;
}

export interface QueueRecentActivityItem {
  id: string;
  label: string;
  state: TaskState;
  lastSeenAt: string;
  tone: StateTone;
}

export interface QueueTimelineBucket {
  label: string;
  total: number;
  sent: number;
  active: number;
  retrying: number;
  succeeded: number;
  failed: number;
}

const STATE_TONES: Record<TaskState, StateTone> = {
  sent: 'neutral',
  received: 'active',
  started: 'active',
  retrying: 'retrying',
  succeeded: 'success',
  failed: 'danger',
  lost: 'danger',
};

export function isActiveState(state: TaskState): boolean {
  return state === 'received' || state === 'started';
}

export function percentOf(value: number, total: number): number {
  return total === 0 ? 0 : Math.round((value / total) * 100);
}

export function completedTotal(queue: QueueSummary): number {
  return queue.historicalSucceededCount + queue.historicalFailedCount;
}

export function completedSuccessRate(queue: QueueSummary): number {
  return percentOf(queue.historicalSucceededCount, completedTotal(queue));
}

export function completedFailureRate(queue: QueueSummary): number {
  return percentOf(queue.historicalFailedCount, completedTotal(queue));
}

export function toneForState(state: TaskState): StateTone {
  return STATE_TONES[state];
}

export function formatRelativeTime(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function formatDurationMs(value: number | null): string {
  if (value === null) return '-';
  if (value < 1_000) return `${value} ms`;

  const seconds = value / 1_000;
  if (seconds < 60) return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;

  const minutes = Math.floor(seconds / 60);
  const remSeconds = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}m ${remSeconds}s`;

  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return `${hours}h ${remMinutes}m`;
}

export function resolveSelectedQueueName(
  queueNames: string[],
  currentSelection: string | null,
  initialQuerySelection: string | null,
  initialQuerySelectionApplied: boolean,
): string | null {
  if (queueNames.length === 0) {
    return null;
  }

  if (
    !initialQuerySelectionApplied &&
    initialQuerySelection !== null &&
    queueNames.includes(initialQuerySelection)
  ) {
    return initialQuerySelection;
  }

  if (currentSelection !== null && queueNames.includes(currentSelection)) {
    return currentSelection;
  }

  return queueNames[0] ?? null;
}

export function shouldRefreshQueuesForEvent(eventType: string, queueName: string | null): boolean {
  if (eventType === 'queue.updated' && queueName !== null) {
    return true;
  }
  return eventType === 'task.created' || eventType === 'task.updated';
}

export function buildHealthBar(queue: QueueSummary): QueueHealthSegment[] {
  const total = queue.totalTasks;
  if (total === 0) return [];

  const candidates = [
    { key: 'sent', tone: 'neutral' as StateTone, count: queue.sentCount, label: 'queued' },
    { key: 'active', tone: 'active' as StateTone, count: queue.activeCount, label: 'in flight' },
    { key: 'retrying', tone: 'retrying' as StateTone, count: queue.retryingCount, label: 'retrying' },
    { key: 'succeeded', tone: 'success' as StateTone, count: queue.succeededCount, label: 'succeeded' },
    { key: 'failed', tone: 'danger' as StateTone, count: queue.failedCount, label: 'failed' },
  ];

  return candidates
    .filter((s) => s.count > 0)
    .map((s) => ({ ...s, percent: percentOf(s.count, total) }));
}

function topRecentTasks(
  items: TaskSummary[],
  predicate: (t: TaskSummary) => boolean,
  limit = 3,
): TaskSummary[] {
  return items
    .filter(predicate)
    .sort((a, b) => b.lastSeenAt.localeCompare(a.lastSeenAt))
    .slice(0, limit);
}

export function buildQueueSlices(queue: QueueSummary, tasks: TaskSummary[]): QueueStateSlice[] {
  return [
    {
      key: 'sent',
      label: 'Queued',
      section: 'current',
      count: queue.sentCount,
      recentTasks: topRecentTasks(tasks, (t) => t.state === 'sent'),
      tone: 'neutral',
    },
    {
      key: 'active',
      label: 'In flight',
      section: 'current',
      count: queue.activeCount,
      recentTasks: topRecentTasks(tasks, (t) => isActiveState(t.state)),
      tone: 'active',
    },
    {
      key: 'retrying',
      label: 'Retrying',
      section: 'current',
      count: queue.retryingCount,
      recentTasks: topRecentTasks(tasks, (t) => t.state === 'retrying'),
      tone: 'retrying',
    },
    {
      key: 'succeeded',
      label: 'Succeeded',
      section: 'retained',
      count: queue.succeededCount,
      recentTasks: topRecentTasks(tasks, (t) => t.state === 'succeeded'),
      tone: 'success',
    },
    {
      key: 'failed',
      label: 'Failed',
      section: 'retained',
      count: queue.failedCount,
      recentTasks: topRecentTasks(tasks, (t) => t.state === 'failed'),
      tone: 'danger',
    },
  ];
}

export function buildRecentActivity(tasks: TaskSummary[]): QueueRecentActivityItem[] {
  return tasks
    .slice()
    .sort((a, b) => b.lastSeenAt.localeCompare(a.lastSeenAt))
    .slice(0, 12)
    .map((t) => ({
      id: t.id,
      label: t.name ?? t.id,
      state: t.state,
      lastSeenAt: formatRelativeTime(t.lastSeenAt),
      tone: toneForState(t.state),
    }));
}

function formatBucketLabel(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function buildQueueTimeline(items: TaskSummary[], bucketCount = 8): QueueTimelineBucket[] {
  if (items.length === 0) return [];

  const timestamps = items
    .map((t) => new Date(t.lastSeenAt).getTime())
    .filter(Number.isFinite)
    .sort((a, b) => a - b);

  if (timestamps.length === 0) return [];

  const minTime = timestamps[0];
  const maxTime = timestamps.at(-1) ?? minTime;
  const span = Math.max(maxTime - minTime, 1);
  const bucketSize = Math.max(Math.ceil(span / bucketCount), 1);

  const buckets: QueueTimelineBucket[] = Array.from({ length: bucketCount }, (_, i) => ({
    label: formatBucketLabel(new Date(minTime + i * bucketSize)),
    total: 0,
    sent: 0,
    active: 0,
    retrying: 0,
    succeeded: 0,
    failed: 0,
  }));

  for (const task of items) {
    const ts = new Date(task.lastSeenAt).getTime();
    const idx = Math.min(Math.max(Math.floor((ts - minTime) / bucketSize), 0), bucketCount - 1);
    const bucket = buckets[idx];
    if (!bucket) continue;

    bucket.total += 1;
    if (task.state === 'sent') bucket.sent += 1;
    else if (isActiveState(task.state)) bucket.active += 1;
    else if (task.state === 'retrying') bucket.retrying += 1;
    else if (task.state === 'succeeded') bucket.succeeded += 1;
    else if (task.state === 'failed') bucket.failed += 1;
  }

  return buckets;
}

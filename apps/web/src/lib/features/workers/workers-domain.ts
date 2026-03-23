import type {
  RawEvent,
  TaskSectionCounts,
  TaskSummary,
  WorkerState,
  WorkerSummary
} from '$lib/core/contracts/monitor';
import { isFutureScheduledTask } from '$lib/features/tasks/domain/task-history-visibility';

export type WorkerTone = 'online' | 'active' | 'stale' | 'offline' | 'success' | 'danger' | 'neutral';

export interface WorkerKpi {
  key: 'active' | 'processed' | 'heartbeats';
  label: string;
  value: string;
  tone: WorkerTone;
  hint: string;
  helpText?: string;
}

export interface WorkerStateSlice {
  key: 'running' | 'succeeded' | 'failed';
  label: string;
  count: number;
  tone: WorkerTone;
}

export interface WorkerActivityItem {
  id: string;
  label: string;
  state: string;
  lastSeenAt: string;
  tone: WorkerTone;
}

export interface WorkerTimelineBucket {
  label: string;
  total: number;
  heartbeats: number;
  received: number;
  started: number;
  failed: number;
}

function formatClock(iso: string | null): string {
  if (iso === null) return '-';
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return iso;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatRelativeTime(iso: string | null): string {
  if (iso === null) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(diff)) return iso;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function toneForWorkerState(state: WorkerState): WorkerTone {
  if (state === 'online') return 'online';
  if (state === 'stale') return 'stale';
  return 'offline';
}

export function tasksForWorker(tasks: TaskSummary[], hostname: string): TaskSummary[] {
  return tasks
    .filter((task) => task.workerHostname === hostname)
    .sort((left, right) => right.lastSeenAt.localeCompare(left.lastSeenAt));
}

export function eventsForWorker(events: RawEvent[], hostname: string): RawEvent[] {
  return events
    .filter((event) => event.hostname === hostname)
    .sort((left, right) => left.capturedAt.localeCompare(right.capturedAt));
}

export function buildWorkerKpis(worker: WorkerSummary): WorkerKpi[] {
  return [
    {
      key: 'active',
      label: 'Active now',
      value: String(worker.active ?? 0),
      tone: 'active',
      hint: 'tasks currently executing',
      helpText: 'Current executions that this worker is running right now.'
    },
    {
      key: 'heartbeats',
      label: 'Last heartbeat',
      value: formatRelativeTime(worker.lastHeartbeatAt),
      tone: toneForWorkerState(worker.state),
      hint: worker.lastHeartbeatAt ?? 'never',
      helpText: 'Most recent heartbeat observed from this worker.'
    },
    {
      key: 'processed',
      label: 'Worker lifetime processed',
      value: String(worker.processed ?? 0),
      tone: 'neutral',
      hint: 'raw Celery worker counter',
      helpText:
        'Raw Celery counter since this worker process started. Includes callbacks, retries, and executions no longer retained by the monitor.'
    }
  ];
}

export function buildWorkerSlices(tasks: TaskSummary[]): WorkerStateSlice[] {
  const visibleTasks = tasks.filter((task) => !isFutureScheduledTask(task));
  return [
    {
      key: 'running',
      label: 'Running',
      count: visibleTasks.filter((task) => task.state === 'received' || task.state === 'started' || task.state === 'retrying' || task.state === 'sent').length,
      tone: 'active'
    },
    {
      key: 'succeeded',
      label: 'Succeeded',
      count: visibleTasks.filter((task) => task.state === 'succeeded').length,
      tone: 'success'
    },
    {
      key: 'failed',
      label: 'Failed',
      count: visibleTasks.filter((task) => task.state === 'failed' || task.state === 'lost').length,
      tone: 'danger'
    }
  ];
}

export function buildWorkerSlicesFromCounts(counts: TaskSectionCounts | null): WorkerStateSlice[] {
  return [
    {
      key: 'running',
      label: 'Running',
      count: counts?.runningFamilies ?? 0,
      tone: 'active'
    },
    {
      key: 'succeeded',
      label: 'Succeeded',
      count: counts?.succeededFamilies ?? 0,
      tone: 'success'
    },
    {
      key: 'failed',
      label: 'Failed',
      count: counts?.failedFamilies ?? 0,
      tone: 'danger'
    }
  ];
}

export function buildWorkerRecentActivity(tasks: TaskSummary[]): WorkerActivityItem[] {
  return tasks.slice(0, 8).map((task) => ({
    id: task.id,
    label: task.name ?? task.id,
    state: task.state,
    lastSeenAt: formatRelativeTime(task.lastSeenAt),
    tone:
      task.state === 'failed' || task.state === 'lost'
        ? 'danger'
        : task.state === 'succeeded'
          ? 'success'
          : 'active'
  }));
}

function bucketLabel(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function buildWorkerTimeline(events: RawEvent[], bucketCount = 8): WorkerTimelineBucket[] {
  if (events.length === 0) return [];

  const timestamps = events
    .map((event) => new Date(event.capturedAt).getTime())
    .filter(Number.isFinite)
    .sort((left, right) => left - right);

  if (timestamps.length === 0) return [];

  const min = timestamps[0]!;
  const max = timestamps[timestamps.length - 1]!;
  const span = Math.max(max - min, 1);
  const bucketSize = Math.max(Math.ceil(span / bucketCount), 1);

  const buckets: WorkerTimelineBucket[] = Array.from({ length: bucketCount }, (_, index) => ({
    label: bucketLabel(new Date(min + index * bucketSize)),
    total: 0,
    heartbeats: 0,
    received: 0,
    started: 0,
    failed: 0
  }));

  for (const event of events) {
    const ts = new Date(event.capturedAt).getTime();
    const index = Math.min(Math.max(Math.floor((ts - min) / bucketSize), 0), bucketCount - 1);
    const bucket = buckets[index];
    if (!bucket) continue;
    bucket.total += 1;
    if (event.eventType === 'worker-heartbeat') bucket.heartbeats += 1;
    if (event.eventType === 'task-received') bucket.received += 1;
    if (event.eventType === 'task-started') bucket.started += 1;
    if (event.eventType === 'task-failed') bucket.failed += 1;
  }

  return buckets;
}

export function formatWorkerSystem(worker: WorkerSummary): string {
  return [worker.swIdent, worker.swVer].filter(Boolean).join(' · ') || 'celery';
}

export function formatLastHeartbeat(worker: WorkerSummary): string {
  return formatClock(worker.lastHeartbeatAt);
}

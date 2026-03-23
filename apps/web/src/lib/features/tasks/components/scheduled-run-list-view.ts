import type { ScheduleSummary, TaskSummary } from '$lib/core/contracts/monitor';

import { formatRelativeTime } from '$lib/features/tasks/components/task-family-list-view';

export function timelineRuns(schedule: ScheduleSummary): TaskSummary[] {
  return schedule.recentRuns.slice(0, 18);
}

export function scheduleSectionId(scheduleId: string, section: 'pending' | 'observed'): string {
  return `${scheduleId}:${section}`;
}

export function isScheduleSectionOpenByDefault(section: 'pending' | 'observed'): boolean {
  return section === 'pending';
}

export function lastActivityLabel(schedule: ScheduleSummary, nowMs = Date.now()): string {
  if (schedule.lastRunAt === null) {
    return 'not observed yet';
  }
  return formatRelativeTime(schedule.lastRunAt, nowMs);
}

export function formatObservedAt(isoStr: string | null): string {
  if (isoStr === null) {
    return '—';
  }
  const timestamp = new Date(isoStr);
  if (!Number.isFinite(timestamp.getTime())) {
    return '—';
  }
  return timestamp.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function scheduleCountLabel(schedule: ScheduleSummary): string {
  return schedule.totalRuns === 1 ? '1 run observed' : `${schedule.totalRuns} runs observed`;
}

export interface ScheduleStatusStat {
  key: 'pending' | 'queued' | 'running' | 'failed' | 'succeeded';
  label: string;
  tone: 'neutral' | 'queued' | 'active' | 'danger' | 'success';
}

export function scheduleStatusSummary(schedule: ScheduleSummary): ScheduleStatusStat[] {
  const stats: ScheduleStatusStat[] = [];
  if (schedule.pendingRuns > 0) {
    stats.push({ key: 'pending', label: `${schedule.pendingRuns} pending`, tone: 'neutral' });
  }
  if (schedule.queuedRuns > 0) {
    stats.push({ key: 'queued', label: `${schedule.queuedRuns} queued`, tone: 'queued' });
  }
  if (schedule.runningRuns > 0) {
    stats.push({ key: 'running', label: `${schedule.runningRuns} running`, tone: 'active' });
  }
  if (schedule.failedRuns > 0) {
    stats.push({ key: 'failed', label: `${schedule.failedRuns} failed`, tone: 'danger' });
  }
  if (schedule.succeededRuns > 0) {
    stats.push({ key: 'succeeded', label: `${schedule.succeededRuns} ok`, tone: 'success' });
  }
  return stats;
}

export function scheduleRunDisplayName(run: TaskSummary): string {
  if (run.scheduleName !== null && run.scheduleName.trim().length > 0) {
    return run.scheduleName;
  }
  if (run.name !== null && run.name.trim().length > 0) {
    return run.name;
  }
  return run.id;
}

export function isFutureScheduledRun(run: TaskSummary, nowMs = Date.now()): boolean {
  if (
    run.scheduleId === null ||
    run.scheduledFor === null ||
    run.state === 'succeeded' ||
    run.state === 'failed' ||
    run.state === 'lost'
  ) {
    return false;
  }
  const scheduledMs = new Date(run.scheduledFor).getTime();
  return Number.isFinite(scheduledMs) && scheduledMs > nowMs;
}

export function scheduleRunLabel(run: TaskSummary, nowMs = Date.now()): string {
  if (isFutureScheduledRun(run, nowMs)) {
    return 'pending';
  }
  if (run.state === 'sent') {
    return 'queued';
  }
  if (run.state === 'started') {
    return 'running';
  }
  return run.state;
}

export function scheduleRunTone(run: TaskSummary, nowMs = Date.now()): string {
  if (isFutureScheduledRun(run, nowMs)) {
    return 'neutral';
  }
  if (run.state === 'sent') {
    return 'queued';
  }
  if (run.state === 'received' || run.state === 'started' || run.state === 'retrying') {
    return 'active';
  }
  if (run.state === 'succeeded') {
    return 'success';
  }
  if (run.state === 'failed' || run.state === 'lost') {
    return 'danger';
  }
  return 'neutral';
}

export function scheduleRunTimingLabel(run: TaskSummary, nowMs = Date.now()): string {
  if (isFutureScheduledRun(run, nowMs)) {
    return formatTimeUntil(run.scheduledFor, nowMs);
  }
  return formatRelativeTime(run.lastSeenAt ?? run.scheduledFor, nowMs);
}

export function scheduleRunRuntimeLabel(
  run: TaskSummary,
  formatRuntime: (task: TaskSummary, nowMs?: number) => string,
  nowMs = Date.now(),
): string {
  if (isFutureScheduledRun(run, nowMs)) {
    return '—';
  }
  if (run.state === 'sent') {
    return 'waiting';
  }
  return formatRuntime(run, nowMs);
}

function formatTimeUntil(isoStr: string | null, nowMs: number): string {
  if (isoStr === null) {
    return '—';
  }
  const diff = new Date(isoStr).getTime() - nowMs;
  if (!Number.isFinite(diff)) {
    return '—';
  }
  if (diff <= 60_000) {
    return 'due now';
  }
  if (diff < 3_600_000) {
    return `in ${Math.floor(diff / 60_000)}m`;
  }
  if (diff < 86_400_000) {
    return `in ${Math.floor(diff / 3_600_000)}h`;
  }
  return `in ${Math.floor(diff / 86_400_000)}d`;
}

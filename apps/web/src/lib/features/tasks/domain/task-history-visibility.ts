import type { TaskSummary } from '$lib/core/contracts/monitor';

function isFutureIso(isoStr: string | null, nowMs: number): boolean {
  if (isoStr === null) {
    return false;
  }
  const timestamp = new Date(isoStr).getTime();
  return Number.isFinite(timestamp) && timestamp > nowMs;
}

export function isFutureScheduledTask(task: TaskSummary, nowMs = Date.now()): boolean {
  return (
    task.scheduleId !== null &&
    task.state !== 'succeeded' &&
    task.state !== 'failed' &&
    isFutureIso(task.scheduledFor, nowMs)
  );
}

export function filterTaskHistoryItems(items: TaskSummary[], nowMs = Date.now()): TaskSummary[] {
  return items.filter((item) => !isFutureScheduledTask(item, nowMs));
}

import type { TaskDetail, TaskSummary } from '$lib/core/contracts/monitor';

const STATE_TONES: Record<string, string> = {
  sent: 'neutral',
  received: 'neutral',
  started: 'active',
  retrying: 'retrying',
  succeeded: 'success',
  failed: 'danger',
  lost: 'danger'
};

export function toneForState(state: string): string {
  return STATE_TONES[state] ?? 'neutral';
}

export function isRunningState(state: string): boolean {
  return state === 'sent' || state === 'received' || state === 'started' || state === 'retrying';
}

export function formatRelativeTime(isoStr: string | null, nowMs = Date.now()): string {
  if (isoStr === null) return '—';
  const diff = nowMs - new Date(isoStr).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function formatTaskRuntime(task: TaskSummary, nowMs = Date.now()): string {
  const start = task.startedAt ?? task.receivedAt ?? task.sentAt;
  if (start === null) {
    return '-';
  }
  const startMs = new Date(start).getTime();
  if (!Number.isFinite(startMs)) {
    return '-';
  }
  const endMs = task.finishedAt ? new Date(task.finishedAt).getTime() : nowMs;
  const elapsedSeconds = Math.max(Math.floor((endMs - startMs) / 1000), 0);
  if (elapsedSeconds < 60) {
    return `${elapsedSeconds}s`;
  }
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

export function stateLabel(state: string): string {
  return state === 'started' ? 'running' : state;
}

export function kwargsPreview(
  selectedTaskId: string | null,
  selectedTask: TaskDetail | null,
  taskId: string
): string {
  if (selectedTaskId !== taskId) {
    return 'Click this execution row to load kwargs.';
  }
  if (selectedTask === null) {
    return 'Loading task detail...';
  }
  return selectedTask.kwargsPreview ?? '-';
}

export function subtaskMeta(task: TaskSummary, nowMs = Date.now()): string {
  const bits = [stateLabel(task.state), formatTaskRuntime(task, nowMs)];
  if (task.kind !== 'unknown') {
    bits.unshift(task.kind);
  }
  if (task.retries > 0) {
    bits.push(`${task.retries} retries`);
  }
  return bits.join(' · ');
}

export function outcomePreview(task: TaskSummary, maxLength = 56): string {
  const raw = task.exceptionPreview ?? task.resultPreview;
  if (raw === null) {
    return task.retries > 0 ? `${task.retries} retries` : '—';
  }

  return raw.length > maxLength ? `${raw.slice(0, maxLength - 1)}…` : raw;
}

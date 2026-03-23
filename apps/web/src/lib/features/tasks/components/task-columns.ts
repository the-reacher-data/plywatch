import type { TableColumn } from '$lib/components/table/types';
import type { TaskSummary } from '$lib/core/contracts/monitor';

function durationLabel(task: TaskSummary): string {
  const startedAt = task.startedAt ?? task.receivedAt ?? task.sentAt;
  const finishedAt = task.finishedAt;
  if (startedAt === null || finishedAt === null) {
    return '-';
  }

  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return '-';
  }

  const elapsedSeconds = Math.max(Math.floor((end - start) / 1000), 0);
  if (elapsedSeconds < 60) {
    return `${elapsedSeconds}s`;
  }

  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

export const taskColumns: TableColumn<TaskSummary>[] = [
  {
    id: 'name',
    header: 'Task',
    accessor: (row) => row.name ?? row.id
  },
  {
    id: 'duration',
    header: 'Duration',
    accessor: (row) => durationLabel(row)
  },
  {
    id: 'retries',
    header: 'Retries',
    accessor: (row) => String(row.retries)
  },
  {
    id: 'queue',
    header: 'Queue',
    accessor: (row) => row.queue ?? '-'
  },
  {
    id: 'worker',
    header: 'Worker',
    accessor: (row) => row.workerHostname ?? '-'
  },
  {
    id: 'seen',
    header: 'Seen',
    accessor: (row) => row.lastSeenAt
  }
];

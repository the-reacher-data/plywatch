import type {
  CursorPage,
  ListResponse,
  Overview,
  QueueSummary,
  RawEvent,
  ScheduleSummary,
  StreamEvent,
  TaskDetail,
  TaskSectionCounts,
  TaskGraph,
  TaskSummary,
  TaskTimeline,
  WorkerSummary
} from '$lib/core/contracts/monitor';

export type TaskHistorySection = 'queued' | 'running' | 'succeeded' | 'failed';

export interface TaskListQuery {
  queue?: string;
  workerHostname?: string;
  section?: TaskHistorySection;
}

export interface MonitorClient {
  getOverview(): Promise<Overview>;
  listTasks(limit: number, cursor?: string, query?: TaskListQuery, signal?: AbortSignal): Promise<CursorPage<TaskSummary>>;
  getTaskSectionCounts(query?: TaskListQuery): Promise<TaskSectionCounts>;
  resetMonitor(): Promise<{ removedTasks: number; removedWorkers: number; removedQueues: number; removedRawEvents: number }>;
  removeTaskRows(ids: string[]): Promise<{ removedCount: number; removedIds: string[] }>;
  removeSchedules(ids: string[]): Promise<{ removedCount: number; removedIds: string[] }>;
  getTask(taskId: string): Promise<TaskDetail>;
  getTaskTimeline(taskId: string): Promise<TaskTimeline>;
  getTaskGraph(taskId: string): Promise<TaskGraph>;
  listWorkers(limit: number): Promise<WorkerSummary[]>;
  listQueues(limit: number): Promise<QueueSummary[]>;
  listSchedules(limit: number, query?: TaskListQuery): Promise<ScheduleSummary[]>;
  listRawEvents(limit: number): Promise<ListResponse<RawEvent>>;
  createStream(
    onEvent: (event: StreamEvent) => void,
    onStatusChange?: (connected: boolean) => void
  ): MonitorStream;
}

export interface MonitorStream {
  close(): void;
}

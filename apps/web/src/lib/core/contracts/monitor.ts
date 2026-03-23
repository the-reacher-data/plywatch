export type TaskKind = 'job' | 'callback' | 'callback_error' | 'unknown';
export type TaskGraphNodeKind = TaskKind | 'canvas';
export type TaskState = 'sent' | 'received' | 'started' | 'retrying' | 'succeeded' | 'failed' | 'lost';
export type WorkerState = 'online' | 'stale' | 'offline';
export type CanvasKind = 'chain' | 'group' | 'chord';
export type CanvasRole = 'head' | 'tail' | 'member' | 'header' | 'body';

export interface Overview {
  product: string;
  configPath: string;
  brokerUrl: string;
  rawEventLimit: number;
  rawEventCount: number;
  bufferedEventCount: number;
  totalEventCount: number;
  heartbeatEventCount: number;
  taskCount: number;
  workerCount: number;
  queueCount: number;
  maxTasks: number;
  maxAgeSeconds: number;
  mode: string;
}

export interface TaskSummary {
  id: string;
  name: string | null;
  kind: TaskKind;
  state: TaskState;
  queue: string | null;
  routingKey: string | null;
  rootId: string | null;
  parentId: string | null;
  childrenIds: string[];
  retries: number;
  firstSeenAt: string;
  lastSeenAt: string;
  sentAt: string | null;
  receivedAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  workerHostname: string | null;
  resultPreview: string | null;
  exceptionPreview: string | null;
  canvasKind: CanvasKind | null;
  canvasId: string | null;
  canvasRole: CanvasRole | null;
  scheduleId: string | null;
  scheduleName: string | null;
  schedulePattern: string | null;
  scheduledFor: string | null;
}

export interface TaskDetail extends TaskSummary {
  argsPreview: string | null;
  kwargsPreview: string | null;
}

export interface TaskTimelineEvent {
  capturedAt: string;
  eventType: string;
  payload: Record<string, unknown>;
}

export interface TaskTimeline {
  taskId: string;
  items: TaskTimelineEvent[];
  count: number;
}

export interface TaskGraphNode {
  id: string;
  name: string | null;
  kind: TaskGraphNodeKind;
  state: TaskState;
  rootId: string | null;
  parentId: string | null;
  queue: string | null;
  workerHostname: string | null;
}

export interface TaskGraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface TaskGraph {
  taskId: string;
  rootId: string;
  nodes: TaskGraphNode[];
  edges: TaskGraphEdge[];
}

export interface CursorPage<T> {
  items: T[];
  nextCursor: string | null;
  hasNext: boolean;
}

export interface TaskSectionCounts {
  queuedFamilies: number;
  runningFamilies: number;
  succeededFamilies: number;
  failedFamilies: number;
  familyCount: number;
  executionCount: number;
  completedExecutions: number;
  totalExecutions: number;
}

export interface ScheduleSummary {
  scheduleId: string;
  scheduleName: string;
  schedulePattern: string | null;
  queue: string | null;
  totalRuns: number;
  pendingRuns: number;
  queuedRuns: number;
  runningRuns: number;
  succeededRuns: number;
  failedRuns: number;
  lastScheduledFor: string | null;
  lastRunAt: string | null;
  pendingRunItems: TaskSummary[];
  recentRuns: TaskSummary[];
}

export interface WorkerSummary {
  hostname: string;
  state: WorkerState;
  firstSeenAt: string;
  lastSeenAt: string;
  lastHeartbeatAt: string | null;
  onlineAt: string | null;
  offlineAt: string | null;
  pid: number | null;
  clock: number | null;
  freq: number | null;
  active: number | null;
  processed: number | null;
  loadavg: number[];
  swIdent: string | null;
  swVer: string | null;
  swSys: string | null;
}

export interface QueueSummary {
  name: string;
  routingKeys: string[];
  firstSeenAt: string;
  lastSeenAt: string;
  totalTasks: number;
  sentCount: number;
  activeCount: number;
  retryingCount: number;
  succeededCount: number;
  failedCount: number;
  historicalTotalSeen: number;
  historicalSucceededCount: number;
  historicalFailedCount: number;
  historicalRetriedCount: number;
  avgQueueWaitMs: number | null;
  queueWaitSampleCount: number;
  avgStartDelayMs: number | null;
  startDelaySampleCount: number;
  avgRunDurationMs: number | null;
  runDurationSampleCount: number;
  avgEndToEndMs: number | null;
  endToEndSampleCount: number;
}

export interface RawEvent {
  capturedAt: string;
  eventType: string;
  payload: Record<string, unknown>;
  uuid: string | null;
  hostname: string | null;
}

export interface ListResponse<T> {
  items: T[];
  count: number;
  limit: number;
}

export interface StreamEvent {
  type: string;
  eventType: string;
  taskId: string | null;
  workerHostname: string | null;
  queueName: string | null;
  capturedAt: string | null;
  taskName: string | null;
}

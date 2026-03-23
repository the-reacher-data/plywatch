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
import type { MonitorClient, MonitorStream, TaskListQuery } from '$lib/core/ports/monitor-client';
import { readJson } from '$lib/core/utils/http';

type FetchLike = typeof fetch;
type EventSourceFactory = (url: string) => EventSource;

interface BackendCursorPage<T> {
  items: T[];
  nextCursor: string | null;
  hasNext: boolean;
}

interface BackendTaskSummary extends Omit<TaskSummary, 'id'> {
  uuid: string;
}

interface BackendTaskDetail extends Omit<TaskDetail, 'id'> {
  uuid: string;
}

interface BackendTaskGraphNode extends Omit<TaskGraph['nodes'][number], 'id'> {
  uuid: string;
}

interface BackendTaskGraph extends Omit<TaskGraph, 'nodes'> {
  nodes: BackendTaskGraphNode[];
}

interface BackendScheduleSummary extends Omit<ScheduleSummary, 'recentRuns' | 'pendingRunItems'> {
  pendingRunItems: BackendTaskSummary[];
  recentRuns: BackendTaskSummary[];
}

function toTaskSummary(task: BackendTaskSummary): TaskSummary {
  return {
    ...task,
    id: task.uuid
  };
}

function toTaskDetail(task: BackendTaskDetail): TaskDetail {
  return {
    ...task,
    id: task.uuid
  };
}

function toTaskGraph(graph: BackendTaskGraph): TaskGraph {
  return {
    ...graph,
    nodes: graph.nodes.map((node) => ({
      ...node,
      id: node.uuid
    }))
  };
}

export class HttpMonitorClient implements MonitorClient {
  private readonly baseUrl: string;
  private readonly fetcher: FetchLike;
  private readonly eventSourceFactory: EventSourceFactory;

  public constructor(
    baseUrl: string,
    fetcher: FetchLike = fetch,
    eventSourceFactory: EventSourceFactory = (url) => new EventSource(url)
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.fetcher = fetcher;
    this.eventSourceFactory = eventSourceFactory;
  }

  public async getOverview(): Promise<Overview> {
    return readJson<Overview>(await this.fetcher(`${this.baseUrl}/api/overview`));
  }

  public async listTasks(
    limit: number,
    cursor?: string,
    queryFilters?: TaskListQuery,
    signal?: AbortSignal,
  ): Promise<CursorPage<TaskSummary>> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor !== undefined) {
      query.set('cursor', cursor);
    }
    if (queryFilters?.queue !== undefined) {
      query.set('queue', queryFilters.queue);
    }
    if (queryFilters?.workerHostname !== undefined) {
      query.set('workerHostname', queryFilters.workerHostname);
    }
    if (queryFilters?.section !== undefined) {
      query.set('section', queryFilters.section);
    }
    const url = `${this.baseUrl}/api/tasks/?${query.toString()}`;
    const response = await (signal !== undefined
      ? this.fetcher(url, { signal })
      : this.fetcher(url));
    const payload = await readJson<BackendCursorPage<BackendTaskSummary>>(response);
    return {
      ...payload,
      items: payload.items.map(toTaskSummary)
    };
  }

  public async getTaskSectionCounts(queryFilters?: TaskListQuery): Promise<TaskSectionCounts> {
    const query = new URLSearchParams();
    if (queryFilters?.queue !== undefined) {
      query.set('queue', queryFilters.queue);
    }
    if (queryFilters?.workerHostname !== undefined) {
      query.set('workerHostname', queryFilters.workerHostname);
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : '';
    return readJson<TaskSectionCounts>(
      await this.fetcher(`${this.baseUrl}/api/task-sections${suffix}`)
    );
  }

  public async resetMonitor(): Promise<{ removedTasks: number; removedWorkers: number; removedQueues: number; removedRawEvents: number }> {
    return readJson(
      await this.fetcher(`${this.baseUrl}/api/monitor/reset`, { method: 'POST' })
    );
  }

  public async removeTaskRows(ids: string[]): Promise<{ removedCount: number; removedIds: string[] }> {
    return readJson(
      await this.fetcher(`${this.baseUrl}/api/monitor/tasks`, {
        method: 'DELETE',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ids }),
      })
    );
  }

  public async removeSchedules(ids: string[]): Promise<{ removedCount: number; removedIds: string[] }> {
    return readJson(
      await this.fetcher(`${this.baseUrl}/api/monitor/schedules`, {
        method: 'DELETE',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ids }),
      })
    );
  }

  public async getTask(taskId: string): Promise<TaskDetail> {
    const payload = await readJson<BackendTaskDetail>(await this.fetcher(`${this.baseUrl}/api/tasks/${taskId}`));
    return toTaskDetail(payload);
  }

  public async getTaskTimeline(taskId: string): Promise<TaskTimeline> {
    return readJson<TaskTimeline>(await this.fetcher(`${this.baseUrl}/api/tasks/${taskId}/events`));
  }

  public async getTaskGraph(taskId: string): Promise<TaskGraph> {
    const payload = await readJson<BackendTaskGraph>(
      await this.fetcher(`${this.baseUrl}/api/tasks/${taskId}/graph`)
    );
    return toTaskGraph(payload);
  }

  public async listWorkers(limit: number): Promise<WorkerSummary[]> {
    const payload = await readJson<ListResponse<WorkerSummary>>(
      await this.fetcher(`${this.baseUrl}/api/workers/?limit=${limit}`)
    );
    return payload.items;
  }

  public async listQueues(limit: number): Promise<QueueSummary[]> {
    const payload = await readJson<ListResponse<QueueSummary>>(
      await this.fetcher(`${this.baseUrl}/api/queues/?limit=${limit}`)
    );
    return payload.items;
  }

  public async listSchedules(limit: number, queryFilters?: TaskListQuery): Promise<ScheduleSummary[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (queryFilters?.queue !== undefined) {
      query.set('queue', queryFilters.queue);
    }
    if (queryFilters?.workerHostname !== undefined) {
      query.set('workerHostname', queryFilters.workerHostname);
    }
    const payload = await readJson<ListResponse<BackendScheduleSummary>>(
      await this.fetcher(`${this.baseUrl}/api/schedules?${query.toString()}`)
    );
    return payload.items.map((item) => ({
      ...item,
      pendingRunItems: item.pendingRunItems.map(toTaskSummary),
      recentRuns: item.recentRuns.map(toTaskSummary),
    }));
  }

  public async listRawEvents(limit: number): Promise<ListResponse<RawEvent>> {
    return readJson<ListResponse<RawEvent>>(
      await this.fetcher(`${this.baseUrl}/api/events/raw?limit=${limit}`)
    );
  }

  public createStream(
    onEvent: (event: StreamEvent) => void,
    onStatusChange?: (connected: boolean) => void
  ): MonitorStream {
    const source = this.eventSourceFactory(`${this.baseUrl}/api/events/stream`);
    source.onopen = (): void => onStatusChange?.(true);
    source.onerror = (): void => onStatusChange?.(false);
    const handle = (event: MessageEvent<string>): void => {
      try {
        onEvent(JSON.parse(event.data) as StreamEvent);
      } catch {
        // Malformed SSE payload — skip event, keep stream alive.
      }
    };
    source.addEventListener('task.created', handle as EventListener);
    source.addEventListener('task.updated', handle as EventListener);
    source.addEventListener('worker.created', handle as EventListener);
    source.addEventListener('worker.updated', handle as EventListener);
    source.addEventListener('queue.updated', handle as EventListener);
    source.addEventListener('raw.event', handle as EventListener);
    source.addEventListener('stream.ready', handle as EventListener);
    return {
      close(): void {
        source.close();
      }
    };
  }
}

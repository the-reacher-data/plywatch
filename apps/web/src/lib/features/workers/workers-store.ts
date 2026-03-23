import { writable, type Readable } from 'svelte/store';

import type { RawEvent, StreamEvent, TaskSummary, WorkerSummary } from '$lib/core/contracts/monitor';
import type { MonitorClient, MonitorStream } from '$lib/core/ports/monitor-client';

export interface WorkersState {
  items: WorkerSummary[];
  tasks: TaskSummary[];
  events: RawEvent[];
  loading: boolean;
  error: string | null;
}

export interface WorkersStore extends Readable<WorkersState> {
  refresh(): Promise<void>;
  connect(intervalMs?: number): void;
  disconnect(): void;
}

const INITIAL_STATE: WorkersState = {
  items: [],
  tasks: [],
  events: [],
  loading: false,
  error: null
};

export function createWorkersStore(
  client: MonitorClient,
  workerLimit = 25,
  taskLimit = 200,
  eventLimit = 200
): WorkersStore {
  const state = writable<WorkersState>(INITIAL_STATE);
  let timer: ReturnType<typeof setInterval> | null = null;
  let bootstrapRetryTimer: ReturnType<typeof setTimeout> | null = null;
  let stream: MonitorStream | null = null;

  const clearBootstrapRetry = (): void => {
    if (bootstrapRetryTimer !== null) {
      clearTimeout(bootstrapRetryTimer);
      bootstrapRetryTimer = null;
    }
  };

  const scheduleBootstrapRetry = (): void => {
    if (bootstrapRetryTimer !== null) return;
    bootstrapRetryTimer = setTimeout(() => {
      bootstrapRetryTimer = null;
      void refresh();
    }, 2_000);
  };

  const refresh = async (): Promise<void> => {
    state.update((current) => ({ ...current, loading: true, error: null }));
    try {
      const items = await client.listWorkers(workerLimit);
      clearBootstrapRetry();
      state.update((current) => ({ ...current, items }));

      const [tasksResult, eventsResult] = await Promise.allSettled([
        client.listTasks(taskLimit),
        client.listRawEvents(eventLimit)
      ]);

      state.update((current) => ({
        ...current,
        loading: false,
        tasks: tasksResult.status === 'fulfilled' ? tasksResult.value.items : current.tasks,
        events: eventsResult.status === 'fulfilled' ? eventsResult.value.items : current.events
      }));
    } catch (error) {
      state.update((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load workers'
      }));
      if (getCurrentState().items.length === 0) {
        scheduleBootstrapRetry();
      }
    }
  };

  let currentState: WorkersState = INITIAL_STATE;
  state.subscribe((value) => {
    currentState = value;
  });

  const getCurrentState = (): WorkersState => currentState;

  // Lightweight refresh: only the worker list, used on SSE state-change events.
  // Tasks and events snapshots are left as-is; the 15s poll keeps them fresh.
  const refreshWorkerList = async (): Promise<void> => {
    try {
      const items = await client.listWorkers(workerLimit);
      state.update((current) => ({ ...current, items }));
    } catch {
      // Silent — the next scheduled poll will recover.
    }
  };

  const handleStreamEvent = (event: StreamEvent): void => {
    if (event.type === 'worker.online' || event.type === 'worker.offline') {
      void refreshWorkerList();
    }
  };

  const connect = (intervalMs = 15_000): void => {
    if (timer !== null || stream !== null) return;
    timer = setInterval(() => { void refresh(); }, intervalMs);
    stream = client.createStream(handleStreamEvent);
  };

  const disconnect = (): void => {
    clearBootstrapRetry();
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
    stream?.close();
    stream = null;
  };

  return {
    subscribe: state.subscribe,
    refresh,
    connect,
    disconnect
  };
}

import { writable, type Readable } from 'svelte/store';

import type { Overview, RawEvent, WorkerState, WorkerSummary } from '$lib/core/contracts/monitor';
import type { MonitorClient } from '$lib/core/ports/monitor-client';

export interface OverviewSeries {
  eventTotals: number[];
  heartbeatTotals: number[];
  receivedTotals: number[];
  taskTotals: number[];
  workerTotals: number[];
  queueTotals: number[];
}

export interface OverviewWorkerLine {
  hostname: string;
  state: WorkerState;
  active: number | null;
  processed: number | null;
  lastHeartbeatAt: string | null;
  receivedNow: number;
  series: number[];
}

export interface OverviewState {
  snapshot: Overview | null;
  series: OverviewSeries;
  workers: OverviewWorkerLine[];
  loading: boolean;
  error: string | null;
}

export interface OverviewStore extends Readable<OverviewState> {
  refresh(): Promise<void>;
  start(intervalMs?: number): Promise<void>;
  stop(): void;
}

export function createOverviewStore(client: MonitorClient): OverviewStore {
  const maxSamples = 30;
  const state = writable<OverviewState>({
    snapshot: null,
    series: {
      eventTotals: [],
      heartbeatTotals: [],
      receivedTotals: [],
      taskTotals: [],
      workerTotals: [],
      queueTotals: [],
    },
    workers: [],
    loading: false,
    error: null,
  });
  let timer: ReturnType<typeof setInterval> | null = null;
  let seenEventKeys = new Set<string>();

  const appendSample = (series: number[], value: number): number[] => {
    const next = [...series, value];
    return next.slice(-maxSamples);
  };

  const rawEventKey = (event: RawEvent): string =>
    `${event.capturedAt}-${event.eventType}-${event.uuid ?? event.hostname ?? 'na'}`;

  const countReceivedByWorker = (events: RawEvent[]): Map<string, number> => {
    const counts = new Map<string, number>();
    for (const event of events) {
      if (event.eventType !== 'task-received' || event.hostname === null) {
        continue;
      }
      counts.set(event.hostname, (counts.get(event.hostname) ?? 0) + 1);
    }
    return counts;
  };

  const buildWorkerLines = (
    previous: OverviewWorkerLine[],
    workers: WorkerSummary[],
    receivedCounts: Map<string, number>
  ): OverviewWorkerLine[] => {
    const previousMap = new Map(previous.map((worker) => [worker.hostname, worker]));
    return workers.map((worker) => {
      const prior = previousMap.get(worker.hostname);
      const receivedNow = receivedCounts.get(worker.hostname) ?? 0;
      const nextSeries = appendSample(prior?.series ?? [], receivedNow);
      return {
        hostname: worker.hostname,
        state: worker.state,
        active: worker.active,
        processed: worker.processed,
        lastHeartbeatAt: worker.lastHeartbeatAt,
        receivedNow,
        series: nextSeries,
      };
    });
  };

  const refresh = async (): Promise<void> => {
    state.update((current) => ({ ...current, loading: true, error: null }));
    try {
      const [snapshot, workers, rawEvents] = await Promise.all([
        client.getOverview(),
        client.listWorkers(20),
        client.listRawEvents(200),
      ]);
      const currentKeys = new Set(rawEvents.items.map(rawEventKey));
      const unseenEvents =
        seenEventKeys.size === 0
          ? []
          : rawEvents.items.filter((event) => !seenEventKeys.has(rawEventKey(event)));
      seenEventKeys = currentKeys;
      const receivedCounts = countReceivedByWorker(unseenEvents);
      const receivedTotal = Array.from(receivedCounts.values()).reduce((sum, value) => sum + value, 0);
      state.update((current) => ({
        snapshot,
        series: {
          eventTotals: appendSample(current.series.eventTotals, snapshot.totalEventCount),
          heartbeatTotals: appendSample(current.series.heartbeatTotals, snapshot.heartbeatEventCount),
          receivedTotals: appendSample(current.series.receivedTotals, receivedTotal),
          taskTotals: appendSample(current.series.taskTotals, snapshot.taskCount),
          workerTotals: appendSample(current.series.workerTotals, snapshot.workerCount),
          queueTotals: appendSample(current.series.queueTotals, snapshot.queueCount),
        },
        workers: buildWorkerLines(current.workers, workers, receivedCounts),
        loading: false,
        error: null,
      }));
    } catch (error) {
      state.update((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load overview',
      }));
    }
  };

  return {
    subscribe: state.subscribe,
    refresh,
    async start(intervalMs = 2000): Promise<void> {
      if (timer !== null) {
        clearInterval(timer);
      }
      void refresh();
      timer = setInterval(() => {
        void refresh();
      }, intervalMs);
    },
    stop(): void {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    },
  };
}

import { writable, type Readable } from 'svelte/store';

import type { ListResponse, RawEvent } from '$lib/core/contracts/monitor';
import type { MonitorClient, MonitorStream } from '$lib/core/ports/monitor-client';

export interface EventsViewState {
  items: RawEvent[];
  count: number;
  limit: number;
  loading: boolean;
  paused: boolean;
  error: string | null;
}

export interface EventsStore extends Readable<EventsViewState> {
  refresh(): Promise<void>;
  connect(): void;
  disconnect(): void;
  pause(): void;
  resume(): void;
}

const initialState = (limit: number): EventsViewState => ({
  items: [],
  count: 0,
  limit,
  loading: false,
  paused: false,
  error: null
});

export function createEventsStore(client: MonitorClient, limit = 120): EventsStore {
  const state = writable<EventsViewState>(initialState(limit));
  let stream: MonitorStream | null = null;
  let refreshInFlight = false;

  const apply = (payload: ListResponse<RawEvent>): void => {
    state.update((s) => ({
      ...s,
      items: payload.items,
      count: payload.count,
      limit: payload.limit,
      loading: false,
      error: null
    }));
  };

  const refresh = async (): Promise<void> => {
    // Skip silently when paused — resume() will trigger a manual refresh.
    let isPaused = false;
    state.update((s) => { isPaused = s.paused; return s; });
    if (isPaused || refreshInFlight) return;

    refreshInFlight = true;
    state.update((s) => ({ ...s, loading: true, error: null }));
    try {
      apply(await client.listRawEvents(limit));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load events';
      state.update((s) => ({ ...s, loading: false, error: message }));
    } finally {
      refreshInFlight = false;
    }
  };

  return {
    subscribe: state.subscribe,
    refresh,
    connect(): void {
      if (stream !== null) return;
      stream = client.createStream(() => { void refresh(); });
    },
    disconnect(): void {
      stream?.close();
      stream = null;
    },
    pause(): void {
      state.update((s) => ({ ...s, paused: true }));
    },
    resume(): void {
      state.update((s) => ({ ...s, paused: false }));
      void refresh();
    }
  };
}

import { writable, type Readable } from 'svelte/store';

import type { MonitorClient } from '$lib/core/ports/monitor-client';
import type { QueueSummary } from '$lib/core/contracts/monitor';

export interface QueuesState {
  items: QueueSummary[];
  loading: boolean;
  error: string | null;
}

export interface QueuesStore extends Readable<QueuesState> {
  refresh(): Promise<void>;
}

const INITIAL_STATE: QueuesState = { items: [], loading: false, error: null };

export function createQueuesStore(client: MonitorClient, limit = 25): QueuesStore {
  const state = writable<QueuesState>(INITIAL_STATE);

  return {
    subscribe: state.subscribe,
    async refresh(): Promise<void> {
      state.update((s) => ({ ...s, loading: true, error: null }));
      try {
        const items = await client.listQueues(limit);
        state.set({ items, loading: false, error: null });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load queues';
        state.update((s) => ({ ...s, loading: false, error: message }));
      }
    },
  };
}

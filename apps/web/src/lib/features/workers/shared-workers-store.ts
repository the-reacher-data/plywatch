import { monitorClient } from '$lib/core/monitor-client';
import { createWorkersStore } from '$lib/features/workers/workers-store';

export const sharedWorkersStore = createWorkersStore(monitorClient);

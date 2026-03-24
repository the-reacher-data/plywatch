import { monitorClient } from '$lib/core/monitor-client';
import { createQueuesStore } from '$lib/features/queues/queues-store';

export const sharedQueuesStore = createQueuesStore(monitorClient);

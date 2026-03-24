import { monitorClient } from '$lib/core/monitor-client';
import { createTaskStore } from '$lib/features/tasks/domain/task-store';

export const sharedTaskStore = createTaskStore(monitorClient);

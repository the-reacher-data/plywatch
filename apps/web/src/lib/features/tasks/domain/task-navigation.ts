export type TaskRouteFilters = {
  queue?: string | null;
  worker?: string | null;
};

function withQuery(basePath: string, filters: TaskRouteFilters): string {
  const query = new URLSearchParams();

  if (filters.queue !== undefined && filters.queue !== null && filters.queue.length > 0) {
    query.set('queue', filters.queue);
  }

  if (filters.worker !== undefined && filters.worker !== null && filters.worker.length > 0) {
    query.set('worker', filters.worker);
  }

  const queryString = query.toString();
  return queryString.length > 0 ? `${basePath}?${queryString}` : basePath;
}

export function buildTasksHref(basePath: string, filters: TaskRouteFilters = {}): string {
  return withQuery(basePath, filters);
}

export function buildScheduledHref(basePath: string, filters: TaskRouteFilters = {}): string {
  return withQuery(basePath, filters);
}

export function clearTaskQueueFilter(basePath: string, filters: TaskRouteFilters): string {
  return withQuery(basePath, { worker: filters.worker ?? null });
}

export function clearTaskWorkerFilter(basePath: string, filters: TaskRouteFilters): string {
  return withQuery(basePath, { queue: filters.queue ?? null });
}

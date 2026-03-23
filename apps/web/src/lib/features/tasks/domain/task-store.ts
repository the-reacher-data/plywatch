import { writable, type Readable } from 'svelte/store';

import type {
  CursorPage,
  StreamEvent,
  TaskDetail,
  TaskGraph,
  TaskSectionCounts,
  TaskSummary,
  TaskTimeline
} from '$lib/core/contracts/monitor';
import type {
  MonitorClient,
  MonitorStream,
  TaskHistorySection,
  TaskListQuery
} from '$lib/core/ports/monitor-client';

export interface TaskSectionState {
  items: TaskSummary[];
  byId: Map<string, TaskSummary>;
  nextCursor: string | null;
  hasNext: boolean;
  loading: boolean;
  error: string | null;
}

export interface TaskViewState {
  items: TaskSummary[];
  byId: Map<string, TaskSummary>;
  sections: Record<TaskHistorySection, TaskSectionState>;
  selectedTaskId: string | null;
  selectedTask: TaskDetail | null;
  selectedTimeline: TaskTimeline | null;
  selectedGraph: TaskGraph | null;
  sectionCounts: TaskSectionCounts | null;
  loading: boolean;
  selectedTaskLoading: boolean;
  error: string | null;
  selectedTaskError: string | null;
  streamConnected: boolean;
  recentlyAddedIds: Set<string>;
}

const TASK_SECTIONS: readonly TaskHistorySection[] = ['queued', 'running', 'succeeded', 'failed'];

function createSectionState(): TaskSectionState {
  return {
    items: [],
    byId: new Map<string, TaskSummary>(),
    nextCursor: null,
    hasNext: false,
    loading: false,
    error: null,
  };
}

function createSectionsState(): Record<TaskHistorySection, TaskSectionState> {
  return {
    queued: createSectionState(),
    running: createSectionState(),
    succeeded: createSectionState(),
    failed: createSectionState(),
  };
}

const initialState = (): TaskViewState => ({
  items: [],
  byId: new Map<string, TaskSummary>(),
  sections: createSectionsState(),
  selectedTaskId: null,
  selectedTask: null,
  selectedTimeline: null,
  selectedGraph: null,
  sectionCounts: null,
  loading: false,
  selectedTaskLoading: false,
  error: null,
  selectedTaskError: null,
  streamConnected: false,
  recentlyAddedIds: new Set(),
});

function matchesQuery(task: TaskSummary, query: TaskListQuery): boolean {
  if (query.queue !== undefined && task.queue !== query.queue) {
    return false;
  }
  if (query.workerHostname !== undefined && task.workerHostname !== query.workerHostname) {
    return false;
  }
  return true;
}

function mergeCombinedSections(
  sections: Record<TaskHistorySection, TaskSectionState>,
): { items: TaskSummary[]; byId: Map<string, TaskSummary> } {
  const byId = new Map<string, TaskSummary>();
  for (const section of TASK_SECTIONS) {
    for (const item of sections[section].items) {
      byId.set(item.id, item);
    }
  }
  const items = Array.from(byId.values()).sort((left, right) =>
    right.lastSeenAt.localeCompare(left.lastSeenAt),
  );
  return { items, byId };
}

function setSectionPage(
  current: TaskViewState,
  {
    section,
    page,
    append,
  }: {
    section: TaskHistorySection;
    page: CursorPage<TaskSummary>;
    append: boolean;
  },
): TaskViewState {
  const previousSection = current.sections[section];
  const byId = new Map<string, TaskSummary>(append ? previousSection.byId : undefined);
  for (const item of page.items) {
    byId.set(item.id, item);
  }
  const sectionItems = Array.from(byId.values()).sort((left, right) =>
    right.lastSeenAt.localeCompare(left.lastSeenAt),
  );
  const sections = {
    ...current.sections,
    [section]: {
      ...previousSection,
      items: sectionItems,
      byId,
      nextCursor: page.nextCursor,
      hasNext: page.hasNext,
      loading: false,
      error: null,
    },
  };
  return {
    ...current,
    sections,
    ...mergeCombinedSections(sections),
  };
}

function markRecentlyAdded(
  state: ReturnType<typeof writable<TaskViewState>>,
  taskId: string,
): void {
  state.update((current) => {
    if (current.recentlyAddedIds.has(taskId)) {
      return current;
    }
    return {
      ...current,
      recentlyAddedIds: new Set([...current.recentlyAddedIds, taskId]),
    };
  });
  setTimeout(() => {
    state.update((current) => {
      if (!current.recentlyAddedIds.has(taskId)) {
        return current;
      }
      const next = new Set(current.recentlyAddedIds);
      next.delete(taskId);
      return { ...current, recentlyAddedIds: next };
    });
  }, 2000);
}

export interface TaskStore extends Readable<TaskViewState> {
  refresh(): Promise<void>;
  loadMore(section: TaskHistorySection): Promise<void>;
  setQuery(query: TaskListQuery): Promise<void>;
  select(taskId: string): Promise<void>;
  clearSelection(): void;
  connect(): void;
  disconnect(): void;
}

export function createTaskStore(client: MonitorClient, pageSize = 25): TaskStore {
  const state = writable<TaskViewState>(initialState());
  let stream: MonitorStream | null = null;
  let currentQuery: TaskListQuery = {};
  let countsRefreshTimer: ReturnType<typeof setTimeout> | null = null;
  let sectionsRefreshTimer: ReturnType<typeof setTimeout> | null = null;

  const refreshCounts = async (): Promise<void> => {
    try {
      const sectionCounts = await client.getTaskSectionCounts(currentQuery);
      state.update((current) => ({ ...current, sectionCounts }));
    } catch {
      // Keep prior counts when the aggregate endpoint fails transiently.
    }
  };

  const refreshSection = async (
    section: TaskHistorySection,
    {
      append,
      cursor,
    }: {
      append: boolean;
      cursor?: string;
    },
  ): Promise<void> => {
    const query = { ...currentQuery, section };
    const page = await client.listTasks(pageSize, cursor, query);
    state.update((current) => setSectionPage(current, { section, page, append }));
  };

  const refreshAllSections = async (): Promise<void> => {
    state.update((current) => ({
      ...current,
      loading: true,
      error: null,
      sections: TASK_SECTIONS.reduce(
        (next, section) => ({
          ...next,
          [section]: {
            ...current.sections[section],
            loading: true,
            error: null,
          },
        }),
        {} as Record<TaskHistorySection, TaskSectionState>,
      ),
    }));

    const results = await Promise.allSettled(
      TASK_SECTIONS.map(async (section) => {
        const page = await client.listTasks(pageSize, undefined, { ...currentQuery, section });
        return { section, page };
      }),
    );

    let firstError: string | null = null;
    state.update((current) => {
      let next = current;
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          next = setSectionPage(next, {
            section: result.value.section,
            page: result.value.page,
            append: false,
          });
          return;
        }

        const message =
          result.reason instanceof Error ? result.reason.message : 'Failed to load tasks';
        firstError ??= message;
        const section = TASK_SECTIONS[index] ?? 'queued';
        next = {
          ...next,
          sections: {
            ...next.sections,
            [section]: {
              ...next.sections[section],
              loading: false,
              error: message,
            },
          },
        };
      });
      return {
        ...next,
        loading: false,
        error: firstError,
      };
    });
  };

  const refresh = async (): Promise<void> => {
    await Promise.all([refreshAllSections(), refreshCounts()]);
  };

  const loadMore = async (section: TaskHistorySection): Promise<void> => {
    let cursor: string | null = null;
    state.update((current) => {
      cursor = current.sections[section].nextCursor;
      return {
        ...current,
        sections: {
          ...current.sections,
          [section]: {
            ...current.sections[section],
            loading: true,
            error: null,
          },
        },
      };
    });
    if (cursor === null) {
      state.update((current) => ({
        ...current,
        sections: {
          ...current.sections,
          [section]: {
            ...current.sections[section],
            loading: false,
          },
        },
      }));
      return;
    }

    try {
      await refreshSection(section, { append: true, cursor });
    } catch (error) {
      state.update((current) => ({
        ...current,
        sections: {
          ...current.sections,
          [section]: {
            ...current.sections[section],
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load more tasks',
          },
        },
      }));
    }
  };

  const setQuery = async (query: TaskListQuery): Promise<void> => {
    currentQuery = query;
    await refresh();
  };

  const select = async (taskId: string): Promise<void> => {
    state.update((current) => ({
      ...current,
      selectedTaskId: taskId,
      selectedTaskLoading: true,
      selectedTaskError: null,
      selectedTask: current.selectedTaskId === taskId ? current.selectedTask : null,
      selectedTimeline: current.selectedTaskId === taskId ? current.selectedTimeline : null,
      selectedGraph: current.selectedTaskId === taskId ? current.selectedGraph : null,
    }));

    let taskDetail: TaskDetail | null = null;
    let selectedTaskError: string | null = null;
    try {
      taskDetail = await client.getTask(taskId);
    } catch (err) {
      selectedTaskError = err instanceof Error ? err.message : 'Failed to load task detail';
    }

    state.update((current) => {
      if (current.selectedTaskId !== taskId) return current;
      return { ...current, selectedTaskLoading: false, selectedTask: taskDetail, selectedTaskError };
    });

    if (taskDetail === null) return;

    const [timelineResult, graphResult] = await Promise.allSettled([
      client.getTaskTimeline(taskId),
      client.getTaskGraph(taskId),
    ]);

    state.update((current) => {
      if (current.selectedTaskId !== taskId) return current;
      return {
        ...current,
        selectedTimeline: timelineResult.status === 'fulfilled' ? timelineResult.value : null,
        selectedGraph: graphResult.status === 'fulfilled' ? graphResult.value : null,
      };
    });
  };

  const clearSelection = (): void => {
    state.update((current) => ({
      ...current,
      selectedTaskId: null,
      selectedTask: null,
      selectedTimeline: null,
      selectedGraph: null,
      selectedTaskLoading: false,
      selectedTaskError: null,
    }));
  };

  const scheduleCountsRefresh = (): void => {
    if (countsRefreshTimer !== null) {
      clearTimeout(countsRefreshTimer);
    }
    countsRefreshTimer = setTimeout(() => {
      countsRefreshTimer = null;
      void refreshCounts();
    }, 250);
  };

  const scheduleSectionsRefresh = (): void => {
    if (sectionsRefreshTimer !== null) {
      clearTimeout(sectionsRefreshTimer);
    }
    sectionsRefreshTimer = setTimeout(() => {
      sectionsRefreshTimer = null;
      void refreshAllSections();
    }, 250);
  };

  const handleStreamEvent = async (event: StreamEvent): Promise<void> => {
    if (event.type !== 'task.created' && event.type !== 'task.updated') {
      return;
    }
    if (event.taskId !== null) {
      markRecentlyAdded(state, event.taskId);
    }
    scheduleCountsRefresh();
    scheduleSectionsRefresh();

    let selectedTaskId: string | null = null;
    state.update((current) => {
      selectedTaskId = current.selectedTaskId;
      return { ...current };
    });
    if (event.taskId !== null && selectedTaskId === event.taskId) {
      try {
        const selectedTask = await client.getTask(event.taskId);
        if (!matchesQuery(selectedTask, currentQuery)) {
          return;
        }
        state.update((current) => ({
          ...current,
          selectedTask,
        }));
      } catch {
        // Keep last good detail snapshot if the refresh fails.
      }
    }
  };

  const connect = (): void => {
    if (stream !== null) return;
    stream = client.createStream(
      (event) => {
        void handleStreamEvent(event);
      },
      (connected) => {
        state.update((current) => ({ ...current, streamConnected: connected }));
      },
    );
  };

  const disconnect = (): void => {
    if (countsRefreshTimer !== null) {
      clearTimeout(countsRefreshTimer);
      countsRefreshTimer = null;
    }
    if (sectionsRefreshTimer !== null) {
      clearTimeout(sectionsRefreshTimer);
      sectionsRefreshTimer = null;
    }
    stream?.close();
    stream = null;
    state.update((current) => ({ ...current, streamConnected: false }));
  };

  return {
    subscribe: state.subscribe,
    refresh,
    loadMore,
    setQuery,
    select,
    clearSelection,
    connect,
    disconnect,
  };
}

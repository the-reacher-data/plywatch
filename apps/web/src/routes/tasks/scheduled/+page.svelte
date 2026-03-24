<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { Trash2 } from 'lucide-svelte';

  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import { monitorClient } from '$lib/core/monitor-client';
  import type { ScheduleSummary } from '$lib/core/contracts/monitor';
  import ScheduledRunList from '$lib/features/tasks/components/ScheduledRunList.svelte';
  import TaskDetailPanel from '$lib/features/tasks/components/TaskDetailPanel.svelte';
  import {
    buildScheduledHref,
    buildTasksHref,
    clearTaskQueueFilter,
    clearTaskWorkerFilter,
  } from '$lib/features/tasks/domain/task-navigation';
  import { sharedTaskStore as tasks } from '$lib/features/tasks/domain/shared-task-store';

  let selectedTask = $state<import('$lib/core/contracts/monitor').TaskDetail | null>(null);
  let selectedTimeline = $state<import('$lib/core/contracts/monitor').TaskTimeline | null>(null);
  let selectedGraph = $state<import('$lib/core/contracts/monitor').TaskGraph | null>(null);
  let selectedTaskLoading = $state(false);
  let selectedTaskError = $state<string | null>(null);

  $effect(() => {
    return tasks.subscribe((s) => {
      selectedTask = s.selectedTask;
      selectedTimeline = s.selectedTimeline;
      selectedGraph = s.selectedGraph;
      selectedTaskLoading = s.selectedTaskLoading;
      selectedTaskError = s.selectedTaskError;
    });
  });

  let panelOpen = $state(false);
  let panelTaskId = $state<string | null>(null);
  let expandedScheduleIds = $state(new Set<string>());
  let selectedScheduleIds = $state(new Set<string>());
  let selectionMode = $state(false);
  let schedules = $state<ScheduleSummary[]>([]);
  let schedulesLoading = $state(false);
  let schedulesError = $state<string | null>(null);
  let removeDialogOpen = $state(false);
  let adminBusy = $state(false);
  let nowMs = $state(Date.now());

  const queueFilter = $derived(page.url.searchParams.get('queue'));
  const workerFilter = $derived(page.url.searchParams.get('worker'));
  const selectedTaskId = $derived(panelTaskId);
  const allTasksHref = $derived(
    buildTasksHref(resolve('/tasks'), { queue: queueFilter, worker: workerFilter })
  );
  const scheduledHref = $derived(
    buildScheduledHref(resolve('/tasks/scheduled'), { queue: queueFilter, worker: workerFilter })
  );
  const clearQueueHref = $derived(
    clearTaskQueueFilter(resolve('/tasks/scheduled'), { queue: queueFilter, worker: workerFilter })
  );
  const clearWorkerHref = $derived(
    clearTaskWorkerFilter(resolve('/tasks/scheduled'), { queue: queueFilter, worker: workerFilter })
  );

  const openDetail = (taskId: string): void => {
    panelTaskId = taskId;
    panelOpen = true;
    void tasks.select(taskId);
  };

  const closeDetail = (): void => {
    panelOpen = false;
    panelTaskId = null;
    tasks.clearSelection();
  };

  const toggleScheduleExpanded = (scheduleId: string, nextExpanded: boolean): void => {
    const next = new Set(expandedScheduleIds);
    if (nextExpanded) {
      next.add(scheduleId);
    } else {
      next.delete(scheduleId);
    }
    expandedScheduleIds = next;
  };

  const toggleScheduleSelection = (scheduleId: string, selected: boolean): void => {
    const next = new Set(selectedScheduleIds);
    if (selected) next.add(scheduleId);
    else next.delete(scheduleId);
    selectedScheduleIds = next;
  };

  const loadSchedules = (): (() => void) => {
    const query = {
      ...(queueFilter !== null ? { queue: queueFilter } : {}),
      ...(workerFilter !== null ? { workerHostname: workerFilter } : {}),
    };
    schedulesLoading = true;
    schedulesError = null;
    let cancelled = false;
    void monitorClient
      .listSchedules(50, query)
      .then((result) => {
        if (cancelled) return;
        schedules = result;
        schedulesLoading = false;
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        schedules = [];
        schedulesLoading = false;
        schedulesError = error instanceof Error ? error.message : 'Unable to load schedules.';
      });
    return () => {
      cancelled = true;
    };
  };

  const removeSelectedSchedules = async (): Promise<void> => {
    adminBusy = true;
    try {
      await monitorClient.removeSchedules(Array.from(selectedScheduleIds));
      selectionMode = false;
      selectedScheduleIds = new Set();
      closeDetail();
      loadSchedules();
    } finally {
      adminBusy = false;
      removeDialogOpen = false;
    }
  };

  $effect(() => {
    const id = setInterval(() => {
      nowMs = Date.now();
    }, 30_000);
    return () => clearInterval(id);
  });

  $effect(() => {
    tasks.connect();
    return () => tasks.disconnect();
  });

  $effect(() => loadSchedules());

  const toggleSelectionMode = (): void => {
    if (selectionMode) {
      selectionMode = false;
      selectedScheduleIds = new Set();
      return;
    }
    selectionMode = true;
  };
</script>

<section class="scheduled-shell">
  <header class="page-header">
    <div class="page-header-top">
      <h2>Tasks</h2>
      {#if queueFilter !== null}
        <a class="filter-chip" href={clearQueueHref}>
          {queueFilter} <span aria-hidden="true">×</span>
        </a>
      {/if}
      {#if workerFilter !== null}
        <a class="filter-chip filter-chip-worker" href={clearWorkerHref}>
          {workerFilter} <span aria-hidden="true">×</span>
        </a>
      {/if}
    </div>
    <nav class="tasks-subnav" aria-label="Tasks views">
      <a class="subnav-tab" href={allTasksHref}>History</a>
      <a class="subnav-tab is-active" href={scheduledHref} aria-current="page">Scheduled</a>
    </nav>
  </header>

  {#if schedulesError !== null}
    <div class="error-banner" role="alert">{schedulesError}</div>
  {/if}

  <div class="list-toolbar">
    {#if selectionMode && selectedScheduleIds.size > 0}
      <button class="admin-btn admin-btn-danger" type="button" onclick={() => { removeDialogOpen = true; }}>
        Remove selected ({selectedScheduleIds.size})
      </button>
    {/if}
    <button
      class="admin-icon-btn"
      class:is-active={selectionMode}
      type="button"
      title={selectionMode ? 'Cancel selection' : 'Select schedules to remove'}
      aria-label={selectionMode ? 'Cancel selection' : 'Select schedules to remove'}
      onclick={toggleSelectionMode}
    >
      <Trash2 size={14} strokeWidth={2} />
    </button>
  </div>

  <div class="scheduled-layout">
    <div class="scheduled-main">
      {#if schedulesLoading}
        <p class="state-hint">Loading schedules…</p>
      {:else if schedules.length === 0}
        <p class="state-hint">No observed scheduled runs yet.</p>
      {:else}
        <ScheduledRunList
          {schedules}
          {selectedTaskId}
          onSelect={openDetail}
          selectionEnabled={selectionMode}
          {selectedScheduleIds}
          onToggleScheduleSelection={toggleScheduleSelection}
          {expandedScheduleIds}
          onToggleExpanded={toggleScheduleExpanded}
          {nowMs}
        />
      {/if}
    </div>

    {#if panelOpen && panelTaskId !== null}
      <TaskDetailPanel
        taskId={panelTaskId}
        loading={selectedTaskLoading}
        task={selectedTask}
        timeline={selectedTimeline}
        graph={selectedGraph}
        allTasks={[]}
        taskError={selectedTaskError}
        onClose={closeDetail}
        onRetry={() => {
          if (panelTaskId !== null) void tasks.select(panelTaskId);
        }}
        onSelectTask={openDetail}
      />
    {/if}
  </div>

  <ConfirmDialog
    open={removeDialogOpen}
    title="Remove schedules from monitor"
    message="This removes the selected schedules and their retained runs from monitor data only. It does not delete the real Celery schedule source."
    confirmLabel="Remove selected"
    destructive={true}
    busy={adminBusy}
    onConfirm={() => { void removeSelectedSchedules(); }}
    onCancel={() => { if (!adminBusy) removeDialogOpen = false; }}
  />
</section>

<style>
  .scheduled-shell {
    display: grid;
    gap: 1rem;
  }

  .page-header {
    display: grid;
    gap: 0.75rem;
  }

  .list-toolbar {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .admin-icon-btn {
    width: 1.9rem;
    height: 1.9rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #d1d5db;
    border-radius: 0.55rem;
    background: #fff;
    color: #475569;
    font: inherit;
    cursor: pointer;
  }

  .admin-icon-btn.is-active {
    border-color: #fecaca;
    background: #fff1f2;
    color: #b91c1c;
  }

  .admin-btn {
    border: 1px solid #d1d5db;
    border-radius: 0.65rem;
    background: #fff;
    color: #1f2937;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.45rem 0.8rem;
    cursor: pointer;
  }

  .admin-btn-danger {
    border-color: #fecaca;
    color: #b91c1c;
  }

  .page-header-top {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .page-header h2 {
    margin: 0;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.55rem;
    border-radius: 3px;
    font-size: 0.78rem;
    font-weight: 600;
    text-decoration: none;
  }

  .filter-chip {
    background: #eff6ff;
    color: #1d4ed8;
  }

  .filter-chip-worker {
    background: #f0fdf4;
    color: #15803d;
  }

  .tasks-subnav {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.2rem;
    border: 1px solid #e2e8f0;
    border-radius: 0.7rem;
    background: #f8fafc;
    width: fit-content;
  }

  .subnav-tab {
    display: inline-flex;
    align-items: center;
    padding: 0.38rem 0.7rem;
    border-radius: 0.55rem;
    color: #526171;
    font-size: 0.8rem;
    font-weight: 600;
    text-decoration: none;
  }

  .subnav-tab:hover {
    color: #1f2937;
    background: #eef2f7;
  }

  .subnav-tab.is-active {
    background: #ffffff;
    color: #111827;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
  }

  .scheduled-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 1rem;
  }

  .error-banner {
    padding: 0.75rem 1rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 4px;
    color: #b91c1c;
    font-size: 0.84rem;
  }

  .state-hint {
    margin: 0;
    padding: 2rem 1rem;
    text-align: center;
    color: #9ca3af;
    font-size: 0.84rem;
    background: #fff;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
  }
</style>

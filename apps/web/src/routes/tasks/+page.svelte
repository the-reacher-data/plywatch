<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { ChevronDown, Trash2 } from 'lucide-svelte';

  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import InfoHint from '$lib/components/InfoHint.svelte';
  import { monitorClient } from '$lib/core/monitor-client';
  import TaskFamilyList from '$lib/features/tasks/components/TaskFamilyList.svelte';
  import TaskDetailPanel from '$lib/features/tasks/components/TaskDetailPanel.svelte';
  import { buildTaskSummaryKpis } from '$lib/features/tasks/components/task-summary-kpis';
  import { buildTaskFamilies } from '$lib/features/tasks/domain/group-task-families';
  import { filterTaskHistoryItems } from '$lib/features/tasks/domain/task-history-visibility';
  import {
    buildTasksHref,
    buildScheduledHref,
    clearTaskQueueFilter,
    clearTaskWorkerFilter,
  } from '$lib/features/tasks/domain/task-navigation';
  import { sharedTaskStore as tasks } from '$lib/features/tasks/domain/shared-task-store';
  import type { TaskHistorySection } from '$lib/core/ports/monitor-client';

  // List + pagination state: $derived is fine — these only change from refresh/loadMore/SSE,
  // all of which are synchronous store updates from the same tick.
  const items = $derived($tasks.items);
  const loading = $derived($tasks.loading);
  const storeError = $derived($tasks.error);
  const sectionCounts = $derived($tasks.sectionCounts);
  const sections = $derived($tasks.sections);

  // Selected-task state: must use direct subscribe, NOT $derived.
  // $derived reads the store value at derivation time and only re-runs when its reactive
  // dependencies change. Updates that arrive from async Promise continuations (e.g. when
  // getTask() resolves after a network round-trip) may not trigger a re-run because Svelte 5
  // does not observe the writable store subscription inside $derived the same way it does
  // inside $effect. Running tasks work by coincidence: SSE stream events keep firing
  // task.updated which resets selectedTaskLoading, masking the timing gap. Completed tasks
  // receive zero SSE events after they finish, so the one-shot update from getTask() would
  // be silently dropped and the panel stays on "Loading task detail…" forever.
  // Direct subscribe guarantees the callback fires synchronously on every state.update().
  let selectedTask = $state<import('$lib/core/contracts/monitor').TaskDetail | null>(null);
  let selectedTimeline = $state<import('$lib/core/contracts/monitor').TaskTimeline | null>(null);
  let selectedGraph = $state<import('$lib/core/contracts/monitor').TaskGraph | null>(null);
  let selectedTaskLoading = $state(false);
  let selectedTaskError = $state<string | null>(null);
  let streamConnected = $state(false);
  let recentlyAddedIds = $state(new Set<string>());

  $effect(() => {
    return tasks.subscribe((s) => {
      selectedTask = s.selectedTask;
      selectedTimeline = s.selectedTimeline;
      selectedGraph = s.selectedGraph;
      selectedTaskLoading = s.selectedTaskLoading;
      selectedTaskError = s.selectedTaskError;
      streamConnected = s.streamConnected;
      recentlyAddedIds = s.recentlyAddedIds;
    });
  });

  // Local panel + UI state only.
  let panelOpen = $state(false);
  let panelTaskId = $state<string | null>(null);
  let expandedFamilyIds = $state(new Set<string>());
  let selectedFamilyIds = $state(new Set<string>());
  let selectionMode = $state(false);
  let removeDialogOpen = $state(false);
  let adminBusy = $state(false);
  let openSections = $state(new Set<TaskHistorySection>(['queued', 'running', 'succeeded', 'failed']));
  let nowMs = $state(Date.now());

  $effect(() => {
    const id = setInterval(() => { nowMs = Date.now(); }, 30_000);
    return () => clearInterval(id);
  });

  const queueFilter = $derived(page.url.searchParams.get('queue'));
  const workerFilter = $derived(page.url.searchParams.get('worker'));
  const tasksHref = $derived(
    buildTasksHref(resolve('/tasks'), { queue: queueFilter, worker: workerFilter })
  );
  const scheduledHref = $derived.by(() => {
    return buildScheduledHref(resolve('/tasks/scheduled'), {
      queue: queueFilter,
      worker: workerFilter,
    });
  });
  const clearQueueHref = $derived(
    clearTaskQueueFilter(resolve('/tasks'), { queue: queueFilter, worker: workerFilter })
  );
  const clearWorkerHref = $derived(
    clearTaskWorkerFilter(resolve('/tasks'), { queue: queueFilter, worker: workerFilter })
  );

  const visibleItems = $derived(filterTaskHistoryItems(items, nowMs));
  const families = $derived(buildTaskFamilies(visibleItems));
  const queuedItems = $derived(filterTaskHistoryItems(sections.queued.items, nowMs));
  const runningItems = $derived(filterTaskHistoryItems(sections.running.items, nowMs));
  const succeededItems = $derived(filterTaskHistoryItems(sections.succeeded.items, nowMs));
  const failedItems = $derived(filterTaskHistoryItems(sections.failed.items, nowMs));
  const queuedFamilies = $derived(buildTaskFamilies(queuedItems));
  const runningFamilies = $derived(buildTaskFamilies(runningItems));
  const succeededFamilies = $derived(buildTaskFamilies(succeededItems));
  const failedFamilies = $derived(buildTaskFamilies(failedItems));
  const familyCount = $derived(sectionCounts?.familyCount ?? families.length);
  const executionCount = $derived(sectionCounts?.executionCount ?? visibleItems.length);
  const totalCompleted = $derived(
    sectionCounts?.completedExecutions ?? families.reduce((sum, family) => sum + family.completedCount, 0)
  );
  const totalProgress = $derived(
    sectionCounts?.totalExecutions ?? families.reduce((sum, family) => sum + family.totalCount, 0)
  );
  const queuedFamilyCount = $derived(sectionCounts?.queuedFamilies ?? queuedFamilies.length);
  const runningFamilyCount = $derived(sectionCounts?.runningFamilies ?? runningFamilies.length);
  const succeededFamilyCount = $derived(sectionCounts?.succeededFamilies ?? succeededFamilies.length);
  const failedFamilyCount = $derived(sectionCounts?.failedFamilies ?? failedFamilies.length);
  const summaryKpis = $derived(
    buildTaskSummaryKpis({ familyCount, executionCount, totalCompleted, totalProgress })
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

  const toggleSection = (section: TaskHistorySection): void => {
    const next = new Set(openSections);
    if (next.has(section)) {
      next.delete(section);
    } else {
      next.add(section);
    }
    openSections = next;
  };

  const toggleExpanded = (familyId: string, nextExpanded: boolean): void => {
    const next = new Set(expandedFamilyIds);
    if (nextExpanded) {
      next.add(familyId);
    } else {
      next.delete(familyId);
    }
    expandedFamilyIds = next;
  };

  const toggleFamilySelection = (familyId: string, selected: boolean): void => {
    const next = new Set(selectedFamilyIds);
    if (selected) next.add(familyId);
    else next.delete(familyId);
    selectedFamilyIds = next;
  };

  const removeSelectedFamilies = async (): Promise<void> => {
    adminBusy = true;
    try {
      await monitorClient.removeTaskRows(Array.from(selectedFamilyIds));
      selectionMode = false;
      selectedFamilyIds = new Set();
      closeDetail();
      await tasks.refresh();
    } finally {
      adminBusy = false;
      removeDialogOpen = false;
    }
  };

  $effect(() => {
    void tasks.setQuery({
      ...(queueFilter !== null ? { queue: queueFilter } : {}),
      ...(workerFilter !== null ? { workerHostname: workerFilter } : {}),
    });
  });

  $effect(() => {
    tasks.connect();
    return () => tasks.disconnect();
  });

  const toggleSelectionMode = (): void => {
    if (selectionMode) {
      selectionMode = false;
      selectedFamilyIds = new Set();
      return;
    }
    selectionMode = true;
  };

  const handleKeydown = (e: KeyboardEvent): void => {
    if (e.key === 'Escape' && panelOpen) {
      closeDetail();
      return;
    }
    if (!panelOpen || panelTaskId === null) return;
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const currentIdx = visibleItems.findIndex((t) => t.id === panelTaskId);
    if (currentIdx === -1) return;
    const nextIdx = e.key === 'ArrowDown' ? currentIdx + 1 : currentIdx - 1;
    if (nextIdx >= 0 && nextIdx < visibleItems.length) {
      openDetail(visibleItems[nextIdx].id);
    }
  };
</script>

<svelte:window onkeydown={handleKeydown} />

<section class="tasks-shell">
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
      <a class="subnav-tab is-active" href={tasksHref} aria-current="page">History</a>
      <a class="subnav-tab" href={scheduledHref}>Scheduled</a>
    </nav>
  </header>

  <div class="tasks-summary" aria-label="Task summary">
    {#each summaryKpis as kpi (kpi.key)}
      <span class="summary-chip" class:summary-chip-progress={kpi.key === 'completed'}>
        <strong>{kpi.value}</strong>
        <span class="summary-chip-label">
          <span>{kpi.label}</span>
          <InfoHint lines={[kpi.helpText]} title={kpi.label} />
        </span>
      </span>
    {/each}
  </div>

  {#if !streamConnected && items.length > 0}
    <div class="disconnected-banner" role="status">
      <span class="disconnected-dot"></span>
      Stream disconnected — data may be stale
    </div>
  {/if}

  {#if storeError !== null}
    <div class="error-banner" role="alert">{storeError}</div>
  {/if}

  <div class="list-toolbar">
    {#if selectionMode && selectedFamilyIds.size > 0}
      <button class="admin-btn admin-btn-danger" type="button" onclick={() => { removeDialogOpen = true; }}>
        Remove selected ({selectedFamilyIds.size})
      </button>
    {/if}
    <button
      class="admin-icon-btn"
      class:is-active={selectionMode}
      type="button"
      title={selectionMode ? 'Cancel selection' : 'Select tasks to remove'}
      aria-label={selectionMode ? 'Cancel selection' : 'Select tasks to remove'}
      onclick={toggleSelectionMode}
    >
      <Trash2 size={14} strokeWidth={2} />
    </button>
  </div>

  <div class="tasks-col">
    {#if loading && items.length === 0}
      <p class="state-hint">Loading tasks…</p>
    {:else}
      <!-- Queued -->
      <div class="accordion-section">
        <button
          class="accordion-header"
          type="button"
          onclick={() => toggleSection('queued')}
          aria-expanded={openSections.has('queued')}
        >
          <span class="section-dot tone-queued"></span>
          <span class="section-label">Queued</span>
          <span class="section-count">{queuedFamilyCount}</span>
          <span class="section-chevron" class:open={openSections.has('queued')}>▾</span>
        </button>
        {#if openSections.has('queued')}
          <div class="accordion-body">
            {#if sections.queued.error !== null}
              <p class="section-error">{sections.queued.error}</p>
            {/if}
            {#if queuedFamilies.length > 0}
              <TaskFamilyList
                families={queuedFamilies}
                selectedTaskId={panelTaskId}
                onSelect={openDetail}
                selectionEnabled={selectionMode}
                {selectedFamilyIds}
                onToggleFamilySelection={toggleFamilySelection}
                {expandedFamilyIds}
                onToggleExpanded={toggleExpanded}
                {nowMs}
                {recentlyAddedIds}
              />
              {#if sections.queued.hasNext}
                <div class="load-more-wrap">
                  <button
                    class="load-more"
                    type="button"
                    onclick={() => void tasks.loadMore('queued')}
                    disabled={sections.queued.loading}
                  >
                    <ChevronDown size={14} strokeWidth={2} />
                    <span>{sections.queued.loading ? 'Loading…' : 'Show more'}</span>
                  </button>
                  <p class="load-more-hint">Older queued executions in this section</p>
                </div>
              {/if}
            {:else}
              <p class="section-empty">No queued tasks.</p>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Running -->
      <div class="accordion-section">
        <button
          class="accordion-header"
          type="button"
          onclick={() => toggleSection('running')}
          aria-expanded={openSections.has('running')}
        >
          <span class="section-dot tone-active"></span>
          <span class="section-label">Running</span>
          <span class="section-count">{runningFamilyCount}</span>
          <span class="section-chevron" class:open={openSections.has('running')}>▾</span>
        </button>
        {#if openSections.has('running')}
          <div class="accordion-body">
            {#if sections.running.error !== null}
              <p class="section-error">{sections.running.error}</p>
            {/if}
            {#if runningFamilies.length > 0}
              <TaskFamilyList
                families={runningFamilies}
                selectedTaskId={panelTaskId}
                onSelect={openDetail}
                selectionEnabled={selectionMode}
                {selectedFamilyIds}
                onToggleFamilySelection={toggleFamilySelection}
                {expandedFamilyIds}
                onToggleExpanded={toggleExpanded}
                {nowMs}
                {recentlyAddedIds}
              />
              {#if sections.running.hasNext}
                <div class="load-more-wrap">
                  <button
                    class="load-more"
                    type="button"
                    onclick={() => void tasks.loadMore('running')}
                    disabled={sections.running.loading}
                  >
                    <ChevronDown size={14} strokeWidth={2} />
                    <span>{sections.running.loading ? 'Loading…' : 'Show more'}</span>
                  </button>
                  <p class="load-more-hint">Older running executions in this section</p>
                </div>
              {/if}
            {:else}
              <p class="section-empty">No running tasks.</p>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Succeeded -->
      <div class="accordion-section">
        <button
          class="accordion-header"
          type="button"
          onclick={() => toggleSection('succeeded')}
          aria-expanded={openSections.has('succeeded')}
        >
          <span class="section-dot tone-success"></span>
          <span class="section-label">Succeeded</span>
          <span class="section-count">{succeededFamilyCount}</span>
          <span class="section-chevron" class:open={openSections.has('succeeded')}>▾</span>
        </button>
        {#if openSections.has('succeeded')}
          <div class="accordion-body">
            {#if sections.succeeded.error !== null}
              <p class="section-error">{sections.succeeded.error}</p>
            {/if}
            {#if succeededFamilies.length > 0}
              <TaskFamilyList
                families={succeededFamilies}
                selectedTaskId={panelTaskId}
                onSelect={openDetail}
                selectionEnabled={selectionMode}
                {selectedFamilyIds}
                onToggleFamilySelection={toggleFamilySelection}
                {expandedFamilyIds}
                onToggleExpanded={toggleExpanded}
                {nowMs}
                {recentlyAddedIds}
              />
              {#if sections.succeeded.hasNext}
                <div class="load-more-wrap">
                  <button
                    class="load-more"
                    type="button"
                    onclick={() => void tasks.loadMore('succeeded')}
                    disabled={sections.succeeded.loading}
                  >
                    <ChevronDown size={14} strokeWidth={2} />
                    <span>{sections.succeeded.loading ? 'Loading…' : 'Show more'}</span>
                  </button>
                  <p class="load-more-hint">Older completed executions in this section</p>
                </div>
              {/if}
            {:else}
              <p class="section-empty">No succeeded tasks.</p>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Failed -->
      <div class="accordion-section">
        <button
          class="accordion-header"
          type="button"
          onclick={() => toggleSection('failed')}
          aria-expanded={openSections.has('failed')}
        >
          <span class="section-dot tone-danger"></span>
          <span class="section-label">Failed</span>
          <span class="section-count">{failedFamilyCount}</span>
          <span class="section-chevron" class:open={openSections.has('failed')}>▾</span>
        </button>
        {#if openSections.has('failed')}
          <div class="accordion-body">
            {#if sections.failed.error !== null}
              <p class="section-error">{sections.failed.error}</p>
            {/if}
            {#if failedFamilies.length > 0}
              <TaskFamilyList
                families={failedFamilies}
                selectedTaskId={panelTaskId}
                onSelect={openDetail}
                selectionEnabled={selectionMode}
                {selectedFamilyIds}
                onToggleFamilySelection={toggleFamilySelection}
                {expandedFamilyIds}
                onToggleExpanded={toggleExpanded}
                {nowMs}
                {recentlyAddedIds}
              />
              {#if sections.failed.hasNext}
                <div class="load-more-wrap">
                  <button
                    class="load-more"
                    type="button"
                    onclick={() => void tasks.loadMore('failed')}
                    disabled={sections.failed.loading}
                  >
                    <ChevronDown size={14} strokeWidth={2} />
                    <span>{sections.failed.loading ? 'Loading…' : 'Show more'}</span>
                  </button>
                  <p class="load-more-hint">Older failed executions in this section</p>
                </div>
              {/if}
            {:else}
              <p class="section-empty">No failed tasks.</p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

  </div>

  <!-- Fixed right-side drawer: overlays content, no layout shift. -->
  {#if panelOpen && panelTaskId !== null}
    <TaskDetailPanel
      taskId={panelTaskId}
      loading={selectedTaskLoading}
      task={selectedTask}
      timeline={selectedTimeline}
      graph={selectedGraph}
      allTasks={items}
      taskError={selectedTaskError}
      onClose={closeDetail}
      onRetry={() => { if (panelTaskId !== null) void tasks.select(panelTaskId); }}
      onSelectTask={openDetail}
    />
  {/if}

  <ConfirmDialog
    open={removeDialogOpen}
    title="Remove tasks from monitor"
    message="This removes the selected task rows from retained monitor data only. It does not cancel or delete the real Celery executions."
    confirmLabel="Remove selected"
    destructive={true}
    busy={adminBusy}
    onConfirm={() => { void removeSelectedFamilies(); }}
    onCancel={() => { if (!adminBusy) removeDialogOpen = false; }}
  />
</section>

<style>
  .tasks-shell {
    display: grid;
    gap: 1rem;
  }

  .tasks-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: center;
  }

  .summary-chip {
    display: inline-flex;
    align-items: baseline;
    gap: 0.4rem;
    padding: 0.45rem 0.7rem;
    border: 1px solid #e2e6eb;
    border-radius: 999px;
    background: #ffffff;
    color: #4b5563;
    font-size: 0.8rem;
  }

  .summary-chip-label {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }

  .summary-chip strong {
    color: #111827;
    font-size: 0.92rem;
  }

  .summary-chip-progress {
    background: #f8fafc;
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

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.55rem;
    background: #eff6ff;
    color: #1d4ed8;
    border-radius: 3px;
    font-size: 0.78rem;
    font-weight: 600;
    text-decoration: none;
    transition: background 0.15s;
  }

  .filter-chip:hover {
    background: #dbeafe;
  }

  .filter-chip-worker {
    background: #f0fdf4;
    color: #15803d;
  }

  .filter-chip-worker:hover {
    background: #dcfce7;
  }

  .disconnected-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.85rem;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 4px;
    color: #92400e;
    font-size: 0.82rem;
    font-weight: 500;
  }

  .disconnected-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: #d97706;
    flex-shrink: 0;
  }

  .error-banner {
    padding: 0.75rem 1rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 4px;
    color: #b91c1c;
    font-size: 0.84rem;
  }

  .tasks-col {
    display: grid;
    gap: 0.5rem;
  }

  /* Accordion */
  .accordion-section {
    background: #fff;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  }

  .accordion-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    padding: 0.7rem 1rem;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    font: inherit;
    transition: background 0.12s;
  }

  .accordion-header:hover {
    background: #f6f7f9;
  }

  .section-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .section-label {
    font-size: 0.84rem;
    font-weight: 600;
    color: #111827;
  }

  .section-count {
    font-size: 0.72rem;
    font-weight: 600;
    color: #6b7280;
    background: #f3f4f6;
    padding: 0.1rem 0.42rem;
    border-radius: 3px;
  }

  .section-chevron {
    margin-left: auto;
    font-size: 0.8rem;
    color: #9ca3af;
    transition: transform 0.18s ease;
    display: inline-block;
  }

  .section-chevron.open {
    transform: rotate(0deg);
  }

  .section-chevron:not(.open) {
    transform: rotate(-90deg);
  }

  .accordion-body {
    border-top: 1px solid #e2e6eb;
    display: grid;
    gap: 0.75rem;
    padding: 0.75rem;
  }

  .section-empty {
    margin: 0;
    padding: 0.5rem 0;
    text-align: center;
    color: #9ca3af;
    font-size: 0.84rem;
  }

  .section-error {
    margin: 0;
    padding: 0.55rem 0.7rem;
    border: 1px solid #fecaca;
    border-radius: 0.5rem;
    background: #fef2f2;
    color: #b91c1c;
    font-size: 0.8rem;
  }

  .tone-queued { background: #9ca3af; }
  .tone-active { background: #2563eb; }
  .tone-success { background: #16a34a; }
  .tone-danger { background: #dc2626; }

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

  .load-more-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    margin-top: 0.9rem;
  }

  .load-more {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    justify-content: center;
    min-width: 8.5rem;
    padding: 0.42rem 0.95rem;
    border: 1px solid #dde3ea;
    border-radius: 999px;
    background: transparent;
    color: #4b5563;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s, color 0.12s;
  }

  .load-more:hover:not(:disabled) {
    background: #f8fafc;
    border-color: #cfd7e3;
    color: #1f2937;
  }

  .load-more:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .load-more-hint {
    margin: 0;
    color: #9aa4b2;
    font-size: 0.72rem;
    text-align: center;
  }

</style>

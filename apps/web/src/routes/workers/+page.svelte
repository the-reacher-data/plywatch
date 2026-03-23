<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';

  import type { TaskSectionCounts } from '$lib/core/contracts/monitor';
  import { monitorClient } from '$lib/core/monitor-client';
  import WorkerCard from '$lib/features/workers/components/WorkerCard.svelte';
  import { buildTasksHref } from '$lib/features/tasks/domain/task-navigation';
  import WorkerDetailPanel from '$lib/features/workers/components/WorkerDetailPanel.svelte';
  import { sharedWorkersStore as workers } from '$lib/features/workers/shared-workers-store';
  import { tasksForWorker } from '$lib/features/workers/workers-domain';

  const requestedHostname = $derived(page.url.searchParams.get('hostname'));

  // User's explicit selection. Null means fallback to URL or first worker.
  let manualHostname = $state<string | null>(null);

  // Read directly from the Svelte 4 store — fully synchronous reactive chain,
  // no $effect intermediary that could introduce a one-tick delay.
  const selectedWorkerHostname = $derived(
    manualHostname ?? requestedHostname ?? $workers.items[0]?.hostname ?? null
  );

  const selectedWorker = $derived(
    selectedWorkerHostname === null
      ? null
      : ($workers.items.find((w) => w.hostname === selectedWorkerHostname) ?? null)
  );

  const workerTasks = $derived(
    selectedWorker === null ? [] : tasksForWorker($workers.tasks, selectedWorker.hostname)
  );

  const tasksHref = $derived(buildTasksHref(resolve('/tasks'), { worker: selectedWorkerHostname }));

  let selectedWorkerCounts = $state<TaskSectionCounts | null>(null);
  let selectedWorkerCountsLoading = $state(false);

  $effect(() => {
    const hostname = selectedWorkerHostname;
    if (hostname === null) {
      selectedWorkerCounts = null;
      selectedWorkerCountsLoading = false;
      return;
    }

    const controller = new AbortController();
    selectedWorkerCountsLoading = true;

    void monitorClient
      .getTaskSectionCounts({ workerHostname: hostname })
      .then((counts) => {
        if (!controller.signal.aborted) {
          selectedWorkerCounts = counts;
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          selectedWorkerCounts = null;
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          selectedWorkerCountsLoading = false;
        }
      });

    return () => controller.abort();
  });

  $effect(() => {
    void workers.refresh();
    workers.connect();
    return () => workers.disconnect();
  });
</script>

<section class="workers-shell">
  <header class="page-header">
    <h2>Workers</h2>
  </header>

  {#if $workers.error !== null}
    <div class="error-banner" role="alert">{$workers.error}</div>
  {/if}

  <div class="content-split">
    <div class="worker-list">
      {#if $workers.loading && $workers.items.length === 0}
        <p class="state-hint">Loading workers…</p>
      {:else if $workers.items.length === 0}
        <p class="state-hint">No workers detected yet.</p>
      {:else}
        {#each $workers.items as worker (worker.hostname)}
          <WorkerCard
            {worker}
            selected={selectedWorkerHostname === worker.hostname}
            onSelect={() => (manualHostname = worker.hostname)}
          />
        {/each}
      {/if}
    </div>

    <div class="detail-area">
      {#if selectedWorker !== null}
        <WorkerDetailPanel
          worker={selectedWorker}
          tasks={workerTasks}
          loading={$workers.loading}
          counts={selectedWorkerCounts}
          countsLoading={selectedWorkerCountsLoading}
          {tasksHref}
        />
      {:else if !$workers.loading}
        <div class="empty-detail">
          <span class="empty-icon">◔</span>
          <p>Select a worker to inspect it.</p>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .workers-shell {
    display: grid;
    gap: 1.25rem;
  }

  .page-header h2 {
    margin: 0;
  }

  .error-banner {
    padding: 0.75rem 1rem;
    background: #fdf0f0;
    border: 1px solid #f0c0c0;
    border-radius: 0.65rem;
    color: #9b2b2b;
    font-size: 0.84rem;
  }

  .content-split {
    display: grid;
    grid-template-columns: 320px minmax(0, 1fr);
    gap: 1rem;
    align-items: start;
  }

  .worker-list {
    display: grid;
    gap: 0.55rem;
    position: sticky;
    top: 2rem;
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
    padding-right: 0.25rem;
  }

  .detail-area {
    min-width: 0;
  }

  .state-hint {
    margin: 0;
    padding: 1rem;
    font-size: 0.84rem;
    color: #8496a9;
    text-align: center;
  }

  .empty-detail {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    min-height: 12rem;
    border: 1px dashed #d8e0ea;
    border-radius: 1rem;
    color: #8496a9;
  }

  .empty-icon {
    font-size: 1.75rem;
    opacity: 0.4;
  }

  .empty-detail p {
    margin: 0;
    font-size: 0.84rem;
  }

  @media (max-width: 900px) {
    .content-split {
      grid-template-columns: 1fr;
    }

    .worker-list {
      position: static;
      max-height: none;
      overflow-y: visible;
    }
  }
</style>

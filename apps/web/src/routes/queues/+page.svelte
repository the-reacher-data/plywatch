<script lang="ts">
  import { resolve } from '$app/paths';
  import { page } from '$app/state';

  import { monitorClient } from '$lib/core/monitor-client';
  import type { TaskSummary } from '$lib/core/contracts/monitor';
  import QueueCard from '$lib/features/queues/components/QueueCard.svelte';
  import QueueDetailPanel from '$lib/features/queues/components/QueueDetailPanel.svelte';
  import { sharedQueuesStore as queues } from '$lib/features/queues/shared-queues-store';
  import { buildTasksHref } from '$lib/features/tasks/domain/task-navigation';
  import { resolveSelectedQueueName, shouldRefreshQueuesForEvent } from '$lib/features/queues/queues-domain';

  const requestedQueueName = $derived(page.url.searchParams.get('queue'));

  let manualQueueName = $state<string | null>(null);
  let initialQuerySelectionApplied = $state(false);
  let queueTasks = $state<TaskSummary[]>([]);
  let tasksLoading = $state(false);
  let currentTasksForQueue: string | null = null;
  let sseDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let taskRefreshTick = $state(0);
  let taskRequestVersion = 0;
  let lastRequestedQueueName = $state<string | null>(null);
  const queueTaskCache = new Map<string, TaskSummary[]>();

  const queueNames = $derived($queues.items.map((queue) => queue.name));

  const selectedQueueName = $derived(
    resolveSelectedQueueName(
      queueNames,
      manualQueueName,
      requestedQueueName,
      initialQuerySelectionApplied,
    )
  );

  const selectedQueue = $derived(
    selectedQueueName === null
      ? null
      : ($queues.items.find((queue) => queue.name === selectedQueueName) ?? null)
  );
  const queueHref = $derived.by(() => {
    return buildTasksHref(resolve('/tasks'), { queue: selectedQueueName });
  });

  async function fetchQueueTasks(
    queueName: string,
    signal: AbortSignal,
    requestVersion: number,
  ): Promise<void> {
    try {
      const result = await monitorClient.listTasks(200, undefined, { queue: queueName }, signal);
      if (signal.aborted || requestVersion !== taskRequestVersion) {
        return;
      }
      currentTasksForQueue = queueName;
      queueTaskCache.set(queueName, result.items);
      queueTasks = result.items;
      tasksLoading = false;
    } catch {
      if (signal.aborted) return;
      if (requestVersion !== taskRequestVersion) {
        return;
      }
      currentTasksForQueue = queueName;
      queueTasks = queueTaskCache.get(queueName) ?? [];
      tasksLoading = false;
    }
  }

  function scheduleTaskRefresh(): void {
    if (sseDebounceTimer !== null) clearTimeout(sseDebounceTimer);
    sseDebounceTimer = setTimeout(() => {
      sseDebounceTimer = null;
      taskRefreshTick++;
    }, 300);
  }

  $effect(() => {
    const requested = requestedQueueName;
    if (requested !== lastRequestedQueueName) {
      lastRequestedQueueName = requested;
      initialQuerySelectionApplied = false;
    }
  });

  $effect(() => {
    if (
      !initialQuerySelectionApplied &&
      requestedQueueName !== null &&
      selectedQueueName === requestedQueueName
    ) {
      initialQuerySelectionApplied = true;
    }
  });

  $effect(() => {
    void queues.refresh();
    const stream = monitorClient.createStream((event) => {
      if (!shouldRefreshQueuesForEvent(event.type, event.queueName)) {
        return;
      }
      void queues.refresh();
      scheduleTaskRefresh();
    });

    return () => {
      stream.close();
      if (sseDebounceTimer !== null) clearTimeout(sseDebounceTimer);
    };
  });

  $effect(() => {
    const queue = selectedQueueName;
    void taskRefreshTick; // track SSE refresh dependency

    if (queue === null) {
      currentTasksForQueue = null;
      queueTasks = [];
      tasksLoading = false;
      return;
    }

    if (queue !== currentTasksForQueue) {
      queueTasks = queueTaskCache.get(queue) ?? [];
    }
    tasksLoading = true;

    const controller = new AbortController();
    const requestVersion = ++taskRequestVersion;
    void fetchQueueTasks(queue, controller.signal, requestVersion);
    return () => controller.abort();
  });
</script>

<section class="queues-shell">
  <header class="page-header">
    <h2>Queues</h2>
  </header>

  {#if $queues.error !== null}
    <div class="error-banner" role="alert">{$queues.error}</div>
  {/if}

  <div class="content-split">
    <div class="queue-list">
      {#if $queues.loading && $queues.items.length === 0}
        <p class="state-hint">Loading queues…</p>
      {:else if $queues.items.length === 0}
        <p class="state-hint">No queues observed yet.</p>
      {:else}
        {#each $queues.items as queue (queue.name)}
          <QueueCard
            {queue}
            selected={selectedQueueName === queue.name}
            onSelect={() => {
              if (selectedQueueName === queue.name) {
                return;
              }
              manualQueueName = queue.name;
              initialQuerySelectionApplied = true;
            }}
          />
        {/each}
      {/if}
    </div>

    <div class="detail-area">
      {#if selectedQueue !== null}
        {#key selectedQueue.name}
          <QueueDetailPanel
            queue={selectedQueue}
            tasks={queueTasks}
            {queueHref}
            loading={tasksLoading}
          />
        {/key}
      {:else if !$queues.loading}
        <div class="empty-detail">
          <span class="empty-icon">⊞</span>
          <p>Select a queue to inspect it.</p>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .queues-shell {
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

  .queue-list {
    display: grid;
    gap: 0.55rem;
    position: sticky;
    top: 2rem;
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
    padding-right: 0.25rem;
  }

  /* subtle scrollbar */
  .queue-list::-webkit-scrollbar {
    width: 4px;
  }
  .queue-list::-webkit-scrollbar-track {
    background: transparent;
  }
  .queue-list::-webkit-scrollbar-thumb {
    background: #d8e0ea;
    border-radius: 999px;
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

    .queue-list {
      position: static;
      max-height: none;
      overflow-y: visible;
    }
  }
</style>

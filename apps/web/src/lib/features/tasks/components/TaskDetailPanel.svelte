<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import type { TaskDetail, TaskGraph, TaskTimeline, TaskSummary } from '$lib/core/contracts/monitor';
  import TaskLifecycleBar from '$lib/components/live/TaskLifecycleBar.svelte';
  import TaskFamilyTree from '$lib/features/tasks/components/TaskFamilyTree.svelte';

  interface Props {
    taskId: string | null;
    loading: boolean;
    task: TaskDetail | null;
    timeline: TaskTimeline | null;
    graph: TaskGraph | null;
    allTasks: TaskSummary[];
    taskError?: string | null;
    onClose: () => void;
    onRetry?: () => void;
    onSelectTask?: (taskId: string) => void;
  }

  let {
    taskId,
    loading,
    task,
    timeline,
    graph,
    allTasks,
    taskError = null,
    onClose,
    onRetry,
    onSelectTask
  }: Props = $props();

  let copiedId = $state(false);
  let timelineOpen = $state(false);
  let familyOpen = $state(true);
  let lastFamilyGraphRootId = $state<string | null>(null);

  const toneByTaskState: Record<string, 'neutral' | 'active' | 'success' | 'failure' | 'retry'> = {
    sent: 'neutral',
    received: 'active',
    started: 'active',
    retrying: 'retry',
    succeeded: 'success',
    failed: 'failure',
    lost: 'failure'
  };

  const copyTaskId = (): void => {
    if (task === null) return;
    void navigator.clipboard.writeText(task.id).then(() => {
      copiedId = true;
      setTimeout(() => { copiedId = false; }, 1500);
    });
  };

  const shortId = $derived(task !== null ? `${task.id.slice(0, 8)}…` : '');
  const taskTone = $derived(task !== null ? (toneByTaskState[task.state] ?? 'neutral') : 'neutral');
  const hasTimeline = $derived((timeline?.items ?? []).length > 0);

  // Build a lookup map for timing enrichment — O(1) per node lookup in family tree.
  const byId = $derived(new Map(allTasks.map((t) => [t.id, t])));
  const graphNodeIds = $derived(new Set((graph?.nodes ?? []).map((node) => node.id)));
  const visibleGraphNodeCount = $derived(
    (graph?.nodes ?? []).filter((node) => !(node.id === graph?.rootId && node.kind === 'canvas')).length
  );
  const familyGraphEdges = $derived(
    (graph?.edges ?? []).filter((edge) => edge.source !== edge.target)
  );
  const familyHasCanvasRoot = $derived(
    (graph?.nodes ?? []).some((node) => node.id === graph?.rootId && node.kind === 'canvas') ?? false
  );
  const familyHasParallelism = $derived.by(() => {
    if (graph === null) return false;
    const visibleNodeIds = new Set(
      graph.nodes
        .filter((node) => !(node.id === graph.rootId && node.kind === 'canvas'))
        .map((node) => node.id)
    );
    const phaseCounts = new Map<string, number>();
    for (const edge of familyGraphEdges) {
      if (visibleNodeIds.has(edge.target)) {
        phaseCounts.set(edge.target, (phaseCounts.get(edge.target) ?? 0) + 1);
      }
    }
    const outgoingBySource = new Map<string, number>();
    for (const edge of familyGraphEdges) {
      if (visibleNodeIds.has(edge.source)) {
        outgoingBySource.set(edge.source, (outgoingBySource.get(edge.source) ?? 0) + 1);
      }
    }
    return Array.from(outgoingBySource.values()).some((count) => count > 1);
  });
  const familyHasJoin = $derived.by(() => {
    if (graph === null) return false;
    const incomingByTarget = new Map<string, number>();
    for (const edge of familyGraphEdges) {
      incomingByTarget.set(edge.target, (incomingByTarget.get(edge.target) ?? 0) + 1);
    }
    return Array.from(incomingByTarget.values()).some((count) => count > 1);
  });
  const familyUsesDagLanguage = $derived(
    familyHasCanvasRoot || familyHasParallelism || familyHasJoin
  );
  const parentTargetId = $derived(
    task?.parentId !== null &&
    task?.parentId !== undefined &&
    task?.parentId !== task?.id &&
    (byId.has(task.parentId) || graphNodeIds.has(task.parentId))
      ? task.parentId
      : null
  );

  const PANEL_WIDTH = 500;

  const timeFormatter = new Intl.DateTimeFormat('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });

  const eventLabel = (eventType: string): string => {
    if (eventType === 'task-retried') return 'Retry scheduled';
    if (eventType === 'task-received') return 'Received by worker';
    if (eventType === 'task-started') return 'Started';
    if (eventType === 'task-succeeded') return 'Succeeded';
    if (eventType === 'task-failed') return 'Failed';
    if (eventType === 'task-lost') return 'Lost';
    if (eventType === 'task-sent') return 'Queued';
    return eventType;
  };

  const eventTone = (eventType: string): string => {
    if (eventType === 'task-failed') return 'failure';
    if (eventType === 'task-lost') return 'failure';
    if (eventType === 'task-succeeded') return 'success';
    if (eventType === 'task-retried') return 'retry';
    return 'active';
  };

  const formatTime = (capturedAt: string): string => {
    const date = new Date(capturedAt);
    if (!Number.isFinite(date.getTime())) return capturedAt;
    return timeFormatter.format(date);
  };

  const familySummary = $derived.by(() => {
    if (!familyUsesDagLanguage) {
      return 'Parent and child tasks for this execution.';
    }
    return 'Compact stage view of the execution DAG. Expand a stage to inspect its tasks.';
  });

  $effect(() => {
    const currentTaskId = taskId;
    if (currentTaskId === null) return;
    timelineOpen = false;
  });

  $effect(() => {
    const graphRootId = graph?.rootId ?? null;
    if (graphRootId === null) {
      lastFamilyGraphRootId = null;
      familyOpen = true;
      return;
    }

    if (graphRootId !== lastFamilyGraphRootId) {
      const nodeCount = visibleGraphNodeCount;
      familyOpen = nodeCount <= 8;
      lastFamilyGraphRootId = graphRootId;
    }
  });
</script>

{#if taskId !== null}
  <!-- Backdrop: subtle dimming, click to close -->
  <div
    class="backdrop"
    role="presentation"
    transition:fade={{ duration: 160 }}
    onclick={onClose}
  ></div>

  <!-- Right-side drawer -->
  <aside
    class="drawer"
    aria-label="Task detail"
    transition:fly={{ x: PANEL_WIDTH, duration: 200, opacity: 1 }}
  >
    <header class="drawer-header tone-{taskTone}">
      <div class="drawer-title">
        <h2>{task?.name ?? taskId}</h2>
        {#if task !== null}
          <div class="title-meta">
            <span class="state-pill tone-{taskTone}">{task.state}</span>
            {#if task.kind !== 'unknown'}
              <span class="meta-pill">{task.kind}</span>
            {/if}
            {#if task.queue !== null}
              <span class="meta-pill">{task.queue}</span>
            {/if}
          </div>
        {:else}
          <p>Loading task snapshot…</p>
        {/if}
      </div>
      <button class="close-btn" type="button" onclick={onClose} aria-label="Close panel">×</button>
    </header>

    {#if loading && task === null}
      <div class="skeleton-block">
        <div class="skeleton-line wide"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line narrow"></div>
      </div>
    {:else if taskError !== null}
      <div class="state-block error-block">
        <p class="error-copy">{taskError}</p>
        {#if onRetry !== undefined}
          <button class="retry-btn" type="button" onclick={onRetry}>Retry</button>
        {/if}
      </div>
    {:else if task !== null}
      {#if parentTargetId !== null && onSelectTask !== undefined}
        {@const parentId = parentTargetId}
        {@const selectTask = onSelectTask}
        {@const parentName = byId.get(parentId)?.name ?? parentId}
        <button class="parent-nav" type="button" onclick={() => selectTask(parentId)}>
          <span class="parent-nav-icon" aria-hidden="true">↑</span>
          <div class="parent-nav-copy">
            <span class="parent-nav-label">Parent task</span>
            <span class="parent-nav-name">{parentName}</span>
          </div>
          <span class="parent-nav-chevron" aria-hidden="true">→</span>
        </button>
      {/if}

      <div class="lifecycle-wrap tone-{taskTone}">
        <TaskLifecycleBar state={task.state} retries={task.retries} startedAt={task.startedAt} finishedAt={task.finishedAt} />
      </div>

      <div class="stack">
        {#if graph !== null && graph.nodes.length > 1 && task !== null}
          <section class="detail-card family-card">
            <button
              class="section-toggle"
              type="button"
              aria-expanded={familyOpen}
              onclick={() => (familyOpen = !familyOpen)}
            >
                <div class="section-heading">
                  <div>
                    <h3>Task family</h3>
                    <p>{familySummary}</p>
                  </div>
                <div class="section-heading-meta">
                  {#if familyUsesDagLanguage}
                    <span class="section-badge">{visibleGraphNodeCount} nodes</span>
                  {/if}
                  <span class="section-chevron">{familyOpen ? '▾' : '▸'}</span>
                </div>
              </div>
            </button>
            {#if familyOpen}
              <TaskFamilyTree
                root={task}
                {graph}
                {byId}
                selectedTaskId={taskId}
                onSelectTask={onSelectTask ?? (() => {})}
              />
            {/if}
          </section>
        {/if}

        <section class="detail-card tone-{taskTone}">
          <h3>Execution</h3>
          <dl>
            <dt>Task ID</dt>
            <dd class="id-row">
              <code class="id-value" title={task.id}>{shortId}</code>
              <button
                class="copy-btn"
                class:copied={copiedId}
                type="button"
                onclick={copyTaskId}
                aria-label="Copy task ID"
              >{copiedId ? 'Copied!' : 'Copy'}</button>
            </dd>
            <dt>Queue</dt>
            <dd>{task.queue ?? '—'}</dd>
            <dt>Worker</dt>
            <dd>{task.workerHostname ?? '—'}</dd>
            <dt>Retries</dt>
            <dd>{task.retries}</dd>
          </dl>
        </section>

        <section class="detail-card tone-{taskTone}">
          <h3>Outcome</h3>
          <dl>
            <dt>Result</dt>
            <dd>{task.resultPreview ?? '—'}</dd>
            <dt>Error</dt>
            <dd>{task.exceptionPreview ?? '—'}</dd>
          </dl>
        </section>

        <section class="detail-card">
          <h3>Payload</h3>
          <dl>
            <dt>Args</dt>
            <dd class="block-value">{task.argsPreview ?? '—'}</dd>
            <dt>Kwargs</dt>
            <dd class="block-value">{task.kwargsPreview ?? '—'}</dd>
          </dl>
        </section>

        {#if hasTimeline}
          <section class="detail-card timeline-card">
            <button
              class="timeline-toggle"
              type="button"
              aria-expanded={timelineOpen}
              onclick={() => (timelineOpen = !timelineOpen)}
            >
              <span class="timeline-title">Timeline</span>
              <span class="timeline-meta">{timeline?.count ?? 0} events</span>
              <span class="timeline-chevron" class:is-open={timelineOpen}>▾</span>
            </button>
            {#if timelineOpen}
              <ol class="event-list">
                {#each timeline?.items ?? [] as event (`${event.eventType}-${event.capturedAt}`)}
                  <li class="event-item">
                    <span class="event-dot node-{eventTone(event.eventType)}" aria-hidden="true"></span>
                    <span class="event-label">{eventLabel(event.eventType)}</span>
                    <span class="event-time">{formatTime(event.capturedAt)}</span>
                  </li>
                {/each}
              </ol>
            {/if}
          </section>
        {/if}
      </div>
    {/if}
  </aside>
{/if}

<style>
  .section-toggle {
    width: 100%;
    border: none;
    background: transparent;
    padding: 0;
    text-align: left;
    cursor: pointer;
  }

  .section-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.9rem;
  }

  .section-heading-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .section-heading h3 {
    margin: 0;
  }

  .section-heading p {
    margin: 0.25rem 0 0;
    color: #6b7280;
    font-size: 0.88rem;
    line-height: 1.4;
  }

  .section-badge {
    flex: 0 0 auto;
    padding: 0.18rem 0.55rem;
    border-radius: 999px;
    background: #eef4ff;
    color: #35548a;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .section-chevron {
    color: #8ea2b3;
    font-size: 0.9rem;
    line-height: 1;
    padding-top: 0.2rem;
  }

  .structure-pill {
    background: #eef4ff;
    color: #35548a;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.10);
    z-index: 49;
    cursor: pointer;
  }

  .drawer {
    position: fixed;
    right: 0;
    top: 0;
    height: 100dvh;
    width: clamp(320px, 38vw, 500px);
    background: #fff;
    border-left: 1px solid #e2e6eb;
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.08);
    overflow-y: auto;
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.25rem;
    padding-bottom: calc(1.25rem + env(safe-area-inset-bottom, 0px));
    box-sizing: border-box;
    overscroll-behavior: contain;
  }

  .drawer-header {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    justify-content: space-between;
    padding: 1rem 1.05rem;
    border: 1px solid #e2e6eb;
    border-radius: 0.9rem;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  }

  .drawer-header.tone-active {
    border-color: #bfdbfe;
    background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
  }

  .drawer-header.tone-success {
    border-color: #bbf7d0;
    background: linear-gradient(180deg, #f7fcf8 0%, #eef9f0 100%);
  }

  .drawer-header.tone-failure {
    border-color: #fecaca;
    background: linear-gradient(180deg, #fff8f8 0%, #fef2f2 100%);
  }

  .drawer-header.tone-retry {
    border-color: #fde68a;
    background: linear-gradient(180deg, #fffdf7 0%, #fffbeb 100%);
  }

  /* Parent task navigation banner */
  .parent-nav {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    padding: 0.65rem 0.9rem;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    background: #f6f7f9;
    color: inherit;
    text-align: left;
    cursor: pointer;
    font: inherit;
    transition: background 0.12s, border-color 0.12s;
  }

  .parent-nav:hover {
    background: #eff6ff;
    border-color: #2563eb;
  }

  .parent-nav-icon {
    font-size: 1rem;
    color: #6b7280;
    flex-shrink: 0;
    line-height: 1;
  }

  .parent-nav-copy {
    display: grid;
    gap: 0.08rem;
    flex: 1;
    min-width: 0;
  }

  .parent-nav-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9ca3af;
  }

  .parent-nav-name {
    font-size: 0.84rem;
    font-weight: 500;
    color: #1d4ed8;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .parent-nav-chevron {
    color: #9ca3af;
    font-size: 0.9rem;
    flex-shrink: 0;
  }

  .drawer-title h2 {
    margin: 0;
    font-size: 1rem;
    overflow-wrap: anywhere;
    color: #111827;
  }

  .drawer-title p {
    margin: 0.2rem 0 0;
    font-size: 0.78rem;
    color: #6b7280;
    text-transform: capitalize;
  }

  .title-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.45rem;
  }

  .state-pill,
  .meta-pill {
    display: inline-flex;
    align-items: center;
    min-height: 1.6rem;
    padding: 0.05rem 0.52rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .meta-pill {
    border: 1px solid #dbe3ec;
    background: rgba(255, 255, 255, 0.72);
    color: #536578;
  }

  .state-pill.tone-active {
    background: #dbeafe;
    color: #1d4ed8;
  }

  .state-pill.tone-success {
    background: #dcfce7;
    color: #15803d;
  }

  .state-pill.tone-failure {
    background: #fee2e2;
    color: #b91c1c;
  }

  .state-pill.tone-retry {
    background: #fef3c7;
    color: #b45309;
  }

  .state-pill.tone-neutral {
    background: #e5e7eb;
    color: #4b5563;
  }

  .close-btn {
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e2e6eb;
    border-radius: 4px;
    background: #fff;
    color: #6b7280;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }

  .close-btn:hover {
    background: #f6f7f9;
    color: #111827;
  }

  .lifecycle-wrap {
    padding: 0.85rem 1rem;
    border: 1px solid #e2e6eb;
    border-radius: 0.85rem;
    background: #f6f7f9;
  }

  .lifecycle-wrap.tone-active {
    border-color: #bfdbfe;
    background: #eff6ff;
  }

  .lifecycle-wrap.tone-success {
    border-color: #bbf7d0;
    background: #f0fdf4;
  }

  .lifecycle-wrap.tone-failure {
    border-color: #fecaca;
    background: #fef2f2;
  }

  .lifecycle-wrap.tone-retry {
    border-color: #fde68a;
    background: #fffbeb;
  }

  .state-block {
    padding: 1.5rem 1rem;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    background: #f6f7f9;
  }

  .skeleton-block {
    display: grid;
    gap: 0.6rem;
    padding: 1.25rem 1rem;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    background: #f6f7f9;
  }

  .skeleton-line {
    height: 0.75rem;
    border-radius: 3px;
    background: linear-gradient(90deg, #e2e6eb 25%, #f3f4f6 50%, #e2e6eb 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.4s ease-in-out infinite;
    width: 70%;
  }

  .skeleton-line.wide { width: 100%; }
  .skeleton-line.narrow { width: 40%; }

  @keyframes skeleton-shimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .error-block {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
    border-color: #fecaca;
    background: #fef2f2;
  }

  .error-copy {
    margin: 0;
    color: #b91c1c;
    font-size: 0.84rem;
  }

  .retry-btn {
    padding: 0.35rem 0.85rem;
    border: 1px solid #fecaca;
    border-radius: 4px;
    background: #fff;
    color: #b91c1c;
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }

  .retry-btn:hover {
    background: #fef2f2;
    border-color: #f87171;
  }

  .stack {
    display: grid;
    gap: 0.65rem;
  }

  .detail-card {
    padding: 0.9rem 1rem;
    border: 1px solid #e2e6eb;
    border-radius: 0.9rem;
    background: #fff;
    min-width: 0;
  }

  .detail-card.tone-active {
    border-color: #dbeafe;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  }

  .detail-card.tone-success {
    border-color: #dcfce7;
    background: linear-gradient(180deg, #ffffff 0%, #f8fdf9 100%);
  }

  .detail-card.tone-failure {
    border-color: #fee2e2;
    background: linear-gradient(180deg, #ffffff 0%, #fff8f8 100%);
  }

  .detail-card.tone-retry {
    border-color: #fef3c7;
    background: linear-gradient(180deg, #ffffff 0%, #fffdf7 100%);
  }

  .detail-card h3 {
    margin: 0 0 0.65rem;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
  }

  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.5rem 1rem;
    margin: 0;
  }

  dt {
    color: #6b7280;
    font-size: 0.82rem;
    font-weight: 600;
  }

  dd {
    margin: 0;
    font-size: 0.84rem;
    overflow-wrap: anywhere;
    color: #111827;
  }

  .id-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .id-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    color: #374151;
    cursor: default;
  }

  .copy-btn {
    padding: 0.1rem 0.45rem;
    border: 1px solid #e2e6eb;
    border-radius: 3px;
    background: #fff;
    color: #6b7280;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s, color 0.12s;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .copy-btn:hover {
    background: #f3f4f6;
    border-color: #d1d5db;
    color: #374151;
  }

  .copy-btn.copied {
    background: #f0fdf4;
    border-color: #bbf7d0;
    color: #15803d;
  }

  .block-value {
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 8rem;
    overflow: auto;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
  }

  /* Node-connector timeline */
  .event-list {
    position: relative;
    padding: 0 1rem 0.85rem 2.4rem;
    display: grid;
    gap: 0;
  }

  .event-list::before {
    content: '';
    position: absolute;
    left: 1.65rem;
    top: 0.3rem;
    bottom: 0.85rem;
    width: 1.5px;
    background: #e2e6eb;
  }

  .event-item {
    position: relative;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 0.5rem;
    padding: 0.28rem 0;
  }

  .event-dot {
    position: absolute;
    left: -1.25rem;
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: #9ca3af;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1.5px #d1d5db;
    flex-shrink: 0;
    z-index: 1;
  }

  .node-success { background: #16a34a; box-shadow: 0 0 0 1.5px #bbf7d0; }
  .node-failure { background: #dc2626; box-shadow: 0 0 0 1.5px #fecaca; }
  .node-retry   { background: #d97706; box-shadow: 0 0 0 1.5px #fde68a; }
  .node-active  { background: #2563eb; box-shadow: 0 0 0 1.5px #bfdbfe; }

  .event-label {
    font-size: 0.82rem;
    color: #111827;
    font-weight: 500;
  }

  .event-time {
    font-size: 0.76rem;
    color: #9ca3af;
    white-space: nowrap;
  }

  /* Family tree card — no inner padding, tree manages its own row padding */
  .family-card {
    padding-bottom: 0.4rem;
  }

  .family-card h3 {
    padding: 0 1rem;
    margin-bottom: 0.5rem;
  }

  .timeline-card {
    padding: 0;
    overflow: clip;
  }

  .timeline-toggle {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: 0.75rem;
    padding: 0.95rem 1rem;
    border: 0;
    background: transparent;
    text-align: left;
    cursor: pointer;
    font: inherit;
  }

  .timeline-toggle:hover {
    background: #f8fafc;
  }

  .timeline-title {
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
  }

  .timeline-meta {
    font-size: 0.75rem;
    color: #94a3b8;
    white-space: nowrap;
  }

  .timeline-chevron {
    color: #64748b;
    transition: transform 0.18s ease;
  }

  .timeline-chevron.is-open {
    transform: rotate(180deg);
  }
</style>

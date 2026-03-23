<script lang="ts">
  import InfoHint from '$lib/components/InfoHint.svelte';
  import type { TaskSectionCounts, TaskSummary, WorkerSummary } from '$lib/core/contracts/monitor';
  import {
    buildWorkerKpis,
    buildWorkerRecentActivity,
    buildWorkerSlices,
    buildWorkerSlicesFromCounts,
    formatLastHeartbeat,
    formatRelativeTime
  } from '$lib/features/workers/workers-domain';

  interface Props {
    worker: WorkerSummary;
    tasks: TaskSummary[];
    loading?: boolean;
    counts?: TaskSectionCounts | null;
    countsLoading?: boolean;
    tasksHref: string;
  }

  const { worker, tasks, loading = false, counts = null, countsLoading = false, tasksHref }: Props = $props();

  const kpis = $derived(buildWorkerKpis(worker));
  const slices = $derived(counts === null ? buildWorkerSlices(tasks) : buildWorkerSlicesFromCounts(counts));
  const recentActivity = $derived(buildWorkerRecentActivity(tasks));
</script>

<article class="detail-panel" aria-label="Worker detail: {worker.hostname}">
  <header class="detail-header">
    <div class="detail-title">
      <h3>{worker.hostname}</h3>
      <p>{worker.state} · heartbeat {formatLastHeartbeat(worker)} · seen {formatRelativeTime(worker.lastSeenAt)}</p>
    </div>
    <a class="open-tasks-link" href={tasksHref}>Open tasks →</a>
  </header>

  <div class="kpi-strip">
    {#each kpis as kpi (kpi.key)}
      <div class={`kpi-card tone-${kpi.tone}`}>
        <span class="kpi-label">
          {kpi.label}
          {#if kpi.helpText !== undefined}
            <InfoHint title={kpi.label} lines={[kpi.helpText]} />
          {/if}
        </span>
        <strong class="kpi-value">{kpi.value}</strong>
        <span class="kpi-sub">{kpi.hint}</span>
      </div>
    {/each}
  </div>

  <section class="prop-section">
    <h4 class="section-title">Task mix</h4>
    <div class="prop-legend">
      {#each slices as slice (slice.key)}
        <span class="prop-item">
          <i class={`prop-dot tone-${slice.tone}`}></i>
          <span class="prop-label">{slice.label}</span>
          <strong class="prop-count">{slice.count}</strong>
        </span>
      {/each}
    </div>
    {#if countsLoading}
      <p class="mix-hint">Refreshing worker totals…</p>
    {/if}
  </section>

  {#if recentActivity.length > 0}
    <section class="activity-section">
      <h4 class="section-title">Recent task activity</h4>
      <div class="activity-list">
        {#each recentActivity as item (item.id)}
          <div class="activity-row">
            <span class={`activity-dot tone-${item.tone}`}></span>
            <span class="activity-name">{item.label}</span>
            <span class={`state-badge tone-badge-${item.tone}`}>{item.state}</span>
            <span class="activity-time">{item.lastSeenAt}</span>
          </div>
        {/each}
      </div>
    </section>
  {:else if !loading}
    <p class="empty-hint">No retained tasks on this worker yet.</p>
  {/if}

  {#if loading}
    <p class="loading-hint">Loading worker activity…</p>
  {/if}
</article>

<style>
  .detail-panel {
    background: #fff;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    padding: 1.25rem;
    display: grid;
    gap: 1.25rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .detail-title h3 {
    margin: 0;
    font-size: 1.05rem;
    color: #111827;
  }

  .detail-title p,
  .open-tasks-link,
  .empty-hint,
  .loading-hint {
    margin: 0.25rem 0 0;
    font-size: 0.78rem;
    color: #6b7280;
  }

  .open-tasks-link {
    color: #2563eb;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
  }

  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .kpi-card {
    display: grid;
    gap: 0.2rem;
    padding: 0.85rem 1rem;
    border-radius: 6px;
    border-left: 3px solid transparent;
  }

  .kpi-card.tone-active { background: #eff6ff; border-left-color: #2563eb; }
  .kpi-card.tone-success,
  .kpi-card.tone-online { background: #f0fdf4; border-left-color: #16a34a; }
  .kpi-card.tone-stale  { background: #fffbeb; border-left-color: #d97706; }
  .kpi-card.tone-neutral { background: #f8fafc; border-left-color: #cbd5e1; }
  .kpi-card.tone-offline,
  .kpi-card.tone-danger { background: #fef2f2; border-left-color: #dc2626; }

  .kpi-label,
  .section-title {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
  }

  .section-title {
    margin: 0 0 0.6rem;
  }

  .kpi-label {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #111827;
    line-height: 1.1;
  }

  .kpi-sub {
    font-size: 0.78rem;
    color: #6b7280;
  }

  .prop-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
  }

  .mix-hint {
    margin: 0.55rem 0 0;
    font-size: 0.78rem;
    color: #6b7280;
  }

  .prop-item {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .prop-dot,
  .activity-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .activity-list {
    display: grid;
    gap: 0.45rem;
  }

  .activity-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    justify-content: space-between;
    padding: 0.55rem 0.75rem;
    border: 1px solid #e2e6eb;
    border-radius: 4px;
    background: #f6f7f9;
  }

  .prop-label,
  .activity-time,
  .activity-name,
  .state-badge {
    font-size: 0.8rem;
  }

  .activity-name {
    flex: 1;
    color: #111827;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .state-badge {
    padding: 0.14rem 0.4rem;
    border-radius: 3px;
    font-weight: 600;
    text-transform: uppercase;
  }

  .tone-online,
  .tone-badge-online { background: #f0fdf4; color: #15803d; }
  .tone-active,
  .tone-badge-active { background: #eff6ff; color: #1d4ed8; }
  .tone-success,
  .tone-badge-success { background: #f0fdf4; color: #15803d; }
  .tone-danger,
  .tone-badge-danger { background: #fef2f2; color: #b91c1c; }
  .tone-neutral,
  .tone-badge-neutral { background: #f3f4f6; color: #6b7280; }

  @media (max-width: 900px) {
    .kpi-strip {
      grid-template-columns: 1fr;
    }
  }
</style>

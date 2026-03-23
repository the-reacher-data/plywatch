<script lang="ts">
  import { onMount } from 'svelte';
  import { resolve } from '$app/paths';

  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import { HttpMonitorClient } from '$lib/core/adapters/http-monitor-client';
  import MultiSparkline from '$lib/components/live/MultiSparkline.svelte';
  import { monitorApiUrl } from '$lib/core/config';
  import { createOverviewStore } from '$lib/features/overview/overview-store';

  const client = new HttpMonitorClient(monitorApiUrl);
  const overview = createOverviewStore(client);
  let resetDialogOpen = $state(false);
  let resetBusy = $state(false);

  // Higher-saturation, perceptually distinct palette for worker lines.
  const workerColors = [
    '#3b82f6', // blue
    '#10b981', // emerald
    '#f59e0b', // amber
    '#8b5cf6', // violet
    '#ef4444', // red
    '#06b6d4', // cyan
    '#ec4899', // pink
    '#84cc16', // lime
  ];

  const lineColor = (index: number): string =>
    workerColors[index % workerColors.length] ?? '#3b82f6';

  // Worker state breakdown
  const onlineWorkers = $derived($overview.workers.filter((w) => w.state === 'online').length);
  const offlineWorkers = $derived($overview.workers.filter((w) => w.state === 'offline').length);
  const staleWorkers  = $derived($overview.workers.filter((w) => w.state === 'stale').length);
  const trackedExecutionsLabel = $derived(
    $overview.snapshot === null
      ? 'Tracked executions in current window'
      : `${$overview.snapshot.taskCount} tracked executions in current window`,
  );
  const repositoryUrl = 'https://github.com/thereacherdata/plywatch';

  onMount(() => {
    void overview.start();
    return () => overview.stop();
  });

  const resetMonitor = async (): Promise<void> => {
    resetBusy = true;
    try {
      await client.resetMonitor();
      await overview.refresh();
    } finally {
      resetBusy = false;
      resetDialogOpen = false;
    }
  };
</script>

<div class="page-header">
  <div class="page-header-main">
    <div class="title-group">
      <h2>Overview</h2>
      {#if $overview.snapshot !== null}
        <div class="release-meta">
          <a class="release-link" href={repositoryUrl} target="_blank" rel="noreferrer">
            GitHub
          </a>
          <span class="release-version">v{$overview.snapshot.version}</span>
        </div>
      {/if}
    </div>
    {#if $overview.snapshot !== null}
      <div class="live-badge">
        <span class="live-dot" aria-hidden="true"></span>
        Live
      </div>
    {/if}
  </div>
  <button
    class="reset-icon-btn"
    type="button"
    title="Reset monitor"
    aria-label="Reset monitor"
    onclick={() => { resetDialogOpen = true; }}
  >
    ↻
  </button>
</div>

{#if $overview.error !== null}
  <div class="error-banner" role="alert">{$overview.error}</div>
{/if}

{#if $overview.snapshot !== null}
  <!-- KPI cards first — most actionable info -->
  <section class="cards">
    <a class="card" href={resolve('/tasks')}>
      <span class="eyebrow">Execution</span>
      <h3>Tasks</h3>
      <p>{$overview.snapshot.taskCount}</p>
      <small>{trackedExecutionsLabel}</small>
    </a>
    <a class="card" href={resolve('/workers')}>
      <span class="eyebrow">Runtime</span>
      <h3>Workers</h3>
      <p>{$overview.snapshot.workerCount}</p>
      <div class="state-breakdown">
        {#if onlineWorkers > 0}
          <span class="sb-chip sb-online">{onlineWorkers} online</span>
        {/if}
        {#if staleWorkers > 0}
          <span class="sb-chip sb-stale">{staleWorkers} stale</span>
        {/if}
        {#if offlineWorkers > 0}
          <span class="sb-chip sb-offline">{offlineWorkers} offline</span>
        {/if}
      </div>
    </a>
    <a class="card" href={resolve('/queues')}>
      <span class="eyebrow">Broker</span>
      <h3>Queues</h3>
      <p>{$overview.snapshot.queueCount}</p>
      <small>Queues with tracked activity</small>
    </a>
    <a class="card card-muted" href={resolve('/events')}>
      <span class="eyebrow">Ingress</span>
      <h3>Events</h3>
      <p>{$overview.snapshot.totalEventCount}</p>
      <small>Buffered in current window</small>
    </a>
  </section>

  <!-- Live pulse — workers integrated, no longer a nav link -->
  {#if $overview.workers.length > 0}
    <section class="pulse-card">
      <div class="pulse-header">
        <div class="pulse-title-group">
          <span class="eyebrow">Live Pulse</span>
          <h3>Worker activity</h3>
        </div>
        <div class="pulse-header-right">
          <span class="pulse-summary">
            {#if onlineWorkers > 0}<span class="ps-online">{onlineWorkers} online</span>{/if}
            {#if staleWorkers > 0}<span class="ps-stale">{staleWorkers} stale</span>{/if}
            {#if offlineWorkers > 0}<span class="ps-offline">{offlineWorkers} offline</span>{/if}
          </span>
          <a class="events-link" href={resolve('/events')}>Event stream →</a>
        </div>
      </div>
      <MultiSparkline
        series={$overview.workers.map((worker, index) => ({
          key: worker.hostname,
          values: worker.series,
          stroke: lineColor(index),
          heartbeatState: worker.state,
          active: worker.active,
        }))}
      />
    </section>
  {/if}
{:else if $overview.loading}
  <p class="state-hint">Loading overview…</p>
{:else}
  <p class="state-hint">Waiting for monitor data…</p>
{/if}

<ConfirmDialog
  open={resetDialogOpen}
  title="Reset monitor"
  message="This removes retained tasks, workers, queues, schedules and raw events from the monitor view. It does not delete real Celery executions or historical totals."
  confirmLabel="Reset monitor"
  destructive={true}
  busy={resetBusy}
  onConfirm={() => { void resetMonitor(); }}
  onCancel={() => { if (!resetBusy) resetDialogOpen = false; }}
/>

<style>
  /* ── Page header ─────────────────────────────── */
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.25rem;
  }

  .page-header-main {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .title-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .page-header h2 {
    margin: 0;
  }

  .release-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.8rem;
    color: #64748b;
  }

  .release-link {
    color: #0f172a;
    text-decoration: none;
    font-weight: 600;
  }

  .release-link:hover {
    text-decoration: underline;
  }

  .release-version {
    color: #475569;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .live-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.2rem 0.6rem;
    border-radius: 3px;
    background: #f0fdf4;
    color: #15803d;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
  }

  .error-banner {
    margin-bottom: 0.75rem;
    padding: 0.85rem 1rem;
    border: 1px solid #fecaca;
    border-radius: 6px;
    background: #fef2f2;
    color: #991b1b;
    font-size: 0.92rem;
  }

  .state-hint {
    margin: 1rem 0 0;
    color: #64748b;
    font-size: 0.95rem;
  }

  .live-dot {
    display: block;
    width: 0.42rem;
    height: 0.42rem;
    border-radius: 50%;
    background: #16a34a;
    animation: live-pulse 1.6s ease-in-out infinite;
  }

  .reset-icon-btn {
    width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #d1d5db;
    border-radius: 999px;
    background: #fff;
    color: #64748b;
    font: inherit;
    font-size: 1rem;
    cursor: pointer;
  }

  .reset-icon-btn:hover {
    border-color: #94a3b8;
    color: #334155;
  }

  @keyframes live-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.5; transform: scale(0.72); }
  }

  /* ── KPI cards ───────────────────────────────── */
  .cards {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .card {
    padding: 1.25rem;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    background: #fff;
    text-decoration: none;
    color: inherit;
    display: grid;
    gap: 0.3rem;
    transition:
      border-color 120ms ease,
      box-shadow 120ms ease;
  }

  a.card:hover {
    border-color: #2563eb;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
  }

  .card-muted {
    background: #f6f7f9;
  }

  .eyebrow {
    color: #9ca3af;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  p {
    font-size: 2rem;
    margin: 0.2rem 0;
    color: #111827;
  }

  h3 {
    margin: 0;
    color: #374151;
  }

  small {
    color: #9ca3af;
    font-size: 0.76rem;
  }

  .state-breakdown {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.1rem;
  }

  .sb-chip {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  .sb-online  { background: #f0fdf4; color: #15803d; }
  .sb-stale   { background: #fffbeb; color: #b45309; }
  .sb-offline { background: #fef2f2; color: #b91c1c; }

  /* ── Pulse card ──────────────────────────────── */
  .pulse-card {
    display: grid;
    gap: 0.85rem;
    padding: 1.1rem 1.25rem 1rem;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    background: #ffffff;
  }

  .pulse-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .pulse-title-group {
    display: grid;
    gap: 0.15rem;
  }

  .pulse-title-group h3 {
    margin: 0;
  }

  .pulse-header-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .pulse-summary {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
  }

  .ps-online, .ps-stale, .ps-offline {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  .ps-online  { background: #f0fdf4; color: #15803d; }
  .ps-stale   { background: #fffbeb; color: #b45309; }
  .ps-offline { background: #fef2f2; color: #b91c1c; }

  .events-link {
    color: #2563eb;
    font-size: 0.78rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
  }

  .events-link:hover {
    text-decoration: underline;
  }

  /* ── Responsive ──────────────────────────────── */
  @media (max-width: 960px) {
    .cards {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .pulse-card {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .cards {
      grid-template-columns: 1fr;
    }
  }
</style>

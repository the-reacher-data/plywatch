<script lang="ts">
  import type { QueueSummary } from '$lib/core/contracts/monitor';
  import {
    buildHealthBar,
    completedFailureRate,
    completedSuccessRate,
    completedTotal,
    formatDurationMs,
    formatRelativeTime,
  } from '../queues-domain';

  interface Props {
    queue: QueueSummary;
    selected: boolean;
    onSelect: () => void;
  }

  let { queue, selected, onSelect }: Props = $props();

  const segments = $derived(buildHealthBar(queue));
  const hasActivity = $derived(queue.activeCount > 0);
  const lastSeen = $derived(formatRelativeTime(queue.lastSeenAt));
  const completedRuns = $derived(completedTotal(queue));
  const successRate = $derived(completedSuccessRate(queue));
  const failRate = $derived(completedFailureRate(queue));
  const avgWait = $derived(formatDurationMs(queue.avgQueueWaitMs));
</script>

<button
  type="button"
  class="queue-card"
  class:selected
  onclick={onSelect}
  aria-pressed={selected}
>
  <div class="card-header">
    <span class="status-dot" class:active={hasActivity}></span>
    <span class="queue-name">{queue.name}</span>
    {#if queue.activeCount > 0}
      <span class="active-pill">{queue.activeCount} active</span>
    {/if}
  </div>

  {#if queue.routingKeys.length > 0}
    <div class="routing-keys">
      {#each queue.routingKeys as key (key)}
        <span class="routing-tag">{key}</span>
      {/each}
    </div>
  {/if}

  <div class="health-bar" aria-label="Queue health distribution">
    {#if segments.length > 0}
      {#each segments as seg (seg.key)}
        <span
          class="health-seg tone-{seg.tone}"
          style="width: {seg.percent}%"
          title="{seg.count} {seg.label}"
        ></span>
      {/each}
    {:else}
      <span class="health-seg-empty"></span>
    {/if}
  </div>

  <div class="card-footer">
    <span class="footer-stat">{queue.totalTasks} visible</span>
    {#if queue.queueWaitSampleCount > 0}
      <span class="footer-stat footer-accent">{avgWait} wait</span>
    {/if}
    {#if failRate >= 10}
      <span class="fail-chip">{failRate}% failed</span>
    {:else if completedRuns > 0}
      <span class="success-rate">{successRate}% ok</span>
    {:else if queue.historicalTotalSeen > 0}
      <span class="success-rate">0 complete</span>
    {/if}
    <span class="last-seen">{lastSeen}</span>
  </div>
</button>

<style>
  .queue-card {
    width: 100%;
    text-align: left;
    background: #fff;
    border: 1px solid #e2e6eb;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    cursor: pointer;
    display: grid;
    gap: 0.5rem;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .queue-card:hover {
    border-color: #d1d5db;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  }

  .queue-card.selected {
    border-color: #2563eb;
    background: #eff6ff;
    box-shadow: 0 1px 4px rgba(37, 99, 235, 0.10);
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 0;
  }

  .status-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
    background: #c8d4de;
    transition: background 0.2s;
  }

  .status-dot.active {
    background: #16a34a;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.2);
    animation: dot-pulse 2s ease-in-out infinite;
  }

  .queue-name {
    font-weight: 600;
    font-size: 0.88rem;
    color: #111827;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .active-pill {
    flex-shrink: 0;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.14rem 0.45rem;
    border-radius: 3px;
  }

  .routing-keys {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .routing-tag {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #6b7280;
    background: #f3f4f6;
    padding: 0.1rem 0.45rem;
    border-radius: 3px;
  }

  .health-bar {
    display: flex;
    height: 5px;
    border-radius: 3px;
    overflow: hidden;
    background: #f3f4f6;
    gap: 2px;
  }

  .health-seg {
    height: 100%;
    border-radius: 2px;
    min-width: 4px;
    transition: width 0.3s ease;
  }

  .health-seg-empty {
    width: 100%;
    height: 100%;
    background: #e5e7eb;
    border-radius: 2px;
  }

  .card-footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .footer-stat {
    font-size: 0.78rem;
    color: #9ca3af;
  }

  .footer-accent {
    color: #6b7280;
  }

  .success-rate {
    font-size: 0.78rem;
    color: #15803d;
    font-weight: 600;
    margin-left: auto;
  }

  .fail-chip {
    font-size: 0.78rem;
    font-weight: 600;
    color: #b91c1c;
    background: #fef2f2;
    padding: 0.08rem 0.35rem;
    border-radius: 3px;
    margin-left: auto;
  }

  .last-seen {
    font-size: 0.78rem;
    color: #9ca3af;
    flex-shrink: 0;
  }
</style>

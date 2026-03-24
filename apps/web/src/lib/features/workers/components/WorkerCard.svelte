<script lang="ts">
  import type { WorkerSummary } from '$lib/core/contracts/monitor';
  import {
    formatLastHeartbeat,
    formatRelativeTime,
    formatWorkerSystem,
    toneForWorkerState
  } from '$lib/features/workers/workers-domain';

  interface Props {
    worker: WorkerSummary;
    selected: boolean;
    onSelect: () => void;
  }

  const { worker, selected, onSelect }: Props = $props();

  const tone = $derived(toneForWorkerState(worker.state));
  const lastSeen = $derived(formatRelativeTime(worker.lastSeenAt));
  const lastHeartbeat = $derived(formatLastHeartbeat(worker));
  const system = $derived(formatWorkerSystem(worker));
</script>

<button type="button" class="worker-card" class:selected onclick={onSelect} aria-pressed={selected}>
  <div class="card-header">
    <span class={`status-dot tone-${tone}`}></span>
    <div class="identity">
      <strong>{worker.hostname}</strong>
      <small>{system}</small>
    </div>
    <span class={`state-pill tone-${tone}`}>{worker.state}</span>
  </div>

  <div class="card-stats">
    <span>{worker.active ?? 0} active</span>
    <span>{worker.processed ?? 0} processed</span>
  </div>

  <div class="card-footer">
    <span>{lastHeartbeat}</span>
    <span>{lastSeen}</span>
  </div>
</button>

<style>
  .worker-card {
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

  .worker-card:hover {
    border-color: #d1d5db;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  }

  .worker-card.selected {
    border-color: #2563eb;
    background: #eff6ff;
    box-shadow: 0 1px 4px rgba(37, 99, 235, 0.10);
  }

  .card-header,
  .card-stats,
  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .identity {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
    flex: 1;
  }

  .identity strong,
  .identity small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .identity small,
  .card-stats span,
  .card-footer span {
    color: #6b7280;
    font-size: 0.78rem;
  }

  .status-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 999px;
    flex-shrink: 0;
  }

  .state-pill {
    padding: 0.14rem 0.4rem;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: #f3f4f6;
    color: #6b7280;
  }

  .tone-online {
    background: #f0fdf4;
    color: #15803d;
  }

  .status-dot.tone-online {
    background: #16a34a;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
  }

  .tone-stale {
    background: #fffbeb;
    color: #b45309;
  }

  .status-dot.tone-stale {
    background: #d97706;
    box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.14);
  }

  .tone-offline {
    background: #fef2f2;
    color: #b91c1c;
  }

  .status-dot.tone-offline {
    background: #dc2626;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.14);
  }
 </style>

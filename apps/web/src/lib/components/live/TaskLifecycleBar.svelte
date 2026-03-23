<script lang="ts">
  import type { TaskState } from '$lib/core/contracts/monitor';

  export let state: TaskState;
  export let retries = 0;
  export let startedAt: string | null = null;
  export let finishedAt: string | null = null;

  function formatDuration(start: string | null, end: string | null): string | null {
    if (start === null) return null;
    const t0 = new Date(start).getTime();
    if (!Number.isFinite(t0)) return null;
    const t1 = end !== null ? new Date(end).getTime() : Date.now();
    if (!Number.isFinite(t1)) return null;
    const ms = t1 - t0;
    if (ms < 0) return null;
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${(ms / 1000).toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = s % 60;
    if (m < 60) return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
  }

  $: duration = formatDuration(startedAt, finishedAt);

  // When retries > 0, give more informative labels so users know this is a retry attempt.
  $: barText = (() => {
    if (state === 'started' && retries > 0) return `Retry #${retries}`;
    if (state === 'retrying') return 'Retry queued';
    return labelByState[state];
  })();

  $: attemptLabel = retries > 0 ? `Attempt ${retries + 1}` : null;

  const progressByState: Record<TaskState, number> = {
    sent: 12,
    received: 40,
    started: 72,
    retrying: 82,
    succeeded: 100,
    failed: 100,
    lost: 100
  };

  const toneByState: Record<TaskState, string> = {
    sent: '#9ca3af',
    received: '#2563eb',
    started: '#0284c7',
    retrying: '#d97706',
    succeeded: '#16a34a',
    failed: '#dc2626',
    lost: '#b91c1c'
  };

  const labelByState: Record<TaskState, string> = {
    sent: 'Queued',
    received: 'Received',
    started: 'Running',
    retrying: 'Retrying',
    succeeded: 'Done',
    failed: 'Failed',
    lost: 'Lost'
  };

  const isLive = (s: TaskState): boolean => s !== 'succeeded' && s !== 'failed' && s !== 'lost';
  const isRetrying = (s: TaskState): boolean => s === 'retrying';
</script>

<div class="lc-bar" aria-label={`Task state: ${state}`}>
  <div class="bar-track">
    <div
      class="bar-fill"
      class:live={isLive(state)}
      class:retrying={isRetrying(state)}
      style="width:{progressByState[state]}%; --tone:{toneByState[state]};"
    >
      <span class="bar-text">{barText}</span>
    </div>
  </div>
  <div class="bar-meta">
    <span class="state-label" style="color:{toneByState[state]};">{barText}</span>
    {#if attemptLabel !== null}
      <span class="attempt-badge">{attemptLabel}</span>
    {/if}
    {#if duration !== null}
      <span class="duration-badge">{duration}</span>
    {/if}
    <span class="state-pill" style="border-color:{toneByState[state]}; color:{toneByState[state]};">{state}</span>
  </div>
</div>

<style>
  .lc-bar {
    display: grid;
    gap: 0.4rem;
  }

  .bar-track {
    position: relative;
    height: 1.4rem;
    background: #f3f4f6;
    border-radius: 4px;
    overflow: hidden;
  }

  .bar-fill {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    min-width: 4.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--tone);
    border-radius: 4px;
    transition:
      width 220ms ease,
      background-color 220ms ease;
  }

  .bar-fill.live {
    overflow: hidden;
    animation: livePulse 1.8s ease-in-out infinite;
  }

  .bar-fill.live::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      color-mix(in srgb, white 28%, transparent) 45%,
      transparent 100%
    );
    transform: translateX(-100%);
    animation: sweep 1.7s linear infinite;
  }

  .bar-fill.retrying {
    animation: retryPulse 1.15s ease-in-out infinite;
  }

  .bar-text {
    position: relative;
    z-index: 1;
    font-size: 0.72rem;
    font-weight: 700;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
    pointer-events: none;
  }

  .bar-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .state-label {
    font-size: 0.78rem;
    font-weight: 600;
  }

  .attempt-badge {
    font-size: 0.72rem;
    font-weight: 600;
    color: #b45309;
    background: #fffbeb;
    border: 1px solid #fde68a;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  .duration-badge {
    font-size: 0.72rem;
    font-weight: 600;
    color: #374151;
    padding: 0.1rem 0.4rem;
    background: #f3f4f6;
    border-radius: 3px;
  }

  .state-pill {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.12rem 0.42rem;
    border: 1px solid;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: #fff;
    margin-left: auto;
  }

  @keyframes livePulse {
    0%, 100% { opacity: 0.9; }
    50% { opacity: 1; }
  }

  @keyframes retryPulse {
    0%, 100% { opacity: 0.84; }
    50% { opacity: 1; }
  }

  @keyframes sweep {
    from { transform: translateX(-100%); }
    to { transform: translateX(150%); }
  }
</style>

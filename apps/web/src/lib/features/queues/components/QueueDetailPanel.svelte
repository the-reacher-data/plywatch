<script lang="ts">
  import type { QueueSummary, TaskSummary } from '$lib/core/contracts/monitor';
  import {
    buildQueueSlices,
    buildQueueTimeline,
    completedFailureRate,
    completedSuccessRate,
    completedTotal,
    formatDurationMs,
    percentOf,
  } from '../queues-domain';

  interface Props {
    queue: QueueSummary;
    tasks: TaskSummary[];
    queueHref: string;
    loading?: boolean;
  }

  let { queue, tasks, queueHref, loading = false }: Props = $props();

  const slices = $derived(buildQueueSlices(queue, tasks));
  const currentSlices = $derived(slices.filter((s) => s.section === 'current'));
  const retainedSlices = $derived(slices.filter((s) => s.section === 'retained'));
  const timeline = $derived(buildQueueTimeline(tasks));
  const maxTimelineTotal = $derived(Math.max(...timeline.map((b) => b.total), 1));

  const completedCount = $derived(completedTotal(queue));
  const successRate = $derived(completedSuccessRate(queue));
  const failureRate = $derived(completedFailureRate(queue));
  const currentTotal = $derived(queue.sentCount + queue.activeCount + queue.retryingCount);
  const retainedTotal = $derived(queue.succeededCount + queue.failedCount);
  const avgQueueWait = $derived(formatDurationMs(queue.avgQueueWaitMs));
  const avgStartDelay = $derived(formatDurationMs(queue.avgStartDelayMs));
  const avgRunDuration = $derived(formatDurationMs(queue.avgRunDurationMs));
  const avgEndToEnd = $derived(formatDurationMs(queue.avgEndToEndMs));
  const isRefreshing = $derived(loading && tasks.length > 0);
</script>

<article class="detail-panel" aria-label="Queue detail: {queue.name}">
  <header class="detail-header">
    <div class="detail-title">
      <h3>{queue.name}</h3>
      <p>{queue.historicalTotalSeen} historical · {queue.totalTasks} visible now · {queue.routingKeys.length} routing keys</p>
    </div>
    <div class="detail-actions">
      {#if isRefreshing}
        <span class="refresh-pill" role="status">Live sample refreshing</span>
      {/if}
      <a class="open-tasks-link" href={queueHref}>Open tasks →</a>
    </div>
  </header>

  <!-- KPI strip -->
  <div class="kpi-strip">
    <div class="kpi-card kpi-active">
      <span class="kpi-label">In flight</span>
      <strong class="kpi-value">{queue.activeCount}</strong>
      <span class="kpi-sub">{queue.sentCount} queued · {queue.retryingCount} retrying</span>
    </div>
    <div class="kpi-card kpi-success">
      <span class="kpi-label">Completed success rate</span>
      <strong class="kpi-value">{successRate}%</strong>
      <span class="kpi-sub">{queue.historicalSucceededCount} of {completedCount} completed</span>
    </div>
    <div class="kpi-card kpi-danger">
      <span class="kpi-label">Observed total</span>
      <strong class="kpi-value">{queue.historicalTotalSeen}</strong>
      <span class="kpi-sub">{queue.historicalFailedCount} failed · {failureRate}% of completed</span>
    </div>
  </div>

  {#if completedCount === 0 && queue.historicalTotalSeen > 0}
    <p class="queue-note">
      No terminal runs observed yet. Success and failure rates only use completed executions.
    </p>
  {/if}

  <section class="timing-section">
    <div class="section-head">
      <h4 class="section-title">Observed timings</h4>
      <span class="section-note">Incremental projection</span>
    </div>

    <div class="timing-grid">
      <div class="timing-card timing-queue">
        <span class="timing-label">Avg queue wait</span>
        <strong class="timing-value">{avgQueueWait}</strong>
        <span class="timing-sub">{queue.queueWaitSampleCount} samples · sent → received</span>
      </div>
      <div class="timing-card timing-start">
        <span class="timing-label">Avg start delay</span>
        <strong class="timing-value">{avgStartDelay}</strong>
        <span class="timing-sub">{queue.startDelaySampleCount} samples · received → started</span>
      </div>
      <div class="timing-card timing-run">
        <span class="timing-label">Avg run time</span>
        <strong class="timing-value">{avgRunDuration}</strong>
        <span class="timing-sub">{queue.runDurationSampleCount} samples · started → finished</span>
      </div>
      <div class="timing-card timing-end">
        <span class="timing-label">Avg end-to-end</span>
        <strong class="timing-value">{avgEndToEnd}</strong>
        <span class="timing-sub">{queue.endToEndSampleCount} samples · sent → finished</span>
      </div>
    </div>
  </section>

  <!-- Current state proportion bar -->
  {#if currentTotal > 0}
    <section class="prop-section">
      <h4 class="section-title">Current</h4>
      <div class="prop-bar">
        {#each currentSlices.filter((s) => s.count > 0) as slice (slice.key)}
          <span
            class="prop-seg tone-{slice.tone}"
            style="width: {percentOf(slice.count, currentTotal)}%"
            title="{slice.label}: {slice.count}"
          ></span>
        {/each}
      </div>
      <div class="prop-legend">
        {#each currentSlices as slice (slice.key)}
          <span class="prop-item">
            <i class="prop-dot tone-{slice.tone}"></i>
            <span class="prop-label">{slice.label}</span>
            <strong class="prop-count">{slice.count}</strong>
            {#if slice.count > 0}
              <span class="prop-pct">{percentOf(slice.count, currentTotal)}%</span>
            {/if}
          </span>
        {/each}
      </div>
    </section>
  {/if}

  <!-- Retained state proportion bar -->
  {#if retainedTotal > 0}
    <section class="prop-section">
      <h4 class="section-title">Retained</h4>
      <div class="prop-bar">
        {#each retainedSlices.filter((s) => s.count > 0) as slice (slice.key)}
          <span
            class="prop-seg tone-{slice.tone}"
            style="width: {percentOf(slice.count, retainedTotal)}%"
            title="{slice.label}: {slice.count}"
          ></span>
        {/each}
      </div>
      <div class="prop-legend">
        {#each retainedSlices as slice (slice.key)}
          <span class="prop-item">
            <i class="prop-dot tone-{slice.tone}"></i>
            <span class="prop-label">{slice.label}</span>
            <strong class="prop-count">{slice.count}</strong>
            {#if slice.count > 0}
              <span class="prop-pct">{percentOf(slice.count, retainedTotal)}%</span>
            {/if}
          </span>
        {/each}
      </div>
    </section>
  {/if}

  <!-- Activity timeline -->
  {#if timeline.length > 0}
    <section class="timeline-section">
      <h4 class="section-title">Activity timeline</h4>
      <div class="timeline-chart">
        {#each timeline as bucket (bucket.label)}
          <div class="tl-col" title="{bucket.label} · {bucket.total} tasks">
            <div class="tl-stack">
              {#if bucket.failed > 0}
                <span class="tl-seg tone-danger" style="height: {(bucket.failed / maxTimelineTotal) * 100}%"></span>
              {/if}
              {#if bucket.retrying > 0}
                <span class="tl-seg tone-retrying" style="height: {(bucket.retrying / maxTimelineTotal) * 100}%"></span>
              {/if}
              {#if bucket.succeeded > 0}
                <span class="tl-seg tone-success" style="height: {(bucket.succeeded / maxTimelineTotal) * 100}%"></span>
              {/if}
              {#if bucket.active > 0}
                <span class="tl-seg tone-active" style="height: {(bucket.active / maxTimelineTotal) * 100}%"></span>
              {/if}
              {#if bucket.sent > 0}
                <span class="tl-seg tone-neutral" style="height: {(bucket.sent / maxTimelineTotal) * 100}%"></span>
              {/if}
            </div>
            <span class="tl-count">{bucket.total > 0 ? bucket.total : ''}</span>
            <span class="tl-label">{bucket.label}</span>
          </div>
        {/each}
      </div>
      <div class="tl-legend">
        <span><i class="tl-dot tone-neutral"></i>queued</span>
        <span><i class="tl-dot tone-active"></i>active</span>
        <span><i class="tl-dot tone-retrying"></i>retrying</span>
        <span><i class="tl-dot tone-success"></i>ok</span>
        <span><i class="tl-dot tone-danger"></i>failed</span>
      </div>
    </section>
  {/if}

  {#if timeline.length === 0 && !loading}
    <p class="empty-hint">No observed queue activity yet.</p>
  {/if}

  {#if loading && tasks.length === 0}
    <p class="loading-hint">Refreshing queue activity sample…</p>
  {/if}
</article>

<style>
  .detail-panel {
    background: linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
    border: 1px solid #d8e0ea;
    border-radius: 1rem;
    padding: 1.25rem;
    display: grid;
    gap: 1.25rem;
    box-shadow: 0 14px 30px rgba(20, 33, 43, 0.05);
  }

  /* Header */
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .detail-actions {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .detail-title h3 {
    margin: 0;
    font-size: 1.1rem;
    color: #14212b;
  }

  .detail-title p {
    margin: 0.25rem 0 0;
    font-size: 0.78rem;
    color: #5f7184;
  }

  .open-tasks-link {
    flex-shrink: 0;
    color: #1e4f85;
    font-size: 0.82rem;
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
  }

  .open-tasks-link:hover {
    text-decoration: underline;
  }

  .refresh-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    background: #eef2f7;
    color: #526171;
    font-size: 0.72rem;
    font-weight: 600;
  }

  /* KPI strip */
  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .kpi-card {
    display: grid;
    gap: 0.2rem;
    padding: 0.85rem 1rem;
    border-radius: 0.85rem;
    border-left: 3px solid transparent;
    border: 1px solid rgba(255, 255, 255, 0.7);
  }

  .kpi-active  { background: linear-gradient(180deg, #f4f8fc 0%, #eef5fc 100%); border-left-color: #1e4f85; }
  .kpi-success { background: linear-gradient(180deg, #f2f7f4 0%, #ebf4ef 100%); border-left-color: #2f855a; }
  .kpi-danger  { background: linear-gradient(180deg, #faf2f2 0%, #f8ecec 100%); border-left-color: #c74b4b; }

  .kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #5f7184;
  }

  .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #14212b;
    line-height: 1.1;
  }

  .kpi-sub {
    font-size: 0.72rem;
    color: #7a8fa0;
  }

  .queue-note {
    margin: -0.45rem 0 0;
    font-size: 0.76rem;
    color: #64748b;
  }

  .timing-section {
    display: grid;
    gap: 0.75rem;
  }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .section-note {
    color: #7a8fa0;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .timing-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .timing-card {
    display: grid;
    gap: 0.22rem;
    padding: 0.85rem 0.95rem;
    border-radius: 0.9rem;
    border: 1px solid #e4ebf3;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
  }

  .timing-queue { background: linear-gradient(180deg, #f7fbff 0%, #eff6ff 100%); }
  .timing-start { background: linear-gradient(180deg, #f8fbff 0%, #f1f6fb 100%); }
  .timing-run { background: linear-gradient(180deg, #f4fbf7 0%, #edf7f1 100%); }
  .timing-end { background: linear-gradient(180deg, #fbf8ff 0%, #f4effd 100%); }

  .timing-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #5f7184;
  }

  .timing-value {
    font-size: 1.2rem;
    line-height: 1.1;
    color: #14212b;
  }

  .timing-sub {
    font-size: 0.72rem;
    color: #7a8fa0;
  }

  /* Proportion bars */
  .prop-section {
    display: grid;
    gap: 0.6rem;
  }

  .section-title {
    margin: 0;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #5f7184;
  }

  .prop-bar {
    display: flex;
    height: 12px;
    border-radius: 999px;
    overflow: hidden;
    background: #eef2f5;
    gap: 2px;
  }

  .prop-seg {
    height: 100%;
    border-radius: 999px;
    min-width: 6px;
    transition: width 0.35s ease;
  }

  .prop-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1.25rem;
  }

  .prop-item {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .prop-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .prop-label {
    font-size: 0.76rem;
    color: #5f7184;
  }

  .prop-count {
    font-size: 0.78rem;
    color: #14212b;
  }

  .prop-pct {
    font-size: 0.72rem;
    color: #8496a9;
  }

  /* Timeline */
  .timeline-section {
    display: grid;
    gap: 0.6rem;
  }

  .timeline-chart {
    display: grid;
    grid-template-columns: repeat(8, minmax(0, 1fr));
    gap: 0.5rem;
    align-items: end;
    min-height: 9rem;
    padding: 0.85rem;
    background: #fbfdff;
    border: 1px solid #e8eef5;
    border-radius: 0.85rem;
  }

  .tl-col {
    display: grid;
    gap: 0.3rem;
    justify-items: center;
  }

  .tl-stack {
    width: 100%;
    min-height: 6rem;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    gap: 2px;
  }

  .tl-seg {
    display: block;
    width: 100%;
    border-radius: 0.3rem;
    min-height: 3px;
    transition: height 0.2s ease;
  }

  .tl-count {
    font-size: 0.72rem;
    font-weight: 700;
    color: #14212b;
  }

  .tl-label {
    font-size: 0.65rem;
    color: #8496a9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .tl-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
  }

  .tl-legend span {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    color: #5f7184;
  }

  .tl-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* Recent activity */
  .activity-section {
    display: grid;
    gap: 0.6rem;
  }

  .activity-list {
    display: grid;
    gap: 0.45rem;
  }

  .activity-row {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    gap: 0.55rem;
    padding: 0.5rem 0.65rem;
    background: #f9fbfd;
    border-radius: 0.55rem;
    border: 1px solid #eef3f7;
  }

  .activity-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .activity-name {
    font-size: 0.8rem;
    font-weight: 600;
    color: #14212b;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .state-badge {
    font-size: 0.67rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
  }

  .activity-time {
    font-size: 0.68rem;
    color: #8496a9;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .empty-hint,
  .loading-hint {
    margin: 0;
    font-size: 0.82rem;
    color: #8496a9;
    text-align: center;
    padding: 1rem 0;
  }

  .loading-hint {
    padding: 0.85rem 1rem;
    border: 1px dashed #d8e0ea;
    border-radius: 0.8rem;
    background: #f9fbfd;
    color: #6f8192;
  }

  @media (max-width: 640px) {
    .kpi-strip {
      grid-template-columns: 1fr;
    }

    .timing-grid {
      grid-template-columns: 1fr;
    }

    .timeline-chart {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .activity-row {
      grid-template-columns: auto 1fr auto;
    }

    .activity-time {
      display: none;
    }
  }

  /* Tone colors — dynamic class names are not statically detectable by Tailwind
     so we define them locally as a fallback. */
  :global(.tone-neutral)      { background-color: #8496a9; }
  :global(.tone-active)       { background-color: #1e4f85; }
  :global(.tone-retrying)     { background-color: #d08a1f; }
  :global(.tone-success)      { background-color: #2f855a; }
  :global(.tone-danger)       { background-color: #c74b4b; }
  :global(.tone-badge-neutral)  { background: #eef2f5; color: #5f7184; }
  :global(.tone-badge-active)   { background: #eaf3ff; color: #1e4f85; }
  :global(.tone-badge-retrying) { background: #fdf4e7; color: #9e7031; }
  :global(.tone-badge-success)  { background: #edf7f1; color: #276749; }
  :global(.tone-badge-danger)   { background: #fdf0f0; color: #9b2b2b; }
</style>

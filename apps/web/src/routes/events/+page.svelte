<script lang="ts">
  import { untrack } from 'svelte';
  import { page } from '$app/state';
  import EventPopover from '$lib/components/live/EventPopover.svelte';

  import { HttpMonitorClient } from '$lib/core/adapters/http-monitor-client';
  import { monitorApiUrl } from '$lib/core/config';
  import type { RawEvent } from '$lib/core/contracts/monitor';
  import { createEventsStore } from '$lib/features/events/events-store';
  import {
    buildEventGroups,
    buildWorkerLanes,
    categorizeEvent,
    colorForEvent,
    eventKey,
    isTaskEvent,
    labelForEvent,
    previewPayload,
  } from '$lib/features/events/events-domain';

  const client = new HttpMonitorClient(monitorApiUrl);
  const events = createEventsStore(client);

  let selectedEventTypes = $state<string[]>([]);
  let highlightedEventKey = $state<string | null>(null);

  // --- filter helpers ---

  const allEventGroups = $derived(buildEventGroups($events.items));

  const isFiltered = $derived(selectedEventTypes.length > 0);

  const visibleEvents = $derived(
    isFiltered
      ? $events.items.filter((e) => selectedEventTypes.includes(e.eventType))
      : $events.items,
  );

  // Pass all raw items so buildWorkerLanes can derive status + heartbeat counts correctly.
  const workerLanes = $derived(buildWorkerLanes(visibleEvents, $events.items));

  function toggleType(eventType: string): void {
    if (selectedEventTypes.includes(eventType)) {
      selectedEventTypes = selectedEventTypes.filter((t) => t !== eventType);
      return;
    }
    selectedEventTypes = [...selectedEventTypes, eventType];
  }

  function showAll(): void {
    selectedEventTypes = [];
  }

  function selectTaskOnly(): void {
    selectedEventTypes = allEventGroups
      .map((g) => g.eventType)
      .filter((t) => isTaskEvent(t));
  }

  function selectWorkerOnly(): void {
    selectedEventTypes = allEventGroups
      .map((g) => g.eventType)
      .filter((t) => {
        const category = categorizeEvent(t);
        return category === 'worker' || category === 'control';
      });
  }

  // --- timeline interaction ---

  function focusEvent(event: RawEvent): void {
    const key = eventKey(event);
    highlightedEventKey = key;
    globalThis.document?.getElementById(`event-${key}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    });
  }

  function popoverLines(event: RawEvent): string[] {
    return [
      `Type: ${event.eventType}`,
      `Captured: ${event.capturedAt}`,
      `Task: ${event.uuid ?? '-'}`,
      `Worker: ${event.hostname ?? '-'}`,
    ];
  }

  // --- lifecycle ---

  // One-time URL param init: fully untracked so neither `page` nor
  // `allEventGroups` (read inside selectXOnly) become effect dependencies.
  $effect(() => {
    untrack(() => {
      const track = page.url.searchParams.get('track');
      if (track === 'worker') selectWorkerOnly();
      else if (track === 'task') selectTaskOnly();
    });
  });

  // SSE lifecycle: no reactive reads → runs once on mount, cleans up on destroy.
  $effect(() => {
    void events.refresh();
    events.connect();
    return () => events.disconnect();
  });
</script>

<section class="events-shell">
  <header class="page-header">
    <h2>Celery Events</h2>
    <p>Live stream of raw Celery events. Filter by type to focus, then inspect the timeline and event list below.</p>
  </header>

  {#if $events.error !== null}
    <div class="error-banner" role="alert">{$events.error}</div>
  {/if}

  <!-- Event type filter -->
  <article class="card">
    <header class="card-header">
      <div>
        <h3>Event types</h3>
        <p>Click to select what you want to see. Multiple selection allowed — empty shows all.</p>
      </div>
      <div class="filter-actions">
        <button type="button" class="ghost-btn" class:active={!isFiltered} onclick={showAll}>
          All
        </button>
        <button type="button" class="ghost-btn" onclick={selectTaskOnly}>Tasks</button>
        <button type="button" class="ghost-btn" onclick={selectWorkerOnly}>Workers</button>
      </div>
    </header>

    <div class="pill-list">
      {#each allEventGroups as group (group.eventType)}
        {@const isSelected = selectedEventTypes.includes(group.eventType)}
        <button
          type="button"
          class="type-pill"
          class:selected={isSelected}
          class:dimmed={isFiltered && !isSelected}
          onclick={() => toggleType(group.eventType)}
          aria-pressed={isSelected}
        >
          <i style="background: {group.color}"></i>
          <span>{labelForEvent(group.eventType)}</span>
          <small class={`pill-category category-${group.category}`}>{group.category}</small>
          <strong>{group.count}</strong>
        </button>
      {/each}
    </div>
  </article>

  <!-- Per-worker swimlane timeline -->
  <article class="card">
    <header class="card-header">
      <div>
        <h3>Timeline</h3>
        <p>One lane per worker. Hover any event node for details, click to pin.</p>
      </div>
      <div class="timeline-actions">
        <button
          type="button"
          class="pause-btn"
          class:paused={$events.paused}
          onclick={() => ($events.paused ? events.resume() : events.pause())}
          title={$events.paused ? 'Resume live updates' : 'Pause live updates'}
        >
          {$events.paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <span class="count-pill">{visibleEvents.length} visible / {$events.count} buffered</span>
      </div>
    </header>

    {#if workerLanes.length > 0}
      <div class="swimlanes">
        {#each workerLanes as lane (lane.hostname)}
          <section class="lane">
            <div class="lane-header">
              <span class="lane-status-dot status-{lane.status}"></span>
              <span class="lane-name" title={lane.hostname}>{lane.displayName}</span>
              <div class="lane-groups">
                {#each lane.groups.slice(0, 4) as group (group.eventType)}
                  <span class="lane-group-pill" style="--dot: {group.color}">
                    {group.count}
                  </span>
                {/each}
              </div>
              {#if lane.heartbeatCount > 0}
                <span class="lane-hb" title="worker-heartbeat events in this lane"
                  >♡ {lane.heartbeatCount}</span
                >
              {/if}
              <span class="lane-total">{lane.events.length}</span>
            </div>

            <div class="lane-track" class:single={lane.events.length === 1}>
              {#each lane.events as event, idx (`${idx}:${eventKey(event)}`)}
                <EventPopover
                  title={labelForEvent(event.eventType)}
                  lines={popoverLines(event)}
                >
                  {#snippet trigger(props)}
                    <button
                      {...props}
                      type="button"
                      class="event-node"
                      style="background: {colorForEvent(event.eventType)}"
                      title="{event.eventType} · {event.capturedAt}"
                      aria-label="{event.eventType} at {event.capturedAt}"
                    ></button>
                  {/snippet}
                  {#snippet footer()}
                    <button
                      type="button"
                      class="popover-jump"
                      onclick={() => focusEvent(event)}
                    >
                      Jump to event
                    </button>
                  {/snippet}
                </EventPopover>
              {/each}
            </div>
          </section>
        {/each}
      </div>
    {:else if !$events.loading}
      <p class="empty-hint">No events match the current filter.</p>
    {/if}
  </article>

  <!-- Event list -->
  <article class="card">
    <header class="card-header">
      <div>
        <h3>Event list</h3>
        <p>Chronological. Task and worker events stay mixed to preserve the real sequence.</p>
      </div>
    </header>

    <div class="event-list">
      {#each visibleEvents as event, idx (`${idx}:${eventKey(event)}`)}
        {@const key = eventKey(event)}
        <section
          id="event-{key}"
          class="event-row"
          class:highlighted={highlightedEventKey === key}
        >
          <div class="event-head">
            <span
              class="event-type-badge"
              style="border-color: {colorForEvent(event.eventType)}; color: {colorForEvent(event.eventType)}"
            >
              {event.eventType}
            </span>
            <time>{event.capturedAt}</time>
          </div>

          <dl class="event-meta">
            <div>
              <dt>Track</dt>
              <dd>{categorizeEvent(event.eventType)}</dd>
            </div>
            <div>
              <dt>Task</dt>
              <dd>{event.uuid ?? '-'}</dd>
            </div>
            <div>
              <dt>Worker</dt>
              <dd>{event.hostname ?? '-'}</dd>
            </div>
          </dl>

          <pre>{previewPayload(event)}</pre>
        </section>
      {/each}

      {#if visibleEvents.length === 0 && !$events.loading}
        <p class="empty-hint">No events match the current filter.</p>
      {/if}
    </div>
  </article>
</section>

<style>
  .events-shell {
    display: grid;
    gap: 1rem;
  }

  .page-header h2 {
    margin: 0;
  }

  .page-header p {
    margin: 0.3rem 0 0;
    color: #5f7184;
    font-size: 0.88rem;
  }

  .error-banner {
    padding: 0.75rem 1rem;
    background: #fdf0f0;
    border: 1px solid #f0c0c0;
    border-radius: 0.65rem;
    color: #9b2b2b;
    font-size: 0.84rem;
  }

  /* Card shell */
  .card {
    padding: 1.15rem 1.25rem;
    border: 1px solid #d8e0ea;
    border-radius: 1rem;
    background: #fff;
    box-shadow: 0 10px 24px rgba(20, 33, 43, 0.04);
    display: grid;
    gap: 1rem;
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .card-header h3 {
    margin: 0;
  }

  .card-header p {
    margin: 0.25rem 0 0;
    color: #5f7184;
    font-size: 0.82rem;
  }

  .timeline-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .pause-btn {
    padding: 0.35rem 0.75rem;
    border: 1px solid #d8e0ea;
    border-radius: 999px;
    background: #fff;
    color: #1e4f85;
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }

  .pause-btn:hover {
    background: #f0f6ff;
    border-color: #a8c0d8;
  }

  .pause-btn.paused {
    background: #fffbeb;
    border-color: #fde68a;
    color: #92400e;
  }

  .count-pill {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    background: #eef4fb;
    color: #1e4f85;
    font-size: 0.78rem;
    font-weight: 700;
  }

  /* Filter actions */
  .filter-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .ghost-btn {
    padding: 0.38rem 0.75rem;
    border: 1px solid #d8e0ea;
    border-radius: 999px;
    background: #fff;
    color: #1e4f85;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }

  .ghost-btn:hover {
    background: #f0f6ff;
    border-color: #a8c0d8;
  }

  .ghost-btn.active {
    background: #eaf3ff;
    border-color: #1e4f85;
  }

  /* Type pills — opt-in filter model */
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .type-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.45rem 0.8rem;
    border: 1px solid #d8e0ea;
    border-radius: 999px;
    background: #f8fbff;
    color: #14212b;
    font-size: 0.82rem;
    cursor: pointer;
    transition: opacity 0.15s, border-color 0.15s, background 0.15s;
  }

  .type-pill:hover {
    border-color: #a8c0d8;
    background: #f0f6ff;
  }

  /* Selected: visually prominent */
  .type-pill.selected {
    border-color: #1e4f85;
    background: #eaf3ff;
    font-weight: 700;
  }

  /* Dimmed: not selected while filter is active */
  .type-pill.dimmed {
    opacity: 0.38;
  }

  .type-pill i {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .type-pill strong {
    font-size: 0.78rem;
    color: #5f7184;
  }

  .pill-category {
    padding: 0.08rem 0.35rem;
    border-radius: 999px;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .category-task {
    background: #eaf3ff;
    color: #1e4f85;
  }

  .category-worker {
    background: #edf7f1;
    color: #276749;
  }

  .category-control {
    background: #f3f0fb;
    color: #6b5ca5;
  }

  .category-other {
    background: #eef2f5;
    color: #5f7184;
  }

  .type-pill.selected strong {
    color: #1e4f85;
  }

  /* Swimlanes */
  .swimlanes {
    display: grid;
    gap: 0.65rem;
  }

  .lane {
    border: 1px solid #e7edf4;
    border-radius: 0.85rem;
    background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
    overflow: hidden;
  }

  .lane-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.65rem 0.9rem;
    border-bottom: 1px solid #eef3f8;
    background: #f9fbfd;
  }

  .lane-status-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-online  { background: #2f855a; box-shadow: 0 0 0 2px rgba(47,133,90,0.2); }
  .status-offline { background: #c74b4b; }
  .status-unknown { background: #c8d4de; }

  .lane-name {
    font-size: 0.82rem;
    font-weight: 700;
    color: #14212b;
    font-family: 'IBM Plex Mono', monospace;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lane-groups {
    display: flex;
    gap: 0.35rem;
  }

  .lane-group-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.7rem;
    font-weight: 700;
    color: #5f7184;
    padding: 0.12rem 0.45rem;
    border-radius: 999px;
    background: #eef2f5;
  }

  .lane-group-pill::before {
    content: '';
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: var(--dot);
    flex-shrink: 0;
  }

  .lane-hb {
    font-size: 0.72rem;
    font-weight: 600;
    color: #a8bac8;
    flex-shrink: 0;
    white-space: nowrap;
  }

  .lane-total {
    font-size: 0.75rem;
    font-weight: 700;
    color: #8496a9;
    flex-shrink: 0;
    min-width: 1.5rem;
    text-align: right;
  }

  .lane-track {
    padding: 0.75rem 0.9rem;
    min-height: 3rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
  }

  .lane-track.single .event-node {
    width: 100%;
    height: 0.85rem;
    border-radius: 999px;
  }

  .event-node {
    width: 0.9rem;
    height: 0.9rem;
    border: 0;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 0 0 2px #fff;
    transition: transform 0.1s, box-shadow 0.1s;
  }

  .event-node:hover {
    transform: scale(1.25);
    box-shadow: 0 0 0 2px #fff, 0 0 0 4px rgba(30,79,133,0.15);
  }

  /* Event list */
  .event-list {
    display: grid;
    gap: 0.75rem;
  }

  .event-row {
    padding: 0.9rem 1rem;
    border: 1px solid #e3eaf1;
    border-radius: 0.85rem;
    background: #fbfdff;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .event-row.highlighted {
    border-color: #1e4f85;
    box-shadow: 0 0 0 3px rgba(30, 79, 133, 0.08);
  }

  .event-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .event-type-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.55rem;
    border: 1px solid currentColor;
    border-radius: 999px;
    font-size: 0.77rem;
    font-weight: 700;
  }

  time {
    font-size: 0.78rem;
    color: #5f7184;
    flex-shrink: 0;
  }

  .event-meta {
    margin: 0.8rem 0 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .event-meta dt {
    margin: 0 0 0.2rem;
    font-size: 0.72rem;
    color: #5f7184;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .event-meta dd {
    margin: 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  pre {
    margin: 0.8rem 0 0;
    padding: 0.85rem;
    border-radius: 0.75rem;
    background: #14212b;
    color: #f4f7fb;
    font-size: 0.76rem;
    overflow-x: auto;
  }

  .popover-jump {
    border: 0;
    background: transparent;
    padding: 0;
    color: #345978;
    font-size: 0.76rem;
    font-weight: 700;
    cursor: pointer;
  }

  .empty-hint {
    margin: 0;
    padding: 1rem 0;
    font-size: 0.84rem;
    color: #8496a9;
    text-align: center;
  }

  @media (max-width: 720px) {
    .card-header,
    .event-head {
      flex-direction: column;
      align-items: flex-start;
    }

    .event-meta {
      grid-template-columns: 1fr;
    }
  }
</style>

<script lang="ts">
  import type { ScheduleSummary, TaskSummary } from '$lib/core/contracts/monitor';
  import { formatTaskRuntime } from '$lib/features/tasks/components/task-family-list-view';
  import {
    formatObservedAt,
    isFutureScheduledRun,
    isScheduleSectionOpenByDefault,
    lastActivityLabel,
    scheduleSectionId,
    scheduleRunDisplayName,
    scheduleRunLabel,
    scheduleRunRuntimeLabel,
    scheduleRunTimingLabel,
    scheduleRunTone,
    scheduleCountLabel,
    scheduleStatusSummary,
    timelineRuns,
  } from '$lib/features/tasks/components/scheduled-run-list-view';

  interface Props {
    schedules: ScheduleSummary[];
    selectedTaskId: string | null;
    onSelect: (taskId: string) => void;
    selectionEnabled?: boolean;
    selectedScheduleIds?: Set<string>;
    onToggleScheduleSelection?: (scheduleId: string, selected: boolean) => void;
    expandedScheduleIds: Set<string>;
    onToggleExpanded: (scheduleId: string, nextExpanded: boolean) => void;
    nowMs?: number;
  }

  const {
    schedules,
    selectedTaskId,
    onSelect,
    selectionEnabled = false,
    selectedScheduleIds = new Set<string>(),
    onToggleScheduleSelection,
    expandedScheduleIds,
    onToggleExpanded,
    nowMs = Date.now(),
  }: Props = $props();

  const isExpanded = (scheduleId: string): boolean => expandedScheduleIds.has(scheduleId);
  const toggle = (scheduleId: string): void => onToggleExpanded(scheduleId, !isExpanded(scheduleId));

  const timelineRunsFor = (schedule: ScheduleSummary): TaskSummary[] => timelineRuns(schedule);
  const pendingRunsFor = (schedule: ScheduleSummary): TaskSummary[] => schedule.pendingRunItems;
  const lastActivity = (schedule: ScheduleSummary): string => lastActivityLabel(schedule, nowMs);
  const runLabel = (run: TaskSummary): string => scheduleRunLabel(run, nowMs);
  const runDisplayName = (run: TaskSummary): string => scheduleRunDisplayName(run);
  const runTone = (run: TaskSummary): string => scheduleRunTone(run, nowMs);
  const runRuntime = (run: TaskSummary): string => scheduleRunRuntimeLabel(run, formatTaskRuntime, nowMs);
  const runTiming = (run: TaskSummary): string => scheduleRunTimingLabel(run, nowMs);
  const runWhen = (run: TaskSummary): string =>
    isFutureScheduledRun(run, nowMs)
      ? formatObservedAt(run.scheduledFor)
      : formatObservedAt(run.lastSeenAt ?? run.scheduledFor);
  const observedRunCount = (schedule: ScheduleSummary): number => schedule.totalRuns - schedule.pendingRuns;
  const statusSummary = (schedule: ScheduleSummary) => scheduleStatusSummary(schedule);

  let toggledSections = $state(new Set<string>());

  const sectionOpen = (scheduleId: string, section: 'pending' | 'observed'): boolean => {
    const sectionId = scheduleSectionId(scheduleId, section);
    const defaultOpen = isScheduleSectionOpenByDefault(section);
    return toggledSections.has(sectionId) ? !defaultOpen : defaultOpen;
  };

  const toggleSection = (scheduleId: string, section: 'pending' | 'observed'): void => {
    const sectionId = scheduleSectionId(scheduleId, section);
    const next = new Set(toggledSections);
    if (next.has(sectionId)) {
      next.delete(sectionId);
    } else {
      next.add(sectionId);
    }
    toggledSections = next;
  };
</script>

<div class="schedule-list">
  {#each schedules as schedule (schedule.scheduleId)}
    <section class="schedule-entry" data-schedule-id={schedule.scheduleId}>
      <button
        class="schedule-row"
        type="button"
        aria-expanded={isExpanded(schedule.scheduleId)}
        onclick={() => toggle(schedule.scheduleId)}
      >
        <label class="schedule-select">
          {#if selectionEnabled}
            <input
              type="checkbox"
              checked={selectedScheduleIds.has(schedule.scheduleId)}
              onchange={(event) => {
                event.stopPropagation();
                onToggleScheduleSelection?.(
                  schedule.scheduleId,
                  (event.currentTarget as HTMLInputElement).checked,
                );
              }}
              onclick={(event) => event.stopPropagation()}
            />
          {/if}
        </label>
        <div class="schedule-main">
          <div class="schedule-title-row">
            <span class="schedule-name">{schedule.scheduleName}</span>
            {#if schedule.schedulePattern !== null}
              <span class="schedule-pattern">{schedule.schedulePattern}</span>
            {/if}
            {#if schedule.queue !== null}
            <span class="schedule-queue">{schedule.queue}</span>
          {/if}
        </div>
        <div class="schedule-subtitle">
          <span>{scheduleCountLabel(schedule)}</span>
          <span>Last activity {lastActivity(schedule)}</span>
        </div>
      </div>

        <div class="schedule-stats">
          {#if statusSummary(schedule).length > 0}
            <div class="schedule-statusline" aria-label={`Status summary for ${schedule.scheduleName}`}>
              {#each statusSummary(schedule) as stat, index (stat.key)}
                {#if index > 0}
                  <span class="schedule-status-sep" aria-hidden="true">·</span>
                {/if}
                <span class="schedule-status schedule-status-{stat.tone}">{stat.label}</span>
              {/each}
            </div>
          {/if}
          <span class="schedule-chevron" aria-hidden="true">{isExpanded(schedule.scheduleId) ? '▾' : '▸'}</span>
        </div>
      </button>

      <div class="schedule-strip">
        <div class="schedule-strip-line" aria-hidden="true"></div>
        <div class="schedule-strip-runs" aria-label={`Recent runs for ${schedule.scheduleName}`}>
          {#each timelineRunsFor(schedule) as run (run.id)}
            <button
              class="timeline-node"
              class:is-selected={selectedTaskId === run.id}
              type="button"
              aria-label={`Open scheduled run ${runDisplayName(run)}`}
              title={`${runDisplayName(run)} · ${runLabel(run)}`}
              onclick={() => onSelect(run.id)}
            >
              <span class="timeline-node-dot tone-{runTone(run)}"></span>
            </button>
          {/each}
        </div>
      </div>

      {#if isExpanded(schedule.scheduleId)}
        {#if pendingRunsFor(schedule).length > 0}
          <div class="run-group">
            <button
              class="run-group-toggle"
              type="button"
              aria-expanded={sectionOpen(schedule.scheduleId, 'pending')}
              onclick={() => toggleSection(schedule.scheduleId, 'pending')}
            >
              <span class="run-group-label">Pending</span>
              <span class="run-group-count">{pendingRunsFor(schedule).length}</span>
              <span class="run-group-chevron" aria-hidden="true">
                {sectionOpen(schedule.scheduleId, 'pending') ? '▾' : '▸'}
              </span>
            </button>
            {#if sectionOpen(schedule.scheduleId, 'pending')}
              <div class="run-list">
                {#each pendingRunsFor(schedule) as run (run.id)}
                  <button
                    class="run-row pending-row"
                    class:is-selected={selectedTaskId === run.id}
                    type="button"
                    onclick={() => onSelect(run.id)}
                  >
                    <span class="run-rail" aria-hidden="true"></span>
                    <span class="run-head">
                      <i class="run-dot tone-{runTone(run)}"></i>
                      <span class="run-name">{runDisplayName(run)}</span>
                      <span class="run-badge">scheduled</span>
                    </span>
                    <span class="run-meta run-state run-state-{runTone(run)}">{runLabel(run)}</span>
                    <span class="run-meta">{runRuntime(run)}</span>
                    <span class="run-meta">{runTiming(run)}</span>
                    <span class="run-meta run-timepoint">{runWhen(run)}</span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        {#if schedule.recentRuns.length > 0}
          <div class="run-group">
            <button
              class="run-group-toggle"
              type="button"
              aria-expanded={sectionOpen(schedule.scheduleId, 'observed')}
              onclick={() => toggleSection(schedule.scheduleId, 'observed')}
            >
              <span class="run-group-label">Recent observed runs</span>
              <span class="run-group-count">{schedule.recentRuns.length}</span>
              <span class="run-group-note">{schedule.recentRuns.length} of {observedRunCount(schedule)}</span>
              <span class="run-group-chevron" aria-hidden="true">
                {sectionOpen(schedule.scheduleId, 'observed') ? '▾' : '▸'}
              </span>
            </button>
            {#if sectionOpen(schedule.scheduleId, 'observed')}
              <div class="run-list">
                {#each schedule.recentRuns as run (run.id)}
                  <button
                    class="run-row"
                    class:is-selected={selectedTaskId === run.id}
                    type="button"
                    onclick={() => onSelect(run.id)}
                  >
                    <span class="run-rail" aria-hidden="true"></span>
                    <span class="run-head">
                      <i class="run-dot tone-{runTone(run)}"></i>
                      <span class="run-name">{runDisplayName(run)}</span>
                      <span class="run-badge">scheduled</span>
                    </span>
                    <span class="run-meta run-state run-state-{runTone(run)}">{runLabel(run)}</span>
                    <span class="run-meta">{runRuntime(run)}</span>
                    <span class="run-meta">{runTiming(run)}</span>
                    <span class="run-meta run-timepoint">{runWhen(run)}</span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </section>
  {/each}
</div>

<style>
  .schedule-list {
    display: grid;
    gap: 0.75rem;
    padding: 0.85rem 1rem 1rem;
  }

  .schedule-entry {
    display: grid;
    gap: 0.55rem;
    padding: 0.8rem 0.9rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background:
      linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  }

  .schedule-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: flex-start;
    gap: 1rem;
    width: 100%;
    border: none;
    background: transparent;
    padding: 0;
    text-align: left;
    cursor: pointer;
    font: inherit;
  }

  .schedule-select {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding-top: 0.1rem;
  }

  .schedule-select input {
    margin: 0;
  }

  .schedule-main {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
    align-self: stretch;
  }

  .schedule-title-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem;
    min-width: 0;
  }

  .schedule-name {
    font-size: 0.85rem;
    font-weight: 700;
    color: #0f172a;
  }

  .schedule-pattern,
  .schedule-queue,
  .run-badge {
    padding: 0.12rem 0.42rem;
    border-radius: 999px;
    background: #f3f4f6;
  }

  .schedule-pattern,
  .schedule-queue,
  .schedule-subtitle,
  .run-meta {
    font-size: 0.75rem;
    color: #64748b;
  }

  .schedule-subtitle {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .schedule-stats {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-start;
    gap: 0.4rem;
    flex-shrink: 0;
    min-width: 10rem;
  }

  .run-badge {
    font-size: 0.72rem;
    font-weight: 600;
  }

  .schedule-statusline {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.28rem;
    color: #6b7280;
    font-size: 0.74rem;
    line-height: 1.2;
    text-align: right;
  }

  .schedule-status {
    font-weight: 600;
  }

  .schedule-status-sep {
    color: #cbd5e1;
  }

  .schedule-status-neutral {
    color: #6b7280;
  }

  .schedule-status-queued {
    color: #4f46e5;
  }

  .schedule-status-active {
    color: #075985;
  }

  .schedule-status-success {
    color: #166534;
  }

  .schedule-status-danger {
    color: #b91c1c;
  }

  .schedule-chevron {
    color: #94a3b8;
    font-size: 0.82rem;
  }

  .schedule-strip {
    position: relative;
    display: grid;
    gap: 0.35rem;
    padding: 0.1rem 0 0.05rem;
  }

  .schedule-strip-line {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 1px;
    background: #cfd8e3;
    transform: translateY(-50%);
  }

  .schedule-strip-runs {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
  }

  .timeline-node {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 0.9rem;
    height: 0.9rem;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
  }

  .timeline-node-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 999px;
    box-shadow: 0 0 0 2px #fff;
    border: 1px solid rgba(15, 23, 42, 0.06);
  }

  .timeline-node.is-selected .timeline-node-dot {
    width: 0.65rem;
    height: 0.65rem;
    box-shadow: 0 0 0 2px #dbeafe;
  }

  .run-list {
    display: grid;
    gap: 0.35rem;
    padding-top: 0.15rem;
  }

  .run-group {
    display: grid;
    gap: 0.35rem;
  }

  .run-group-label {
    font-size: 0.69rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #94a3b8;
  }

  .run-group-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    width: 100%;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    font: inherit;
  }

  .run-group-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.35rem;
    height: 1.35rem;
    padding: 0 0.35rem;
    border-radius: 999px;
    background: #eef2f7;
    color: #475569;
    font-size: 0.72rem;
    font-weight: 700;
  }

  .run-group-chevron {
    margin-left: auto;
    color: #64748b;
    font-size: 0.82rem;
  }

  .run-group-note {
    font-size: 0.72rem;
    color: #94a3b8;
  }

  .run-row {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto auto;
    gap: 0.75rem;
    align-items: center;
    padding: 0.6rem 0.7rem 0.6rem 0.9rem;
    border: 1px solid #edf0f3;
    border-radius: 7px;
    background: #fff;
    cursor: pointer;
    text-align: left;
  }

  .run-row.is-selected {
    background: #eff6ff;
    border-color: #bfdbfe;
  }

  .pending-row {
    background: #f8fafc;
  }

  .run-rail {
    position: absolute;
    left: 0.35rem;
    top: 0.55rem;
    bottom: 0.55rem;
    width: 2px;
    border-radius: 999px;
    background: #e2e8f0;
  }

  .run-head {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
  }

  .run-dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    flex-shrink: 0;
  }

  .run-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.8rem;
    color: #111827;
  }

  .run-badge {
    color: #475569;
    background: #e2e8f0;
  }

  .run-state {
    text-transform: capitalize;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 1.35rem;
    padding: 0.08rem 0.45rem;
    border-radius: 999px;
    font-weight: 700;
  }

  .run-state-neutral,
  .run-state-queued {
    background: #e5e7eb;
    color: #334155;
  }

  .run-state-active {
    background: #cfe0ff;
    color: #1e3a8a;
  }

  .run-state-success {
    background: #bbf7d0;
    color: #14532d;
  }

  .run-state-danger {
    background: #fee2e2;
    color: #991b1b;
  }

  .run-timepoint {
    color: #475569;
    font-variant-numeric: tabular-nums;
  }

  :global(.tone-neutral) {
    background-color: #e5e7eb;
    color: #334155;
  }

  :global(.tone-active) {
    background-color: #cfe0ff;
    color: #1e3a8a;
  }

  :global(.tone-queued) {
    background-color: #e2e8f0;
    color: #334155;
  }

  :global(.tone-success) {
    background-color: #bbf7d0;
    color: #14532d;
  }

  :global(.tone-danger) {
    background-color: #fee2e2;
    color: #991b1b;
  }

  @media (max-width: 860px) {
    .schedule-stats {
      min-width: 0;
      align-items: flex-start;
    }

    .schedule-statusline {
      justify-content: flex-start;
      text-align: left;
    }
  }
</style>

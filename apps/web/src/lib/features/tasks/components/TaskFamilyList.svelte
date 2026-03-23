<script lang="ts">
  import SparkSpinner from './SparkSpinner.svelte';
  import type { TaskFamilyView } from '$lib/features/tasks/domain/group-task-families';
  import {
    formatTaskRuntime,
    formatRelativeTime,
    outcomePreview,
    stateLabel,
    toneForState,
    isRunningState
  } from '$lib/features/tasks/components/task-family-list-view';

  interface Props {
    families: TaskFamilyView[];
    selectedTaskId: string | null;
    onSelect: (taskId: string) => void;
    selectionEnabled?: boolean;
    selectedFamilyIds?: Set<string>;
    onToggleFamilySelection?: (familyId: string, selected: boolean) => void;
    expandedFamilyIds: Set<string>;
    onToggleExpanded: (familyId: string, nextExpanded: boolean) => void;
    nowMs?: number;
    recentlyAddedIds?: Set<string>;
  }

  const {
    families,
    selectedTaskId,
    onSelect,
    selectionEnabled = false,
    selectedFamilyIds = new Set<string>(),
    onToggleFamilySelection,
    expandedFamilyIds,
    onToggleExpanded,
    nowMs = Date.now(),
    recentlyAddedIds = new Set<string>()
  }: Props = $props();

  const isExpanded = (id: string): boolean => expandedFamilyIds.has(id);

  const toggle = (id: string): void => {
    onToggleExpanded(id, !expandedFamilyIds.has(id));
  };

  const rowIsSelected = (family: TaskFamilyView): boolean =>
    selectedTaskId === family.root.id || family.children.some((c) => c.id === selectedTaskId);

  const canExpand = (family: TaskFamilyView): boolean =>
    family.children.length > 0 ||
    family.root.resultPreview !== null ||
    family.root.exceptionPreview !== null ||
    family.root.retries > 0;

  const progressValue = (family: TaskFamilyView): number =>
    family.progressValue ?? family.completedCount;

  const progressTotal = (family: TaskFamilyView): number =>
    family.progressTotal ?? family.totalCount;

  const toggleSelection = (familyId: string, nextSelected: boolean): void => {
    onToggleFamilySelection?.(familyId, nextSelected);
  };
</script>

<div class="task-table">
  <div class="t-head">
    <span></span>
    <span></span>
    <span>Task</span>
    <span>State</span>
    <span class="t-dur">Duration</span>
    <span class="t-queue">Queue</span>
    <span class="t-worker">Worker</span>
    <span class="t-progress">Progress</span>
    <span class="t-outcome">Outcome</span>
    <span class="t-age">Age</span>
    <span></span>
  </div>

  {#each families as family (family.root.id)}
    <div class="t-entry">
      <!-- Main row -->
      <div
        class="t-row"
        class:is-selected={rowIsSelected(family)}
        class:is-new={recentlyAddedIds.has(family.root.id)}
        role="button"
        tabindex="0"
        onclick={() => onSelect(family.root.id)}
        onkeydown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect(family.root.id);
          }
        }}
      >
        <label class="t-select">
          {#if selectionEnabled}
            <input
              type="checkbox"
              checked={selectedFamilyIds.has(family.root.id)}
              onchange={(event) => {
                event.stopPropagation();
                toggleSelection(family.root.id, (event.currentTarget as HTMLInputElement).checked);
              }}
              onclick={(event) => event.stopPropagation()}
            />
          {/if}
        </label>
        <i
          class="t-dot tone-{toneForState(family.aggregateState)}"
          class:is-running={family.aggregateState === 'started'}
        ></i>
        <span class="t-name-wrap">
          <span class="t-name" title={family.root.id}>{family.displayName}</span>
          {#if family.root.scheduleId !== null}
            <span class="t-origin-tag">scheduled</span>
          {/if}
        </span>
        <span class="t-state-cell">
          <span class="t-badge tone-badge-{toneForState(family.aggregateState)}"
            >{stateLabel(family.aggregateState)}</span
          >
          {#if family.root.retries > 0}
            <span class="t-retry-chip" title="Retried {family.root.retries}× — attempt {family.root.retries + 1}">↻{family.root.retries}</span>
          {/if}
        </span>
        <span class="t-dur t-mono">{formatTaskRuntime(family.root, nowMs)}</span>
        <span class="t-queue t-meta">{family.root.queue ?? '—'}</span>
        <span class="t-worker t-meta">{family.root.workerHostname ?? '—'}</span>
        <span class="t-progress-cell">
          <span class="t-progress-meta">{progressValue(family)}/{progressTotal(family)}</span>
          <span class="t-progress-track" aria-hidden="true">
            <span
              class="t-progress-fill tone-{toneForState(family.aggregateState)}"
              style={`width: ${(progressValue(family) / Math.max(progressTotal(family), 1)) * 100}%`}
            ></span>
          </span>
        </span>
        <span class="t-outcome-cell">
          {#if family.canvasKind === null}
            <span
              class="t-outcome-preview"
              class:is-error={family.root.exceptionPreview !== null}
              title={family.root.exceptionPreview ?? family.root.resultPreview ?? `${family.root.retries} retries`}
            >
              {outcomePreview(family.root)}
            </span>
          {:else}
            <span class="t-outcome-preview is-empty" aria-hidden="true">—</span>
          {/if}
        </span>
        <span class="t-age t-meta">{formatRelativeTime(family.root.lastSeenAt, nowMs)}</span>
        {#if canExpand(family)}
          <button
            class="t-expand"
            type="button"
            aria-label={isExpanded(family.root.id) ? 'Collapse subtasks' : 'Expand subtasks'}
            onclick={(e) => {
              e.stopPropagation();
              toggle(family.root.id);
            }}>{isExpanded(family.root.id) ? '▾' : '▸'}</button>
        {:else}
          <span></span>
        {/if}
      </div>

      <!-- Inline expansion: subtasks + kwargs -->
      {#if isExpanded(family.root.id)}
        <div class="t-expanded" role="presentation">
          <!-- Subtask rows -->
          {#each family.children as child, idx (child.id)}
            <button
              class="sub-row"
              class:sub-selected={selectedTaskId === child.id}
              type="button"
              onclick={() => onSelect(child.id)}
            >
              <span class="sub-connector" aria-hidden="true"
                >{idx === family.children.length - 1 ? '└─' : '├─'}</span
              >
              <i class="t-dot tone-{toneForState(child.state)}"></i>
              <span class="t-name sub">{child.name ?? child.id}</span>
              <span class="sub-state">
                {#if isRunningState(child.state)}
                  <SparkSpinner />
                {/if}
                <span class="t-badge tone-badge-{toneForState(child.state)}"
                  >{stateLabel(child.state)}</span
                >
              </span>
              <span class="t-mono">{formatTaskRuntime(child)}</span>
              <span
                class="sub-outcome"
                class:is-error={child.exceptionPreview !== null}
                title={child.exceptionPreview ?? child.resultPreview ?? `${child.retries} retries`}
              >
                {outcomePreview(child, 48)}
              </span>
              <span class="t-meta">{formatRelativeTime(child.lastSeenAt, nowMs)}</span>
            </button>
          {/each}

          {#if family.root.retries > 0}
            <div class="t-preview t-preview-retry">
              <span class="preview-label retry">retries</span>
              <code class="preview-val retry">
                {family.root.retries} scheduled retry{family.root.retries === 1 ? '' : 's'} on this task execution
              </code>
            </div>
          {/if}

          <!-- Result / exception preview from summary -->
          {#if family.root.resultPreview !== null || family.root.exceptionPreview !== null}
            <div class="t-preview">
              {#if family.root.resultPreview !== null}
                <span class="preview-label">result</span>
                <code class="preview-val">{family.root.resultPreview}</code>
              {/if}
              {#if family.root.exceptionPreview !== null}
                <span class="preview-label err">exception</span>
                <code class="preview-val err">{family.root.exceptionPreview}</code>
              {/if}
            </div>
          {/if}

        </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .task-table {
    --t-cols: 1.2rem 0.5rem minmax(0, 1fr) auto 3.5rem 5.5rem 7rem minmax(0, 9rem) minmax(0, 12rem) 4.5rem 1.75rem;
    display: grid;
  }

  .t-head {
    display: grid;
    grid-template-columns: var(--t-cols);
    gap: 0.75rem;
    padding: 0.55rem 0.85rem;
    border-bottom: 1px solid #e2e6eb;
    color: #9ca3af;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    position: sticky;
    top: 0;
    background: #fff;
    z-index: 1;
  }

  .t-entry {
    border-top: 1px solid #f3f4f6;
  }

  .t-entry:first-of-type {
    border-top: none;
  }

  .t-name-wrap {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
  }

  .t-select {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .t-select input {
    margin: 0;
  }

  .t-progress-cell {
    display: grid;
    gap: 0.22rem;
    min-width: 0;
  }

  .t-row {
    display: grid;
    grid-template-columns: var(--t-cols);
    gap: 0.75rem;
    align-items: center;
    padding: 0 0.85rem;
    min-height: 2.5rem;
    cursor: pointer;
    user-select: none;
    outline: none;
  }

  .t-row:hover {
    background: #f6f7f9;
  }

  .t-row.is-selected {
    background: #eff6ff;
  }

  .t-row.is-new {
    animation: row-flash 2s ease-out forwards;
  }

  @keyframes row-flash {
    0%   { background: #dbeafe; }
    100% { background: transparent; }
  }

  .t-row:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: -2px;
  }

  .t-dot {
    display: block;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* Running dot pulses with blue shadow */
  .t-dot.is-running {
    animation: task-dot-pulse 2s ease-in-out infinite;
  }

  @keyframes task-dot-pulse {
    0%, 100% { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.22); }
    50%       { box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.06); }
  }

  .t-name {
    font-size: 0.84rem;
    font-weight: 500;
    color: #111827;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .t-origin-tag {
    display: inline-flex;
    align-items: center;
    padding: 0.1rem 0.38rem;
    border-radius: 999px;
    background: #ede9fe;
    color: #6d28d9;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: lowercase;
  }

  .t-name.sub {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    font-weight: 400;
    color: #374151;
  }

  .t-state-cell {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .t-badge {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.1rem 0.38rem;
    border-radius: 3px;
    white-space: nowrap;
    width: fit-content;
  }

  .t-retry-chip {
    font-size: 0.7rem;
    font-weight: 600;
    color: #b45309;
    background: #fffbeb;
    border: 1px solid #fde68a;
    padding: 0.1rem 0.32rem;
    border-radius: 3px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .t-mono {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #6b7280;
  }

  .t-meta {
    font-size: 0.78rem;
    color: #9ca3af;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .t-outcome-preview,
  .sub-outcome {
    min-width: 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .t-outcome-preview.is-error,
  .sub-outcome.is-error {
    color: #b91c1c;
  }

  .t-outcome-cell {
    min-width: 0;
    display: grid;
    gap: 0.22rem;
  }

  .t-progress-meta {
    font-size: 0.74rem;
    font-weight: 700;
    color: #516476;
  }

  .t-progress-track {
    display: block;
    width: 100%;
    height: 0.34rem;
    border-radius: 999px;
    background: #e7edf3;
    overflow: clip;
  }

  .t-progress-fill {
    display: block;
    height: 100%;
    border-radius: 999px;
  }

  .t-expand {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    border: none;
    background: transparent;
    color: #9ca3af;
    font-size: 0.72rem;
    cursor: pointer;
    border-radius: 3px;
    padding: 0;
    transition: background 0.12s, color 0.12s;
  }

  .t-expand:hover {
    background: #dbeafe;
    color: #2563eb;
  }

  /* Expanded panel */
  .t-expanded {
    background: #f6f7f9;
    border-top: 1px solid #e2e6eb;
    padding: 0.4rem 0.85rem 0.5rem;
    display: grid;
    gap: 0.2rem;
  }

  .sub-row {
    --sub-cols: 1.5rem 0.5rem minmax(0, 1fr) auto 3.5rem minmax(0, 12rem) 4.5rem;
    display: grid;
    grid-template-columns: var(--sub-cols);
    gap: 0.65rem;
    align-items: center;
    padding: 0.28rem 0.5rem;
    border: none;
    background: transparent;
    text-align: left;
    cursor: pointer;
    border-radius: 4px;
    width: 100%;
    transition: background 0.1s;
  }

  .sub-row:hover {
    background: #dbeafe;
  }

  .sub-row.sub-selected {
    background: #eff6ff;
  }

  .sub-connector {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #d1d5db;
    user-select: none;
  }

  .sub-state {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  /* Result / exception block */
  .t-preview {
    margin-top: 0.2rem;
    padding: 0.45rem 0.65rem;
    background: #fff;
    border: 1px solid #e2e6eb;
    border-radius: 4px;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.22rem 0.65rem;
    align-items: baseline;
  }

  .preview-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    white-space: nowrap;
    align-self: start;
    padding-top: 0.1rem;
  }

  .preview-label.err {
    color: #b91c1c;
  }

  .preview-label.retry {
    color: #b45309;
  }

  .preview-val {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #374151;
    word-break: break-all;
    white-space: pre-wrap;
  }

  .preview-val.err {
    color: #b91c1c;
  }

  .preview-val.retry {
    color: #b45309;
  }

  @media (max-width: 960px) {
    .task-table {
      --t-cols: 0.5rem minmax(0, 1fr) auto 3.5rem 5.5rem minmax(0, 10rem) 4.5rem 1.75rem;
    }
    .t-worker {
      display: none;
    }
  }

  @media (max-width: 640px) {
    .task-table {
      --t-cols: 0.5rem minmax(0, 1fr) auto minmax(0, 9rem) 1.75rem;
    }
    .t-dur,
    .t-queue,
    .t-worker,
    .t-age {
      display: none;
    }
    .sub-row {
      --sub-cols: 1.5rem 0.5rem minmax(0, 1fr) auto minmax(0, 9rem);
    }
  }
</style>

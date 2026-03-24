<script lang="ts">
  import TaskLifecycleBar from '$lib/components/live/TaskLifecycleBar.svelte';
  import type { TaskDetail, TaskSummary } from '$lib/core/contracts/monitor';

  interface Props {
    items: TaskSummary[];
    allItems: TaskSummary[];
    selectedTaskId: string | null;
    selectedTask: TaskDetail | null;
    onSelect: (taskId: string) => void;
  }

  const { items, allItems, selectedTaskId, selectedTask, onSelect }: Props = $props();

  const runtimeLabel = (task: TaskSummary): string => {
    const start = task.startedAt ?? task.receivedAt ?? task.sentAt;
    if (start === null) {
      return '-';
    }
    const startedAt = new Date(start).getTime();
    if (!Number.isFinite(startedAt)) {
      return '-';
    }
    const end = task.finishedAt ? new Date(task.finishedAt).getTime() : Date.now();
    const elapsedSeconds = Math.max(Math.floor((end - startedAt) / 1000), 0);
    if (elapsedSeconds < 60) {
      return `${elapsedSeconds}s`;
    }
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    return `${minutes}m ${seconds}s`;
  };

  const kwargsPreview = (task: TaskSummary): string => {
    if (selectedTaskId === task.id && selectedTask?.kwargsPreview) {
      return selectedTask.kwargsPreview;
    }
    return 'Select row to inspect kwargs';
  };

  const childProgress = (task: TaskSummary): { total: number; completed: number } => {
    const total = task.childrenIds.length;
    if (total === 0) {
      return { total: 0, completed: 0 };
    }
    const children = allItems.filter((item) => task.childrenIds.includes(item.id));
    const completed = children.filter((item) => item.state === 'succeeded' || item.state === 'failed').length;
    return { total, completed };
  };

  const clampPercent = (value: number): number => Math.min(Math.max(value, 0), 100);
</script>

<section class="running-list">
  {#each items as task (task.id)}
    {@const progress = childProgress(task)}
    {@const progressPercent = progress.total === 0 ? 0 : clampPercent((progress.completed / progress.total) * 100)}
    <article class:selected={selectedTaskId === task.id} class="running-card" onclick={() => onSelect(task.id)}>
      <header class="running-head">
        <div class="identity">
          <h4>{task.name ?? task.id}</h4>
          <small>{task.id}</small>
        </div>
        <div class="meta">
          <span class="meta-pill">{task.state}</span>
          <span class="meta-pill">{runtimeLabel(task)}</span>
        </div>
      </header>

      <TaskLifecycleBar state={task.state} retries={task.retries} />

      <div class="details-grid">
        <div class="detail-block">
          <small>Worker</small>
          <strong>{task.workerHostname ?? '-'}</strong>
        </div>
        <div class="detail-block">
          <small>Queue</small>
          <strong>{task.queue ?? '-'}</strong>
        </div>
        <div class="detail-block">
          <small>Children</small>
          <strong>{progress.total === 0 ? 'No children' : `${progress.completed} / ${progress.total} done`}</strong>
        </div>
      </div>

      {#if progress.total > 0}
        <div class="child-progress">
          <div class="child-progress-bar">
            <span style={`width:${progressPercent}%;`}></span>
          </div>
          <small>{Math.round(progressPercent)}% child completion</small>
        </div>
      {/if}

      <details class="kwargs-block" open={selectedTaskId === task.id && selectedTask?.kwargsPreview !== null}>
        <summary>Kwargs</summary>
        <pre>{kwargsPreview(task)}</pre>
      </details>
    </article>
  {/each}
</section>

<style>
  .running-list {
    display: grid;
    gap: 0.85rem;
  }

  .running-card {
    display: grid;
    gap: 0.85rem;
    padding: 1rem;
    border: 1px solid #d8e0ea;
    border-radius: 1rem;
    background: rgba(255, 255, 255, 0.92);
    cursor: pointer;
    transition:
      border-color 120ms ease,
      transform 120ms ease,
      box-shadow 120ms ease;
  }

  .running-card.selected {
    border-color: #4c6d8c;
    box-shadow: 0 12px 28px rgba(20, 33, 43, 0.08);
  }

  .running-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(20, 33, 43, 0.06);
  }

  .running-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .identity h4 {
    margin: 0;
    font-size: 0.96rem;
  }

  .identity small,
  .detail-block small,
  .child-progress small {
    color: #5f7184;
    font-size: 0.75rem;
  }

  .identity small {
    display: block;
    margin-top: 0.2rem;
    word-break: break-all;
  }

  .meta {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .meta-pill {
    padding: 0.25rem 0.55rem;
    border-radius: 999px;
    background: #eef2f5;
    color: #556371;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .details-grid {
    display: grid;
    gap: 0.8rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .detail-block {
    display: grid;
    gap: 0.2rem;
  }

  .detail-block strong {
    font-size: 0.84rem;
  }

  .child-progress {
    display: grid;
    gap: 0.4rem;
  }

  .child-progress-bar {
    height: 0.55rem;
    border-radius: 999px;
    background: #ecf1f5;
    overflow: hidden;
  }

  .child-progress-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #5f8b70 0%, #80a88f 100%);
  }

  .kwargs-block {
    border-top: 1px solid #ecf1f5;
    padding-top: 0.7rem;
  }

  .kwargs-block summary {
    cursor: pointer;
    color: #35556f;
    font-size: 0.8rem;
    font-weight: 700;
  }

  .kwargs-block pre {
    margin: 0.65rem 0 0;
    padding: 0.8rem;
    border-radius: 0.85rem;
    background: #f6f9fc;
    color: #31414f;
    font-size: 0.75rem;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
  }

  @media (max-width: 720px) {
    .running-head,
    .details-grid {
      grid-template-columns: 1fr;
      flex-direction: column;
    }

    .meta {
      justify-content: flex-start;
    }
  }
</style>

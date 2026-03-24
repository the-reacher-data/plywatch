<script lang="ts">
  import type { TaskDetail, TaskGraph, TaskSummary } from '$lib/core/contracts/monitor';
  import { buildFamilyTree, type FamilyTreeNode } from '$lib/features/tasks/domain/family-tree';
  import { buildTaskDagLayout } from '$lib/features/tasks/domain/task-graph-layout';

  interface Props {
    root: TaskDetail;
    graph: TaskGraph;
    byId: Map<string, TaskSummary>;
    selectedTaskId: string | null;
    onSelectTask: (taskId: string) => void;
  }

  const { root, graph, byId, selectedTaskId, onSelectTask }: Props = $props();

  const tree = $derived(buildFamilyTree(root, graph, byId));
  const hasChildren = $derived(tree.children.length > 0);
  let collapsedPhaseKeys = $state(new Set<string>());

  function formatRuntime(startedAt: string | null, finishedAt: string | null): string {
    if (startedAt === null) return '—';
    const t0 = new Date(startedAt).getTime();
    if (!Number.isFinite(t0)) return '—';
    const t1 = finishedAt !== null ? new Date(finishedAt).getTime() : Date.now();
    const ms = t1 - t0;
    if (ms < 0) return '—';
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${(ms / 1000).toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  }

  function formatTimestamp(iso: string | null): string {
    if (iso === null) return '—';
    const d = new Date(iso);
    if (!Number.isFinite(d.getTime())) return '—';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  const toneByState: Record<string, string> = {
    sent: '#8aa0b5',
    received: '#2f6ea8',
    started: '#1f7a8c',
    retrying: '#d08a1f',
    succeeded: '#2f855a',
    failed: '#c74b4b',
    lost: '#b91c1c'
  };

  function dotColor(state: string): string {
    return toneByState[state] ?? '#8aa0b5';
  }

  // Flatten the tree into rows for rendering, preserving connector context.
  //
  // Two-prefix approach is required for correct tree connectors:
  //   nodePrefix     — segments rendered BEFORE this node's own connector (│ or space per level)
  //   childrenBase   — base prefix that will be used as nodePrefix for direct children
  //
  // This mirrors the standard string-based tree algorithm where the prefix used to
  // DISPLAY a child row is the PARENT's current prefix, and the extension (│ or space)
  // is only added when recursing into grandchildren and beyond.
  //
  // Without this distinction, depth-1 nodes incorrectly render "│├─" instead of "├─".
  interface TreeRow {
    node: FamilyTreeNode;
    prefixSegments: boolean[]; // true = │ bar, false = space, one per ancestor depth level
  }

  function flattenTree(
    node: FamilyTreeNode,
    nodePrefix: boolean[],
    childrenBase: boolean[]
  ): TreeRow[] {
    const rows: TreeRow[] = [{ node, prefixSegments: nodePrefix }];
    for (let i = 0; i < node.children.length; i++) {
      const child = node.children[i]!;
      const isLast = i === node.children.length - 1;
      // Grandchildren inherit childrenBase + whether this level continues beyond this child.
      const grandchildrenBase = [...childrenBase, !isLast];
      rows.push(...flattenTree(child, childrenBase, grandchildrenBase));
    }
    return rows;
  }

  const rows = $derived(flattenTree(tree, [], []));
  const dagLayout = $derived(buildTaskDagLayout(root, graph, byId));
  const dagPhases = $derived(dagLayout.phases);
  const dagStats = $derived(dagLayout.stats);
  const useDagLayout = $derived(
    dagStats.isCanvasRooted || dagStats.hasParallelism || dagStats.hasJoin
  );
  const selectedPhaseKey = $derived(
    selectedTaskId === null
      ? null
      : (dagPhases.find((phase) => phase.nodes.some((node) => node.id === selectedTaskId))?.key ?? null)
  );

  function roleBadge(role: string | null): string | null {
    if (role === 'body') return 'join';
    return null;
  }

  function incomingEdgesForPhase(phaseIndex: number): number {
    if (phaseIndex <= 0) return 0;
    const current = dagPhases[phaseIndex];
    const previous = dagPhases[phaseIndex - 1];
    if (!current || !previous) return 0;
    const currentIds = new Set(current.nodes.map((node) => node.id));
    const previousIds = new Set(previous.nodes.map((node) => node.id));
    return graph.edges.filter((edge) => previousIds.has(edge.source) && currentIds.has(edge.target)).length;
  }

  $effect(() => {
    const rootId = graph.rootId;
    if (rootId === '') return;
    collapsedPhaseKeys = new Set(dagPhases.map((phase) => phase.key));
  });

  $effect(() => {
    const phaseKey = selectedPhaseKey;
    if (phaseKey === null) return;
    if (!collapsedPhaseKeys.has(phaseKey)) return;
    const next = new Set(collapsedPhaseKeys);
    next.delete(phaseKey);
    collapsedPhaseKeys = next;
  });
</script>

{#if useDagLayout}
  <div class="canvas-flow">
    <div class="canvas-summary">
      <div class="canvas-title">
        <strong>Task DAG</strong>
        <span>{dagPhases.length} stage{dagPhases.length === 1 ? '' : 's'} · {dagStats.total} task{dagStats.total === 1 ? '' : 's'}</span>
      </div>
      <div class="canvas-stats">
        <span class="canvas-stat">{dagStats.done} done</span>
        <span class="canvas-stat">{dagStats.running} running</span>
        <span class="canvas-stat">{dagStats.queued} queued</span>
        {#if dagStats.failed > 0}
          <span class="canvas-stat canvas-stat-danger">{dagStats.failed} failed</span>
        {/if}
      </div>
    </div>

    {#each dagPhases as phase, index (phase.key)}
      <section class="canvas-phase">
        {#if index > 0}
          <div class="stage-connector" aria-hidden="true">
            <span class="connector-line"></span>
            {#if incomingEdgesForPhase(index) > phase.nodes.length}
              <span class="connector-join">join</span>
            {/if}
          </div>
        {/if}
        <div
          class="stage-node"
          class:is-open={!collapsedPhaseKeys.has(phase.key)}
          class:has-selected={phase.nodes.some((node) => node.id === selectedTaskId)}
        >
          <button
            type="button"
            class="stage-toggle"
            aria-expanded={!collapsedPhaseKeys.has(phase.key)}
            onclick={() => {
              const next = new Set(collapsedPhaseKeys);
              if (next.has(phase.key)) next.delete(phase.key);
              else next.add(phase.key);
              collapsedPhaseKeys = next;
            }}
          >
            <div class="stage-node-top">
              <span class="phase-label">{phase.label}</span>
              <span class="phase-chevron">{collapsedPhaseKeys.has(phase.key) ? '▸' : '▾'}</span>
            </div>
            <div class="stage-node-bottom">
              <span class="stage-count">{phase.nodes.length} task{phase.nodes.length === 1 ? '' : 's'}</span>
              <span class="stage-state-strip" aria-hidden="true">
                {#each phase.nodes as node (node.id)}
                  <i class="stage-state-dot" style="background:{dotColor(node.state)};"></i>
                {/each}
              </span>
            </div>
          </button>
          {#if !collapsedPhaseKeys.has(phase.key)}
            <div class="stage-tasks">
              {#each phase.nodes as node (node.id)}
                {@const isSelected = selectedTaskId === node.id}
                {@const canSelect = !isSelected && (byId.has(node.id) || root.id === node.id)}
                <button
                  type="button"
                  class="task-chip"
                  class:is-selected={isSelected}
                  class:is-static={!canSelect}
                  disabled={!canSelect}
                  onclick={() => onSelectTask(node.id)}
                >
                  <span class="state-dot" class:dot-live={node.state === 'started'} style="background:{dotColor(node.state)};"></span>
                  <span class="task-chip-name">{node.name ?? node.id}</span>
                  <span class="task-chip-meta">
                    {#if roleBadge(node.role) !== null}
                      <span class="body-badge">{roleBadge(node.role)}</span>
                    {/if}
                    {#if node.retries > 0}
                      <span class="retry-chip">↻{node.retries}</span>
                    {/if}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </section>
    {/each}
  </div>
{:else}
  <div class="family-tree" class:single-task={!hasChildren}>
    {#each rows as row (row.node.id)}
      {@const node = row.node}
      {@const isRoot = node.depth === 0}
      {@const isSelected = selectedTaskId === node.id}
      {@const canSelect = !isSelected && byId.has(node.id)}
      <button
        type="button"
        class="tree-row"
        class:is-root={isRoot}
        class:is-selected={isSelected}
        class:is-static={!canSelect}
        disabled={!canSelect}
        onclick={() => onSelectTask(node.id)}
      >
        <span class="connector" aria-hidden="true">
          {#each row.prefixSegments as continues, idx (idx)}
            <span class="seg">{continues ? '│' : ' '}</span>
          {/each}
          {#if !isRoot}
            <span class="seg">{node.isLastChild ? '└─' : '├─'}</span>
          {/if}
        </span>

        <span
          class="state-dot"
          class:dot-live={node.state === 'started'}
          style="background:{dotColor(node.state)};"
          aria-label={node.state}
        ></span>

        <span class="node-name" class:root-name={isRoot}>{node.name ?? node.id}</span>

        {#if node.retries > 0}
          <span class="retry-chip" title="Attempt {node.retries + 1}">↻{node.retries}</span>
        {/if}

        <span class="timing">
          {#if node.startedAt !== null || node.sentAt !== null}
            <span class="time-range">
              {formatTimestamp(node.startedAt ?? node.sentAt)}
              {#if node.finishedAt !== null}
                <span class="time-sep">→</span>
                {formatTimestamp(node.finishedAt)}
              {:else if node.state === 'started' || node.state === 'retrying'}
                <span class="time-sep">→</span>
                <span class="running-now">running…</span>
              {/if}
            </span>
            <span class="duration">({formatRuntime(node.startedAt ?? node.sentAt, node.finishedAt)})</span>
          {:else}
            <span class="no-timing">no timing</span>
          {/if}
        </span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .family-tree {
    display: grid;
    gap: 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.76rem;
  }

  .single-task {
    padding: 0.5rem 0.75rem;
  }

  .tree-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.32rem 0.75rem;
    border: none;
    background: transparent;
    text-align: left;
    cursor: pointer;
    width: 100%;
    border-radius: 0.4rem;
    transition: background 0.1s;
    min-width: 0;
  }

  .tree-row:hover {
    background: #f0f6fb;
  }

  .tree-row.is-selected {
    background: #e6f1fb;
  }

  .tree-row.is-root {
    font-weight: 600;
  }

  .tree-row.is-static {
    cursor: default;
  }

  .canvas-flow {
    display: grid;
    gap: 0.45rem;
    padding: 0.35rem 0;
  }

  .canvas-summary {
    display: grid;
    gap: 0.35rem;
    padding: 0 0.75rem;
  }

  .canvas-title {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: baseline;
    color: #314454;
  }

  .canvas-title strong {
    font-size: 0.8rem;
    color: #14212b;
  }

  .canvas-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .canvas-stat {
    display: inline-flex;
    align-items: center;
    padding: 0.14rem 0.4rem;
    border-radius: 999px;
    background: #eef3f7;
    color: #536779;
    font-size: 0.68rem;
    font-weight: 700;
  }

  .canvas-stat-danger {
    background: #fdecec;
    color: #b34747;
  }

  .canvas-phase {
    display: grid;
    justify-items: center;
    gap: 0.2rem;
    padding: 0 0.75rem;
  }

  .stage-connector {
    width: 100%;
    display: grid;
    justify-items: center;
    gap: 0.12rem;
    padding-bottom: 0.05rem;
  }

  .connector-line {
    width: 2px;
    height: 1rem;
    background: linear-gradient(180deg, #c8d6e0 0%, #dfe8ef 100%);
    border-radius: 999px;
  }

  .connector-join {
    padding: 0.02rem 0.28rem;
    border-radius: 999px;
    background: #fff5e8;
    color: #a55b14;
    font-size: 0.55rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .stage-node {
    width: min(17rem, 100%);
    border: 1px solid #dfe8ef;
    background: #ffffff;
    border-radius: 0.7rem;
    text-align: left;
    transition: border-color 120ms ease, background 120ms ease, box-shadow 120ms ease;
    overflow: hidden;
  }

  .stage-node:hover {
    border-color: #c8d6e0;
    background: #fcfdff;
    box-shadow: 0 8px 18px rgba(20, 33, 43, 0.04);
  }

  .stage-node.is-open {
    background: #fbfdff;
  }

  .stage-node.has-selected {
    border-color: #9fbfd6;
    box-shadow: 0 0 0 1px rgba(159, 191, 214, 0.35);
    background: linear-gradient(180deg, #fbfdff 0%, #f5f9fc 100%);
  }

  .stage-toggle {
    width: 100%;
    border: none;
    background: transparent;
    padding: 0.55rem 0.7rem;
    text-align: left;
    cursor: pointer;
  }

  .stage-node-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .phase-label {
    color: #42596c;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .stage-node-bottom {
    margin-top: 0.35rem;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
  }

  .stage-count {
    display: inline-flex;
    align-items: center;
    color: #7b90a0;
    font-size: 0.74rem;
    font-weight: 600;
  }

  .stage-state-strip {
    display: inline-flex;
    align-items: center;
    gap: 0.16rem;
    justify-content: flex-end;
    min-width: 0;
    flex-wrap: wrap;
  }

  .stage-state-dot {
    width: 0.34rem;
    height: 0.34rem;
    border-radius: 999px;
    opacity: 0.95;
  }

  .phase-chevron {
    color: #8ca0af;
    font-size: 0.86rem;
    line-height: 1;
  }

  .stage-tasks {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    padding: 0 0.55rem 0.55rem;
    width: 100%;
    border-top: 1px solid #edf2f6;
    background: linear-gradient(180deg, rgba(248, 251, 253, 0.9) 0%, rgba(252, 253, 254, 0.95) 100%);
    align-items: flex-start;
    justify-content: center;
  }

  .task-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.38rem;
    min-width: 0;
    max-width: 100%;
    border: 1px solid #e5ecf2;
    background: #fbfdfe;
    border-radius: 999px;
    padding: 0.34rem 0.5rem;
    text-align: left;
    cursor: pointer;
    transition: border-color 120ms ease, background 120ms ease;
  }

  .task-chip:hover:not(:disabled) {
    border-color: #ccd9e3;
    background: #ffffff;
  }

  .task-chip.is-selected {
    border-color: #9fbfd6;
    background: #f3f8fb;
  }

  .task-chip.is-static {
    cursor: default;
  }

  .task-chip-name {
    min-width: 0;
    max-width: 10rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #173041;
    font-size: 0.66rem;
    font-weight: 800;
  }

  .task-chip-meta {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    margin-left: auto;
    flex-shrink: 0;
  }

  .body-badge {
    padding: 0.04rem 0.22rem;
    border-radius: 999px;
    background: #f3f6f8;
    color: #738696;
    font-size: 0.54rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  /* Connector */
  .connector {
    display: flex;
    color: #b8c8d4;
    white-space: pre;
    flex-shrink: 0;
    line-height: 1;
  }

  .seg {
    display: inline-block;
    width: 1.4ch;
  }

  /* State dot */
  .state-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    flex-shrink: 0;
    border: 1.5px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.08);
  }

  .dot-live {
    animation: dot-pulse 2s ease-in-out infinite;
  }

  @keyframes dot-pulse {
    0%, 100% { box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.08), 0 0 0 2px rgba(31, 122, 140, 0.2); }
    50%       { box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.08), 0 0 0 4px rgba(31, 122, 140, 0.06); }
  }

  /* Name */
  .node-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #1e3040;
    min-width: 0;
  }

  .root-name {
    color: #14212b;
  }

  /* Retry chip */
  .retry-chip {
    font-size: 0.62rem;
    font-weight: 700;
    color: #9e6a1a;
    background: #fef4e4;
    border: 1px solid #f0d49a;
    padding: 0.08rem 0.28rem;
    border-radius: 999px;
    flex-shrink: 0;
  }

  /* Timing block */
  .timing {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
    color: #7a8fa0;
    font-size: 0.7rem;
    white-space: nowrap;
  }

  .time-range {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .time-sep {
    color: #b0bfcc;
  }

  .running-now {
    color: #1f7a8c;
    font-style: italic;
  }

  .duration {
    color: #9aacba;
  }

  .no-timing {
    color: #b8c8d4;
    font-style: italic;
  }

  @media (max-width: 700px) {
    .stage-node,
    .stage-tasks {
      width: 100%;
    }
  }
</style>

<script lang="ts">
  export interface SparklineSeries {
    key: string;
    label?: string;
    values: number[];
    stroke: string;
    heartbeatState?: 'online' | 'stale' | 'offline';
    active?: number | null;
  }

  export let series: SparklineSeries[] = [];

  const W = 100;
  const H = 38;
  const PAD = 3;

  function localPeak(values: number[]): number {
    return Math.max(1, ...values);
  }

  function toY(value: number, pk: number): number {
    const ratio = Math.min(Math.max(value / pk, 0), 1);
    return H - PAD - ratio * (H - PAD * 2 - 2);
  }

  // Catmull-Rom → cubic bezier for smooth curves
  function buildSmoothLine(values: number[], pk: number): string {
    if (values.length === 0) return '';
    if (values.length === 1) {
      return `M ${(W / 2).toFixed(2)} ${toY(values[0] ?? 0, pk).toFixed(2)}`;
    }
    const pts = values.map((v, i) => ({
      x: (i / (values.length - 1)) * W,
      y: toY(v, pk)
    }));
    let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[Math.min(pts.length - 1, i + 2)];
      const cp1x = (p1.x + (p2.x - (p0?.x ?? p1.x)) / 6).toFixed(2);
      const cp1y = (p1.y + (p2.y - (p0?.y ?? p1.y)) / 6).toFixed(2);
      const cp2x = (p2.x - ((p3?.x ?? p2.x) - p1.x) / 6).toFixed(2);
      const cp2y = (p2.y - ((p3?.y ?? p2.y) - p1.y) / 6).toFixed(2);
      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
    }
    return d;
  }

  function buildSmoothArea(values: number[], pk: number): string {
    if (values.length === 0) return '';
    const line = buildSmoothLine(values, pk);
    const lastX = values.length === 1 ? W / 2 : W;
    return `${line} L ${lastX.toFixed(2)} ${(H - PAD).toFixed(2)} L 0 ${(H - PAD).toFixed(2)} Z`;
  }

  function endPoint(values: number[], pk: number): { x: number; y: number } | null {
    if (values.length === 0) return null;
    const last = values[values.length - 1] ?? 0;
    const x = values.length === 1 ? W / 2 : W;
    return { x, y: toY(last, pk) };
  }

  function shortName(key: string, label?: string): string {
    if (label !== undefined && label !== '') return label;
    const afterAt = key.includes('@') ? (key.split('@')[1] ?? key) : key;
    return afterAt.split('.')[0] ?? afterAt;
  }

  function gradId(key: string): string {
    return `sg-${key.replace(/[^a-zA-Z0-9]/g, '-')}`;
  }
</script>

<div class="pulse-shell" aria-hidden="true">
  {#if series.length === 0}
    <div class="pulse-empty">Waiting for worker activity…</div>
  {:else}
    {#each series as item (item.key)}
      {@const pk = localPeak(item.values)}
      {@const ep = endPoint(item.values, pk)}
      {@const line = buildSmoothLine(item.values, pk)}
      {@const area = buildSmoothArea(item.values, pk)}
      {@const state = item.heartbeatState ?? 'offline'}
      {@const gid = gradId(item.key)}
      {@const hasActive = (item.active ?? 0) > 0}
      <div class="pulse-row">
        <span class="pulse-label" title={item.key}>{shortName(item.key, item.label)}</span>

        <div class="pulse-chart">
          <svg viewBox="0 0 100 38" preserveAspectRatio="none" class="pulse-svg">
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style="stop-color:{item.stroke}; stop-opacity:0.28" />
                <stop offset="100%" style="stop-color:{item.stroke}; stop-opacity:0.02" />
              </linearGradient>
            </defs>
            <!-- 50% grid reference line -->
            <line x1="0" y1="20" x2="100" y2="20" class="grid-mid" />
            <!-- Baseline -->
            <line x1="0" y1="35" x2="100" y2="35" class="baseline" />
            {#if area}
              <path d={area} fill="url(#{gid})" />
            {/if}
            {#if line}
              <path
                d={line}
                fill="none"
                style="stroke:{item.stroke}; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"
              />
            {/if}
            {#if ep !== null}
              <circle
                cx={ep.x}
                cy={ep.y}
                r="2.8"
                style="fill:{item.stroke};"
                class="endpoint-dot"
                class:dot-live={state === 'online'}
              />
            {/if}
          </svg>
        </div>

        <div class="pulse-meta">
          {#if hasActive}
            <span class="pulse-active-badge">{item.active}</span>
          {:else}
            <span class="pulse-idle">—</span>
          {/if}
          <span class="pulse-state-dot state-{state}" title={state}></span>
        </div>
      </div>
    {/each}
  {/if}
</div>

<style>
  .pulse-shell {
    display: grid;
    gap: 0.2rem;
    width: 100%;
  }

  .pulse-row {
    display: grid;
    grid-template-columns: 7rem 1fr 3.4rem;
    align-items: center;
    gap: 0.65rem;
    min-height: 2.4rem;
    padding: 0.18rem 0.5rem;
    border-radius: 5px;
    transition: background 0.12s;
  }

  .pulse-row:hover {
    background: #f6f7f9;
  }

  .pulse-label {
    color: #374151;
    font-size: 0.73rem;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pulse-chart {
    height: 2.4rem;
  }

  .pulse-svg {
    width: 100%;
    height: 100%;
    display: block;
    overflow: visible;
  }

  .baseline {
    stroke: #e2e6eb;
    stroke-width: 0.6;
  }

  .grid-mid {
    stroke: #f3f4f6;
    stroke-width: 0.5;
    stroke-dasharray: 2 2;
  }

  .endpoint-dot {
    transition: opacity 0.2s;
  }

  .dot-live {
    transform-origin: center;
    transform-box: fill-box;
    animation: dot-scale 1.8s ease-in-out infinite;
  }

  @keyframes dot-scale {
    0%, 100% { transform: scale(1);    opacity: 1; }
    50%       { transform: scale(1.65); opacity: 0.6; }
  }

  .pulse-meta {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.4rem;
    flex-shrink: 0;
  }

  .pulse-active-badge {
    font-size: 0.68rem;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    color: #1d4ed8;
    background: #eff6ff;
    border-radius: 3px;
    padding: 0.08rem 0.32rem;
    min-width: 1.3rem;
    text-align: center;
  }

  .pulse-idle {
    font-size: 0.7rem;
    color: #d1d5db;
    font-family: 'IBM Plex Mono', monospace;
    min-width: 1.3rem;
    text-align: right;
  }

  .pulse-state-dot {
    width: 0.46rem;
    height: 0.46rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .state-online {
    background: #16a34a;
    box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.18);
    animation: ring-pulse 1.8s ease-in-out infinite;
  }

  .state-stale {
    background: #d97706;
  }

  .state-offline {
    background: #d1d5db;
  }

  @keyframes ring-pulse {
    0%, 100% { box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.18); }
    50%       { box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.04); }
  }

  .pulse-empty {
    display: grid;
    place-items: center;
    min-height: 5rem;
    color: #9ca3af;
    font-size: 0.82rem;
  }

  @media (max-width: 720px) {
    .pulse-row {
      grid-template-columns: 5.5rem 1fr 3rem;
    }
  }
</style>

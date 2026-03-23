<script lang="ts">
  export let values: number[] = [];
  export let stroke = '#1e4f85';
  export let fill = 'rgba(30, 79, 133, 0.12)';

  const width = 240;
  const height = 72;
  const padding = 8;

  const buildLine = (samples: number[]): string => {
    if (samples.length === 0) {
      return '';
    }
    const max = Math.max(...samples, 1);
    const step = samples.length === 1 ? width - padding * 2 : (width - padding * 2) / (samples.length - 1);
    return samples
      .map((value, index) => {
        const x = padding + index * step;
        const y = height - padding - ((value / max) * (height - padding * 2));
        return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  };

  const buildArea = (samples: number[]): string => {
    if (samples.length === 0) {
      return '';
    }
    const line = buildLine(samples);
    const lastX = samples.length === 1 ? width / 2 : width - padding;
    return `${line} L ${lastX} ${height - padding} L ${padding} ${height - padding} Z`;
  };

  $: linePath = buildLine(values);
  $: areaPath = buildArea(values);
</script>

<div class="sparkline-shell" aria-hidden="true">
  <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
    {#if areaPath}
      <path d={areaPath} fill={fill}></path>
    {/if}
    {#if linePath}
      <path d={linePath} fill="none" stroke={stroke} stroke-width="2.5" stroke-linecap="round"></path>
    {/if}
  </svg>
</div>

<style>
  .sparkline-shell {
    width: 100%;
    height: 4.5rem;
    border-radius: 0.85rem;
    background: linear-gradient(180deg, rgba(248, 251, 255, 0.9) 0%, rgba(255, 255, 255, 0.96) 100%);
    overflow: hidden;
  }

  svg {
    width: 100%;
    height: 100%;
    display: block;
  }
</style>

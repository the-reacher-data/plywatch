<script lang="ts">
  import { Popover } from 'bits-ui';
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    lines?: string[];
    /**
     * Receives the bits-ui merged trigger props to spread on the trigger element.
     * Example:
     *   {#snippet trigger(props)}
     *     <button {...props} class="event-node">...</button>
     *   {/snippet}
     */
    trigger: Snippet<[Record<string, unknown>]>;
    /** Optional footer content rendered below the detail lines. */
    footer?: Snippet;
  }

  const { title = '', lines = [], trigger, footer }: Props = $props();
</script>

<Popover.Root>
  <Popover.Trigger>
    {#snippet child({ props })}
      {@render trigger(props)}
    {/snippet}
  </Popover.Trigger>

  <Popover.Content class="popover-panel" sideOffset={8}>
    {#if title}
      <h5 class="panel-title">{title}</h5>
    {/if}

    {#if lines.length > 0}
      <div class="panel-lines">
        {#each lines as line, i (i)}
          <p>{line}</p>
        {/each}
      </div>
    {/if}

    {#if footer}
      <div class="panel-footer">
        {@render footer()}
      </div>
    {/if}
  </Popover.Content>
</Popover.Root>

<style>
  .panel-title {
    margin: 0 0 0.45rem;
    font-size: 0.82rem;
    font-weight: 700;
    color: #14212b;
  }

  .panel-lines {
    display: grid;
    gap: 0.3rem;
  }

  .panel-lines p {
    margin: 0;
    color: #4c5a69;
    font-size: 0.76rem;
    line-height: 1.35;
  }

  .panel-footer {
    margin-top: 0.65rem;
    padding-top: 0.55rem;
    border-top: 1px solid #ecf1f6;
  }
</style>

<script lang="ts">
  import { onMount } from 'svelte';

  export let label = 'Details';
  export let title = '';
  export let lines: string[] = [];
  export let hoverCloseDelayMs = 180;
  export let pinnedCloseDelayMs = 900;

  let shellElement: HTMLDivElement | null = null;
  let hoverOpen = false;
  let pinnedOpen = false;
  let closeTimer: ReturnType<typeof setTimeout> | null = null;

  const clearCloseTimer = (): void => {
    if (closeTimer !== null) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
  };

  const isOpen = (): boolean => hoverOpen || pinnedOpen;

  const scheduleHoverClose = (): void => {
    clearCloseTimer();
    closeTimer = setTimeout(() => {
      if (pinnedOpen) {
        close();
        return;
      }
      hoverOpen = false;
    }, pinnedOpen ? pinnedCloseDelayMs : hoverCloseDelayMs);
  };

  const toggle = (): void => {
    clearCloseTimer();
    pinnedOpen = !pinnedOpen;
    hoverOpen = true;
  };

  const close = (): void => {
    clearCloseTimer();
    hoverOpen = false;
    pinnedOpen = false;
  };

  const handlePointerEnter = (): void => {
    clearCloseTimer();
    hoverOpen = true;
  };

  const handlePointerLeave = (): void => {
    scheduleHoverClose();
  };

  const handleDocumentPointerDown = (event: PointerEvent): void => {
    if (shellElement?.contains(event.target as Node) ?? false) {
      return;
    }
    close();
  };

  const handleKeyDown = (event: KeyboardEvent): void => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle();
    }
    if (event.key === 'Escape') {
      close();
    }
  };

  onMount(() => {
    globalThis.document?.addEventListener('pointerdown', handleDocumentPointerDown);
    return () => {
      clearCloseTimer();
      globalThis.document?.removeEventListener('pointerdown', handleDocumentPointerDown);
    };
  });
</script>

<div
  class="popover-shell"
  role="presentation"
  bind:this={shellElement}
  onpointerenter={handlePointerEnter}
  onpointerleave={handlePointerLeave}
>
  <span
    class="trigger"
    role="button"
    tabindex="0"
    aria-expanded={isOpen()}
    onclick={toggle}
    onkeydown={handleKeyDown}
  >
    <slot name="trigger">{label}</slot>
  </span>
  {#if isOpen()}
    <section class="panel">
      {#if title}
        <h5>{title}</h5>
      {/if}
      <div class="lines">
        {#each lines as line (line)}
          <p>{line}</p>
        {/each}
      </div>
      <div class="footer">
        <slot name="footer"></slot>
      </div>
    </section>
  {/if}
</div>

<style>
  .popover-shell {
    position: relative;
    display: inline-flex;
  }

  .trigger {
    border: 0;
    background: transparent;
    padding: 0;
    cursor: pointer;
  }

  .panel {
    position: absolute;
    top: calc(100% + 0.45rem);
    left: 50%;
    z-index: 20;
    width: 16rem;
    transform: translateX(-50%);
    padding: 0.8rem 0.9rem;
    border: 1px solid #d8e0ea;
    border-radius: 0.85rem;
    background: #ffffff;
    box-shadow: 0 16px 34px rgba(20, 33, 43, 0.14);
    text-align: left;
  }

  h5 {
    margin: 0 0 0.45rem;
    font-size: 0.82rem;
  }

  .lines {
    display: grid;
    gap: 0.3rem;
  }

  .lines p {
    margin: 0;
    color: #4c5a69;
    font-size: 0.76rem;
    line-height: 1.35;
  }

  .footer:empty {
    display: none;
  }

  .footer {
    margin-top: 0.65rem;
    padding-top: 0.55rem;
    border-top: 1px solid #ecf1f6;
  }
</style>

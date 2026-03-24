<script lang="ts">
  interface Props {
    title?: string;
    lines: string[];
  }

  let { title = '', lines }: Props = $props();

  let open = $state(false);
  let closeTimer: ReturnType<typeof setTimeout> | null = null;
  let shell: HTMLSpanElement | null = null;

  const clearCloseTimer = (): void => {
    if (closeTimer !== null) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
  };

  const show = (): void => {
    clearCloseTimer();
    open = true;
  };

  const hideSoon = (): void => {
    clearCloseTimer();
    closeTimer = setTimeout(() => {
      open = false;
      closeTimer = null;
    }, 120);
  };

  const toggle = (): void => {
    clearCloseTimer();
    open = !open;
  };

  $effect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: PointerEvent): void => {
      if (shell?.contains(event.target as Node) ?? false) {
        return;
      }
      open = false;
    };

    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        open = false;
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  });
</script>

<span
  class="info-shell"
  role="presentation"
  bind:this={shell}
  onmouseenter={show}
  onmouseleave={hideSoon}
>
  <button
    type="button"
    class="info-hint"
    aria-expanded={open}
    aria-label={title || lines.join(' ')}
    onclick={toggle}
    onfocus={show}
    onblur={hideSoon}
  >
    i
  </button>

  {#if open}
    <section class="info-panel" role="tooltip">
      {#if title.length > 0}
        <h5>{title}</h5>
      {/if}
      {#each lines as line (line)}
        <p>{line}</p>
      {/each}
    </section>
  {/if}
</span>

<style>
  .info-shell {
    position: relative;
    display: inline-flex;
    align-items: center;
  }

  .info-hint {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 0.8rem;
    height: 0.8rem;
    padding: 0;
    border-radius: 999px;
    border: 1px solid #cbd5e1;
    color: #64748b;
    background: #fff;
    font-size: 0.56rem;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    text-transform: lowercase;
    vertical-align: middle;
  }

  .info-hint:hover {
    border-color: #94a3b8;
    color: #334155;
  }

  .info-panel {
    position: absolute;
    top: calc(100% + 0.45rem);
    left: 50%;
    z-index: 30;
    width: 14rem;
    transform: translateX(-50%);
    padding: 0.75rem 0.85rem;
    border: 1px solid #d8e0ea;
    border-radius: 0.8rem;
    background: #ffffff;
    box-shadow: 0 16px 34px rgba(20, 33, 43, 0.14);
    text-align: left;
  }

  h5 {
    margin: 0 0 0.35rem;
    font-size: 0.78rem;
    color: #0f172a;
  }

  p {
    margin: 0;
    color: #475569;
    font-size: 0.74rem;
    line-height: 1.35;
  }

  p + p {
    margin-top: 0.3rem;
  }
</style>

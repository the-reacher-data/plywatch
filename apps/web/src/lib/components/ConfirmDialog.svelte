<script lang="ts">
  interface Props {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    destructive?: boolean;
    busy?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  }

  let {
    open,
    title,
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    destructive = false,
    busy = false,
    onConfirm,
    onCancel,
  }: Props = $props();
</script>

{#if open}
  <div
    class="dialog-backdrop"
    role="button"
    tabindex="0"
    aria-label="Close confirmation dialog"
    onclick={onCancel}
    onkeydown={(event) => {
      if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onCancel();
      }
    }}
  >
    <div
      class="dialog-card"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      tabindex="-1"
      onclick={(event) => event.stopPropagation()}
      onkeydown={(event) => event.stopPropagation()}
    >
      <h3 id="confirm-dialog-title">{title}</h3>
      <p>{message}</p>
      <div class="dialog-actions">
        <button type="button" class="dialog-btn" onclick={onCancel} disabled={busy}>{cancelLabel}</button>
        <button
          type="button"
          class="dialog-btn dialog-btn-confirm"
          class:dialog-btn-danger={destructive}
          onclick={onConfirm}
          disabled={busy}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(15, 23, 42, 0.32);
    z-index: 60;
  }

  .dialog-card {
    width: min(28rem, calc(100vw - 2rem));
    display: grid;
    gap: 0.9rem;
    padding: 1rem 1rem 0.9rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.9rem;
    background: #fff;
    box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
  }

  .dialog-card h3,
  .dialog-card p {
    margin: 0;
  }

  .dialog-card h3 {
    font-size: 0.96rem;
    color: #0f172a;
  }

  .dialog-card p {
    font-size: 0.84rem;
    line-height: 1.5;
    color: #475569;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
  }

  .dialog-btn {
    border: 1px solid #d1d5db;
    border-radius: 0.65rem;
    background: #fff;
    color: #1f2937;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.5rem 0.85rem;
    cursor: pointer;
  }

  .dialog-btn-confirm {
    background: #111827;
    color: #fff;
    border-color: #111827;
  }

  .dialog-btn-danger {
    background: #b91c1c;
    border-color: #b91c1c;
  }
</style>

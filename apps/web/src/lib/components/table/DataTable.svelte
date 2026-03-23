<script lang="ts">
  import type { TableView } from '$lib/components/table/create-table';

  interface Props {
    view: TableView<unknown>;
    selectedRowId?: string | null;
    onSelect?: (rowId: string) => void;
  }

  const {
    view,
    selectedRowId = null,
    onSelect
  }: Props = $props();
</script>

<table class="data-table">
  <thead>
    <tr>
      {#each view.headers as header (header)}
        <th>{header}</th>
      {/each}
    </tr>
  </thead>
  <tbody>
    {#each view.rows as row (row.id)}
      <tr class:selected={selectedRowId === row.id} onclick={() => onSelect?.(row.id)}>
        {#each row.cells as cell (cell.id)}
          <td>{cell.value}</td>
        {/each}
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
    background: #fff;
    border: 1px solid #d8e0ea;
    border-radius: 1rem;
    overflow: hidden;
  }

  th,
  td {
    padding: 0.75rem;
    border-bottom: 1px solid #d8e0ea;
    text-align: left;
  }

  tbody tr {
    cursor: pointer;
  }

  tbody tr.selected {
    background: #eaf3ff;
  }
</style>

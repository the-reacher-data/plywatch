<script lang="ts">
  import DataTable from '$lib/components/table/DataTable.svelte';
  import { buildTableView } from '$lib/components/table/create-table';
  import { toColumnDefs } from '$lib/components/table/types';
  import type { TaskSummary } from '$lib/core/contracts/monitor';
  import { taskColumns } from '$lib/features/tasks/components/task-columns';

  interface Props {
    items: TaskSummary[];
    selectedTaskId: string | null;
    onSelect: (taskId: string) => void;
  }

  const { items, selectedTaskId, onSelect }: Props = $props();
  const view = $derived(buildTableView(items, toColumnDefs(taskColumns), (item) => item.id));
</script>

<DataTable
  {view}
  selectedRowId={selectedTaskId}
  onSelect={onSelect}
/>

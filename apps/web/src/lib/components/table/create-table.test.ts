import { describe, expect, it } from 'vitest';

import { buildTableView } from '$lib/components/table/create-table';
import { toColumnDefs, type TableColumn } from '$lib/components/table/types';

interface RowItem {
  id: string;
  value: string;
}

describe('buildTableView', () => {
  it('builds a renderable table view from generic columns', () => {
    const items: RowItem[] = [{ id: '1', value: 'hello' }];
    const columns: TableColumn<RowItem>[] = [
      {
        id: 'value',
        header: 'Value',
        accessor: (row) => row.value
      }
    ];

    const table = buildTableView(items, toColumnDefs(columns), (item) => item.id);

    expect(table.headers).toEqual(['Value']);
    expect(table.rows).toHaveLength(1);
    expect(table.rows[0]?.id).toBe('1');
    expect(table.rows[0]?.cells[0]?.value).toBe('hello');
  });

  it('uses the custom cell renderer when provided', () => {
    const columns: TableColumn<RowItem>[] = [
      {
        id: 'value',
        header: 'Value',
        accessor: (row) => row.value,
        cell: (value, row) => `${row.id}:${String(value).toUpperCase()}`
      }
    ];

    const [column] = toColumnDefs(columns);
    const rendered = column?.cell?.({
      getValue: () => 'hello',
      row: { original: { id: '1', value: 'hello' } }
    } as never);

    expect(rendered).toBe('1:HELLO');
  });
});

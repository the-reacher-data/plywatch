import type { AccessorFn, ColumnDef } from '@tanstack/table-core';

export interface TableColumn<TData> {
  id: string;
  header: string;
  accessor: AccessorFn<TData, unknown>;
  cell?: (value: unknown, row: TData) => string;
}

export function toColumnDefs<TData>(columns: TableColumn<TData>[]): ColumnDef<TData>[] {
  return columns.map((column) => ({
    id: column.id,
    header: column.header,
    accessorFn: column.accessor,
    cell: (context) => {
      const value = context.getValue();
      const row = context.row.original;
      return column.cell === undefined ? String(value ?? '') : column.cell(value, row);
    }
  }));
}

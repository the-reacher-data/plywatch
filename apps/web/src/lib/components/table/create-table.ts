import {
  createTable,
  getCoreRowModel,
  type ColumnDef
} from '@tanstack/table-core';

export interface TableCellView {
  id: string;
  value: string;
}

export interface TableRowView<TData> {
  id: string;
  original: TData;
  cells: TableCellView[];
}

export interface TableView<TData> {
  headers: string[];
  rows: TableRowView<TData>[];
}

export function buildTableView<TData>(
  data: TData[],
  columns: ColumnDef<TData>[],
  rowId: (item: TData) => string,
): TableView<TData> {
  const table = createTable<TData>({
    data,
    columns,
    state: {},
    onStateChange: () => undefined,
    renderFallbackValue: null,
    getCoreRowModel: getCoreRowModel()
  });

  return {
    headers: columns.map((column) => String(column.header ?? '')),
    rows: table.getRowModel().rows.map((row) => ({
      id: rowId(row.original),
      original: row.original,
      cells: row.getAllCells().map((cell) => ({
        id: cell.id,
        value: String(cell.getValue() ?? '')
      }))
    }))
  };
}

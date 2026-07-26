import type { ReactNode } from "react";

export interface DataColumn<T> {
  title: ReactNode;
  dataIndex?: keyof T;
  key: string;
  align?: "left" | "center" | "right";
  width?: number;
  fixed?: "left";
  sorter?: (left: T, right: T) => number;
  render?: (value: never, record: T, index: number) => ReactNode;
}

interface DataTableProps<T> {
  label: string;
  columns: DataColumn<T>[];
  data: T[];
  rowKey: keyof T | ((record: T) => string);
  minimumWidth: "medium" | "wide";
  emptyText?: ReactNode;
}

export function DataTable<T>({
  label,
  columns,
  data,
  rowKey,
  minimumWidth,
  emptyText = "暂无数据"
}: DataTableProps<T>) {
  return (
    <div
      className={`data-table-scroll data-table-${minimumWidth}`}
      role="region"
      aria-label={label}
      tabIndex={0}
    >
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={`align-${column.align ?? "left"}`}>
                {column.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length ? (
            data.map((record, rowIndex) => (
              <tr key={typeof rowKey === "function" ? rowKey(record) : String(record[rowKey])}>
                {columns.map((column) => {
                  const value = column.dataIndex ? record[column.dataIndex] : undefined;
                  return (
                    <td key={column.key} className={`align-${column.align ?? "left"}`}>
                      {column.render
                        ? column.render(value as never, record, rowIndex)
                        : String(value ?? "—")}
                    </td>
                  );
                })}
              </tr>
            ))
          ) : (
            <tr>
              <td className="data-table-empty" colSpan={columns.length}>{emptyText}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

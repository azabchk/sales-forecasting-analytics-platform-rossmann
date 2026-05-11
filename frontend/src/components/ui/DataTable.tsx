import React from "react";

// ─── Simple children-passthrough (backward compat) ──────────────────────────

type DataTableProps = {
  children: React.ReactNode;
};

export default function DataTable({ children }: DataTableProps) {
  return (
    <div className="table-wrap">
      <table className="table">{children}</table>
    </div>
  );
}

// ─── Smart table with sort / search / pagination ─────────────────────────────

export type SortDirection = "asc" | "desc" | null;

export type SmartColumn<T> = {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  searchable?: boolean;
  render?: (value: unknown, row: T, index: number) => React.ReactNode;
  width?: string;
  align?: "left" | "center" | "right";
};

type SmartTableProps<T extends Record<string, unknown>> = {
  columns: SmartColumn<T>[];
  data: T[];
  pageSize?: number;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyMessage?: string;
  rowKey?: (row: T, index: number) => string | number;
  onRowClick?: (row: T) => void;
  selectedKey?: string | number | null;
  rowKeyField?: keyof T;
  className?: string;
  compact?: boolean;
};

export function SmartTable<T extends Record<string, unknown>>({
  columns,
  data,
  pageSize = 10,
  searchable = false,
  searchPlaceholder = "Search…",
  emptyMessage = "No records found.",
  rowKey,
  onRowClick,
  selectedKey,
  rowKeyField,
  className = "",
  compact = false,
}: SmartTableProps<T>) {
  const [search, setSearch] = React.useState("");
  const [sortKey, setSortKey] = React.useState<string | null>(null);
  const [sortDir, setSortDir] = React.useState<SortDirection>(null);
  const [page, setPage] = React.useState(0);

  // Reset page when search changes
  React.useEffect(() => {
    setPage(0);
  }, [search, sortKey, sortDir]);

  const searchableKeys = React.useMemo(
    () => columns.filter((c) => c.searchable !== false).map((c) => c.key as string),
    [columns]
  );

  const filtered = React.useMemo(() => {
    if (!search.trim()) return data;
    const q = search.toLowerCase();
    return data.filter((row) =>
      searchableKeys.some((key) => {
        const val = row[key];
        return val != null && String(val).toLowerCase().includes(q);
      })
    );
  }, [data, search, searchableKeys]);

  const sorted = React.useMemo(() => {
    if (!sortKey || !sortDir) return filtered;
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const paged = sorted.slice(safePage * pageSize, safePage * pageSize + pageSize);

  function handleSort(key: string) {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortKey(null);
      setSortDir(null);
    }
  }

  function getKey(row: T, index: number): string | number {
    if (rowKey) return rowKey(row, index);
    if (rowKeyField) return row[rowKeyField as string] as string | number;
    return index;
  }

  const sortIcon = (key: string) => {
    if (sortKey !== key) return <span className="sort-icon unsorted" aria-hidden="true">⇅</span>;
    return <span className="sort-icon sorted" aria-hidden="true">{sortDir === "asc" ? "↑" : "↓"}</span>;
  };

  return (
    <div className={`smart-table-wrap ${className}`.trim()}>
      {searchable && (
        <div className="smart-table-toolbar">
          <div className="smart-table-search-wrap">
            <svg className="smart-table-search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10 10l2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              className="input smart-table-search"
              placeholder={searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label={searchPlaceholder}
            />
            {search && (
              <button
                className="smart-table-clear-btn"
                type="button"
                aria-label="Clear search"
                onClick={() => setSearch("")}
              >
                ✕
              </button>
            )}
          </div>
          <span className="smart-table-count">
            {filtered.length} / {data.length}
          </span>
        </div>
      )}

      <div className="table-wrap">
        <table className={`table${compact ? " table-compact" : ""}`}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  style={{ width: col.width, textAlign: col.align ?? "left" }}
                  className={col.sortable !== false ? "th-sortable" : ""}
                  onClick={col.sortable !== false ? () => handleSort(String(col.key)) : undefined}
                  aria-sort={
                    sortKey === String(col.key)
                      ? sortDir === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <span className="th-inner">
                    {col.label}
                    {col.sortable !== false && sortIcon(String(col.key))}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-empty">
                  {search ? `No results for "${search}"` : emptyMessage}
                </td>
              </tr>
            ) : (
              paged.map((row, idx) => {
                const key = getKey(row, safePage * pageSize + idx);
                const isSelected = selectedKey != null && key === selectedKey;
                return (
                  <tr
                    key={key}
                    className={`${onRowClick ? "table-row-clickable" : ""}${isSelected ? " table-row-active" : ""}`}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    onKeyDown={
                      onRowClick
                        ? (e) => {
                            if (e.key === "Enter" || e.key === " ") onRowClick(row);
                          }
                        : undefined
                    }
                  >
                    {columns.map((col) => {
                      const rawVal = row[col.key as string];
                      const cell = col.render
                        ? col.render(rawVal, row, safePage * pageSize + idx)
                        : (rawVal as React.ReactNode);
                      return (
                        <td key={String(col.key)} style={{ textAlign: col.align ?? "left" }}>
                          {cell}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination-row">
          <span className="pagination-info">
            {safePage * pageSize + 1}–{Math.min(safePage * pageSize + pageSize, sorted.length)} of {sorted.length}
          </span>
          <div className="pagination-controls">
            <button
              className="button ghost pagination-btn"
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage(0)}
              aria-label="First page"
            >
              «
            </button>
            <button
              className="button ghost pagination-btn"
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage((p) => p - 1)}
              aria-label="Previous page"
            >
              ‹
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const start = Math.max(0, Math.min(safePage - 2, totalPages - 5));
              const p = start + i;
              return (
                <button
                  key={p}
                  className={`button pagination-btn ${p === safePage ? "primary" : "ghost"}`}
                  type="button"
                  onClick={() => setPage(p)}
                  aria-label={`Page ${p + 1}`}
                  aria-current={p === safePage ? "page" : undefined}
                >
                  {p + 1}
                </button>
              );
            })}
            <button
              className="button ghost pagination-btn"
              type="button"
              disabled={safePage === totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next page"
            >
              ›
            </button>
            <button
              className="button ghost pagination-btn"
              type="button"
              disabled={safePage === totalPages - 1}
              onClick={() => setPage(totalPages - 1)}
              aria-label="Last page"
            >
              »
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

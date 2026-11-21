import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { http, visit } from "@lila";
import { Button } from "./Button";
import { cn } from "./cn";
import { Skeleton } from "./Feedback";
import { toast } from "./Toast";

export interface Column<T> {
  key: keyof T & string | string;
  label?: ReactNode;
  sortable?: boolean;
  /** Included in the local search (default: true for text/number values). */
  searchable?: boolean;
  align?: "left" | "center" | "right";
  render?: (row: T) => ReactNode;
  /** Value used for sorting/searching when `render` returns markup. */
  value?: (row: T) => string | number | null | undefined;
  hideOnMobile?: boolean;
  className?: string;
}

export interface DataTableProps<T> {
  /** Local mode: every row in memory (search/sort/paginate in the browser). */
  rows?: T[];
  /** Server mode: GET url?page=&per_page=&search=&sort=&order= (also limit/offset).
   *  Accepts paginate_async() {items, total}, {data, total}, or a plain list. */
  url?: string;
  params?: Record<string, string | number | boolean | undefined>;
  columns: Array<Column<T>>;
  rowKey?: keyof T & string;
  searchable?: boolean;
  pageSize?: number;
  pageSizes?: number[];
  defaultSort?: { key: string; desc?: boolean };
  /** Function, or a link pattern like "/users/:id/edit". */
  onEdit?: ((row: T) => void) | string;
  /** Function (may be async), or an API pattern like "/api/users/:id" (DELETE + CSRF). */
  onDelete?: ((row: T) => void | Promise<void>) | string;
  confirmDelete?: string | false;
  actions?: (row: T) => ReactNode;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  toolbar?: ReactNode;
  caption?: ReactNode;
  /** Change it to reload server data (e.g. after creating a row). */
  refreshKey?: unknown;
  labels?: Partial<Record<"search" | "previous" | "next" | "edit" | "delete" | "empty" | "of" | "rows", string>>;
  className?: string;
}

const DEFAULT_LABELS = { search: "Search...", previous: "Previous", next: "Next", edit: "Edit", delete: "Delete", empty: "No records found", of: "of", rows: "rows" };

function fill(pattern: string, row: any) {
  return pattern.replace(/:(\w+)/g, (_m, key) => encodeURIComponent(String(row?.[key] ?? "")));
}

function cellValue<T>(row: T, column: Column<T>): any {
  return column.value ? column.value(row) : (row as any)?.[column.key];
}

/** Normalizes Lila/REST list responses to {rows, total}. */
export function normalizeTableResponse<T>(body: any): { rows: T[]; total: number | null } {
  if (Array.isArray(body)) return { rows: body, total: null };
  const data = body?.data ?? body;
  if (Array.isArray(data)) return { rows: data, total: body?.total ?? body?.pagination?.total ?? null };
  const rows = data?.items ?? data?.rows ?? data?.data ?? [];
  return { rows: Array.isArray(rows) ? rows : [], total: data?.total ?? body?.total ?? null };
}

export function DataTable<T extends Record<string, any>>({
  rows, url, params, columns, rowKey = "id" as keyof T & string, searchable = true, pageSize = 10, pageSizes = [10, 25, 50],
  defaultSort, onEdit, onDelete, confirmDelete = "Delete this record?", actions, onRowClick, empty, toolbar, caption,
  refreshKey, labels: customLabels, className,
}: DataTableProps<T>) {
  const labels = { ...DEFAULT_LABELS, ...customLabels };
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState(defaultSort || null);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(pageSize);
  const [remote, setRemote] = useState<{ rows: T[]; total: number | null }>({ rows: [], total: 0 });
  const [loading, setLoading] = useState(Boolean(url));
  const [removed, setRemoved] = useState<Set<unknown>>(new Set());
  const [reload, setReload] = useState(0);

  // Debounced search.
  useEffect(() => {
    const id = window.setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, url ? 300 : 0);
    return () => window.clearTimeout(id);
  }, [search, url]);

  const paramsKey = JSON.stringify(params || {});
  useEffect(() => {
    if (!url) return undefined;
    const controller = new AbortController();
    const qs = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => v !== undefined && qs.set(k, String(v)));
    qs.set("page", String(page));
    qs.set("per_page", String(perPage));
    qs.set("limit", String(perPage));
    qs.set("offset", String((page - 1) * perPage));
    if (query) qs.set("search", query);
    if (sort) {
      qs.set("sort", sort.key);
      qs.set("order", sort.desc ? "desc" : "asc");
    }
    setLoading(true);
    http(`${url}${url.includes("?") ? "&" : "?"}${qs}`, { signal: controller.signal })
      .then((body) => setRemote(normalizeTableResponse<T>(body)))
      .catch((error) => {
        if (error?.name !== "AbortError") toast.error(error.message || "Error");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [url, page, perPage, query, sort, paramsKey, refreshKey, reload]);

  const local = useMemo(() => {
    if (url) return null;
    let list = (rows || []).filter((row) => !removed.has(row[rowKey]));
    if (query) {
      const needle = query.toLowerCase();
      list = list.filter((row) =>
        columns.some((col) => col.searchable !== false && String(cellValue(row, col) ?? "").toLowerCase().includes(needle)),
      );
    }
    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      list = [...list].sort((a, b) => {
        const x = col ? cellValue(a, col) : a[sort.key];
        const y = col ? cellValue(b, col) : b[sort.key];
        const order = typeof x === "number" && typeof y === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""), undefined, { numeric: true });
        return sort.desc ? -order : order;
      });
    }
    return list;
  }, [url, rows, removed, query, sort, columns, rowKey]);

  const total = local ? local.length : remote.total;
  const visible = local ? local.slice((page - 1) * perPage, page * perPage) : remote.rows.filter((row) => !removed.has(row[rowKey]));
  const pages = total === null ? null : Math.max(1, Math.ceil(total / perPage));
  const hasNext = pages === null ? remote.rows.length >= perPage : page < pages;

  useEffect(() => {
    if (pages !== null && page > pages) setPage(pages);
  }, [pages, page]);

  const toggleSort = (key: string) =>
    setSort((current) => (!current || current.key !== key ? { key } : current.desc ? null : { key, desc: true }));

  const remove = useCallback(async (row: T) => {
    if (confirmDelete && !window.confirm(confirmDelete)) return;
    try {
      if (typeof onDelete === "string") {
        const res: any = await http(fill(onDelete, row), { method: "DELETE" });
        toast.success(res?.message || res?.msg || labels.delete);
      } else {
        await onDelete?.(row);
      }
      setRemoved((prev) => new Set(prev).add(row[rowKey]));
      if (url) setReload((n) => n + 1);
    } catch (error: any) {
      toast.error(error?.message || "Error");
    }
  }, [confirmDelete, onDelete, rowKey, url, labels.delete]);

  const hasActions = Boolean(onEdit || onDelete || actions);
  const align = (a?: string) => (a === "right" ? "text-right" : a === "center" ? "text-center" : "");

  return (
    <div className={cn("card overflow-hidden", className)}>
      {(searchable || toolbar) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
          {searchable && (
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={labels.search}
              aria-label={labels.search} className="form-control max-w-xs py-2" />
          )}
          {toolbar && <div className="flex gap-2">{toolbar}</div>}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="table-lila">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col" className={cn(align(col.align), col.hideOnMobile && "hidden md:table-cell")}
                  aria-sort={sort?.key === col.key ? (sort.desc ? "descending" : "ascending") : undefined}>
                  {col.sortable ? (
                    <button type="button" onClick={() => toggleSort(col.key)} className="inline-flex items-center gap-1 uppercase hover:text-primary">
                      {col.label ?? col.key}
                      <span aria-hidden="true">{sort?.key === col.key ? (sort.desc ? "↓" : "↑") : "↕"}</span>
                    </button>
                  ) : (col.label ?? col.key)}
                </th>
              ))}
              {hasActions && <th className="text-right" scope="col"><span className="sr-only">Actions</span></th>}
            </tr>
          </thead>
          <tbody>
            {loading && !visible.length
              ? Array.from({ length: Math.min(perPage, 5) }).map((_, i) => (
                  <tr key={`s${i}`}>
                    {columns.map((col) => <td key={col.key}><Skeleton /></td>)}
                    {hasActions && <td />}
                  </tr>
                ))
              : visible.map((row, i) => (
                  <tr key={String(row[rowKey] ?? i)} onClick={onRowClick ? () => onRowClick(row) : undefined} className={cn(onRowClick && "cursor-pointer")}>
                    {columns.map((col) => (
                      <td key={col.key} className={cn(align(col.align), col.hideOnMobile && "hidden md:table-cell", col.className)}>
                        {col.render ? col.render(row) : String(cellValue(row, col) ?? "")}
                      </td>
                    ))}
                    {hasActions && (
                      <td className="text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <div className="inline-flex gap-1">
                          {actions?.(row)}
                          {onEdit && (
                            <Button size="sm" variant="ghost" onClick={() => (typeof onEdit === "string" ? visit(fill(onEdit, row)) : onEdit(row))}>
                              {labels.edit}
                            </Button>
                          )}
                          {onDelete && <Button size="sm" variant="ghost" className="text-danger" onClick={() => remove(row)}>{labels.delete}</Button>}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
            {!loading && !visible.length && (
              <tr>
                <td colSpan={columns.length + (hasActions ? 1 : 0)} className="py-10 text-center text-muted-foreground">{empty ?? labels.empty}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }} className="form-control w-auto py-1.5" aria-label={labels.rows}>
            {pageSizes.map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
          <span>{total !== null ? `${total ? (page - 1) * perPage + 1 : 0}–${Math.min(page * perPage, total)} ${labels.of} ${total}` : `${labels.rows} ${page}`}</span>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>{labels.previous}</Button>
          <Button size="sm" variant="outline" disabled={!hasNext || loading} onClick={() => setPage((p) => p + 1)}>{labels.next}</Button>
        </div>
      </div>
    </div>
  );
}

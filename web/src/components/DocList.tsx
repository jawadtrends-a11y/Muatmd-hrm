"use client";

/**
 * قائمة مستندات — الأساس الذي تُبنى عليه كل شاشة قوائم.
 *
 * 🔑 درس RTL من المحاسبي: الخلية باتجاه المستند، والرقم معزول
 * بـ<span className="num"> — لا تضع className="num" على الخلية.
 *
 * 🔑 لا يُعرَّف مكوّن داخل مكوّن (ضياع التركيز بعد كل حرف).
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { apiGet, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcPlus, IcSearch } from "@/components/Icons";

const T: Dict = {
  search: { ar: "بحث…", en: "Search…" },
  empty: { ar: "لا نتائج", en: "No results" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  error: { ar: "تعذّر تحميل البيانات", en: "Failed to load" },
  retry: { ar: "إعادة المحاولة", en: "Retry" },
  total: { ar: "الإجمالي", en: "Total" },
  rows: { ar: "سجل", en: "records" },
};

export type Column<R> = {
  key: string;
  label: { ar: string; en: string };
  /** عرض العمود بالبكسل — الجدول بـtable-layout: fixed */
  width?: number;
  /** رقم: يُعزل بـ<span className="num"> ويُحاذى للنهاية */
  numeric?: boolean;
  render?: (row: R) => React.ReactNode;
};

export type Stat = {
  label: { ar: string; en: string };
  value: string | number;
  tone?: "default" | "ok" | "warn" | "danger";
};

type Props<R> = {
  /** مسار الـAPI — يُنادى مع الفلاتر */
  endpoint: string;
  columns: Column<R>[];
  /** مفتاح فريد لكل صف */
  rowKey: (row: R) => string | number;
  /** فلاتر تُرسل مع الطلب */
  filters?: Record<string, unknown>;
  /** شريط فلاتر مخصّص فوق الجدول */
  filterBar?: React.ReactNode;
  /** بطاقات مجاميع */
  stats?: (rows: R[]) => Stat[];
  /** بحث محلي في الصفوف */
  searchable?: boolean;
  searchFields?: (row: R) => string;
  /** زر الإضافة */
  newHref?: string;
  newLabel?: { ar: string; en: string };
  onRowClick?: (row: R) => void;
  /** يُعاد التحميل عند تغيّره */
  refreshKey?: unknown;
  emptyHint?: { ar: string; en: string };
};

export default function DocList<R>({
  endpoint,
  columns,
  rowKey,
  filters,
  filterBar,
  stats,
  searchable = true,
  searchFields,
  newHref,
  newLabel,
  onRowClick,
  refreshKey,
  emptyHint,
}: Props<R>) {
  const { L, lang } = useT(T);

  const [rows, setRows] = useState<R[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [reload, setReload] = useState(0);

  const query = useMemo(() => qs(filters || {}), [filters]);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError("");

    apiGet<R[] | { rows?: R[]; data?: R[] }>(`${endpoint}${query}`)
      .then((res) => {
        if (!alive) return;
        const list = Array.isArray(res)
          ? res
          : (res.rows ?? res.data ?? []);
        setRows(list as R[]);
        setBusy(false);
      })
      .catch((e: ApiError) => {
        if (!alive) return;
        setError(e.message || L("error"));
        setBusy(false);
      });

    return () => {
      alive = false;
    };
  }, [endpoint, query, refreshKey, reload, L]);

  const visible = useMemo(() => {
    if (!search.trim() || !searchFields) return rows;
    const q = search.trim().toLowerCase();
    return rows.filter((r) => searchFields(r).toLowerCase().includes(q));
  }, [rows, search, searchFields]);

  const cards = stats?.(visible) ?? [];

  return (
    <div className="stack">
      {/* بطاقات المجاميع */}
      {cards.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: `repeat(auto-fit, minmax(170px, 1fr))`,
          gap: 12,
        }}>
          {cards.map((s, i) => (
            <div key={i} className="card" style={{ padding: "14px 16px" }}>
              <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
                {s.label[lang]}
              </div>
              <div style={{
                fontSize: "1.45rem", fontWeight: 600,
                color: s.tone === "ok" ? "var(--ok)"
                  : s.tone === "warn" ? "var(--copper)"
                  : s.tone === "danger" ? "var(--danger)"
                  : "var(--ink)",
              }}>
                <span className="num">{s.value}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* شريط الأدوات */}
      <div className="row" style={{ flexWrap: "wrap" }}>
        {searchable && searchFields && (
          <div style={{ position: "relative", minWidth: 220, flex: "0 1 300px" }}>
            <span style={{
              position: "absolute", insetInlineStart: 11, top: 10,
              color: "var(--ink-3)", pointerEvents: "none",
            }}>
              <IcSearch size={17} />
            </span>
            <input
              className="input"
              style={{ paddingInlineStart: 36 }}
              placeholder={L("search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        )}

        {filterBar}
        <div className="grow" />

        {newHref && (
          <Link href={newHref} className="btn btn-primary">
            <IcPlus size={17} />
            {newLabel?.[lang] || "+"}
          </Link>
        )}
      </div>

      {/* الجدول */}
      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : error ? (
          <div style={{ padding: 32, textAlign: "center" }}>
            <div style={{ color: "var(--danger)", marginBottom: 12 }}>
              <IcAlert size={22} />
              <div style={{ marginTop: 6 }}>{error}</div>
            </div>
            <button className="btn btn-sm" onClick={() => setReload((n) => n + 1)}>
              {L("retry")}
            </button>
          </div>
        ) : visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <div>{L("empty")}</div>
            {emptyHint && (
              <div style={{ marginTop: 6, fontSize: ".88rem" }}>
                {emptyHint[lang]}
              </div>
            )}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                {columns.map((c) => (
                  <col key={c.key} style={{ width: c.width ? `${c.width}px` : undefined }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} style={{
                      textAlign: c.numeric ? "end" : "start",
                    }}>
                      {c.label[lang]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={rowKey(row)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    style={{ cursor: onRowClick ? "pointer" : undefined }}
                  >
                    {columns.map((c) => {
                      const raw = c.render
                        ? c.render(row)
                        : ((row as Record<string, unknown>)[c.key] as React.ReactNode);
                      return (
                        <td key={c.key} style={{
                          textAlign: c.numeric ? "end" : "start",
                        }}>
                          {c.numeric && raw != null && raw !== "" ? (
                            <span className="num">{raw}</span>
                          ) : (
                            raw ?? "—"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!busy && !error && visible.length > 0 && (
        <div className="muted" style={{ fontSize: ".85rem" }}>
          {L("total")}: <span className="num">{visible.length}</span> {L("rows")}
        </div>
      )}
    </div>
  );
}

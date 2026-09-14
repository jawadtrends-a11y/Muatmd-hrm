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

/** ق-166: أحجام الصفحة المتاحة (قرار جواد) */
const PAGE_SIZES = [10, 25, 50, 100];
import Link from "next/link";

import { apiGet, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcPlus, IcSearch } from "@/components/Icons";

const T: Dict = {
  search: { ar: "بحث…", en: "Search…" },
  empty: { ar: "لا نتائج", en: "No results" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  listView: { ar: "عرض قائمة", en: "List view" },
  cardsView: { ar: "عرض بطاقات", en: "Card view" },
  error: { ar: "تعذّر تحميل البيانات", en: "Failed to load" },
  retry: { ar: "إعادة المحاولة", en: "Retry" },
  total: { ar: "الإجمالي", en: "Total" },
  rows: { ar: "سجل", en: "records" },
  page: { ar: "صفحة", en: "Page" },
  perPage: { ar: "في الصفحة", en: "Per page" },
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
  /** ق-155: أزرارٌ إضافية بجانب «جديد» — كالاستيراد */
  actions?: React.ReactNode;
  /**
   * ق-155: عرضٌ بالبطاقات — **والمبدّل يظهر إن وُجدت**.
   *
   * ⚠️ فشاشةٌ بلا بطاقةٍ معرَّفة لا تُظهر زرًّا لا يفعل شيئًا.
   */
  cardView?: (row: R) => React.ReactNode;
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
  actions,
  cardView,
  onRowClick,
  refreshKey,
  emptyHint,
}: Props<R>) {
  const { L, lang } = useT(T);

  const [rows, setRows] = useState<R[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  // ق-155: طريقة العرض — **وتُحفظ فلا تُنسى بالتحديث** (بلاغ
  // جواد): فمن اختار البطاقات يجدها كما تركها.
  //
  // ⚠️ **ومفتاحُها بالمسار**: فاختيارُه في الموظفين لا يقلب
  // شاشةً أخرى.
  const [view, setView] = useState<"list" | "cards">("list");

  // ق-166: **حجم الصفحة** (بلاغ جواد) — ⚠️ فشركةٌ بألف موظف
  // **لا تُعرض في صفحةٍ واحدة**، والمستخدم يختار ما يناسبه.
  //
  // ⚠️ **ويُحفظ بالمسار** كطريقة العرض: فمن اختار ١٠٠ لا يعود
  // لعشرة في كل فتح.
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const v = Number(window.localStorage.getItem(
        `doclist-size:${endpoint}`));
      if (PAGE_SIZES.includes(v)) setPageSize(v);
    } catch { /* الوضع الخاصّ يمنعه */ }
  }, [endpoint]);

  const pickSize = (n: number) => {
    setPageSize(n);
    setPage(1);
    try {
      window.localStorage.setItem(`doclist-size:${endpoint}`,
                                  String(n));
    } catch { /* يُتجاهل */ }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem(
        `doclist-view:${endpoint}`);
      if (saved === "cards" || saved === "list") setView(saved);
    } catch { /* الوضع الخاصّ يمنعه — والافتراض يكفي */ }
  }, [endpoint]);

  const pickView = (v: "list" | "cards") => {
    setView(v);
    try {
      window.localStorage.setItem(`doclist-view:${endpoint}`, v);
    } catch { /* يُتجاهل */ }
  };
  const [meta, setMeta] = useState<
    { total: number; pages: number } | null>(null);
  const [reload, setReload] = useState(0);

  // ق-166: ⚠️ **والصفحة تُطلب من الخادم** — فالترقيم في العميل
  // يُرسل الكلّ ثم يقطّعه، **وذاك يثقل عند الألوف** (قرار جواد).
  // ق-167: ⚠️⚠️ **والبحث في الخادم لا العميل** (بلاغ جواد):
  // فالعميل لا يملك إلا صفحته — **وبحثٌ فيها يُخفي من في الصفحات
  // الأخرى**.
  //
  // ⚠️ **وبمهلةٍ قصيرة**: فطلبٌ مع كل حرفٍ يُثقل الخادم.
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const query = useMemo(
    () => qs({
      ...(filters || {}), page, page_size: pageSize,
      ...(debounced ? { q: debounced } : {}),
    }),
    [filters, page, pageSize, debounced]);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError("");

    apiGet<R[] | { rows?: R[]; data?: R[];
                   meta?: { total: number; pages: number } }>(
      `${endpoint}${query}`)
      .then((res) => {
        if (!alive) return;
        const list = Array.isArray(res)
          ? res
          : (res.rows ?? res.data ?? []);
        setRows(list as R[]);
        // ⚠️ **ومسارٌ بلا ترقيمٍ يعمل كما كان**: فـ`meta` غائبةٌ
        // فيُقطَّع محلّيًّا — **فلا نكسر ما لم نُرقّمه بعد**.
        setMeta(Array.isArray(res) ? null : (res.meta ?? null));
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
    // ⚠️ L مستثناة عمدًا: دالة الترجمة تتغيّر مرجعيًا في كل رسم،
    // فإدراجها يعيد إطلاق الطلب بلا نهاية — الجدول يظهر ثم يختفي.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, query, refreshKey, reload]);

  const visible = useMemo(() => {
    // ⚠️ **ولا ترشيحَ محلّيّ حين رشّح الخادم**: فترشيحٌ ثانٍ على
    // الصفحة **يُخفي نتائجَ صحيحة**.
    if (meta !== null) return rows;
    if (!search.trim() || !searchFields) return rows;
    const q = search.trim().toLowerCase();
    return rows.filter((r) => searchFields(r).toLowerCase().includes(q));
  }, [rows, search, searchFields]);

  // ⚠️ **والمجاميع على الكلّ لا الصفحة**: فـ«الموظفون ١٠»
  // في شركةٍ بألف **رقمٌ خاطئ**.
  const cards = stats?.(visible) ?? [];

  // ⚠️ **والترقيم من الخادم إن رقّم** — وإلا محلّيًّا.
  const serverPaged = meta !== null;
  const totalCount = serverPaged ? meta!.total : visible.length;
  const totalPages = serverPaged
    ? Math.max(1, meta!.pages)
    : Math.max(1, Math.ceil(visible.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const paged = useMemo(
    () => (serverPaged
      ? visible
      : visible.slice((safePage - 1) * pageSize, safePage * pageSize)),
    [visible, safePage, pageSize, serverPaged]);

  // ⚠️ **والبحث يُرجع للصفحة الأولى**: فنتيجةٌ في الصفحة الخامسة
  // تبدو مفقودة.
  useEffect(() => { setPage(1); }, [debounced]);

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

        {actions}

        {newHref && (
          <Link href={newHref} className="btn btn-primary">
            <IcPlus size={17} />
            {newLabel?.[lang] || "+"}
          </Link>
        )}
      </div>

      {/* ق-155: مبدّل العرض — ولا يظهر إلا لمن عرّف بطاقته */}
      {cardView && (
        <div className="row" style={{ gap: 4 }}>
          <button
            className={`btn btn-sm ${view === "list" ? "btn-primary" : "btn-ghost"}`}
            title={L("listView")}
            onClick={() => pickView("list")}
            style={{ minWidth: 40, padding: "6px 10px" }}>
            ☰
          </button>
          <button
            className={`btn btn-sm ${view === "cards" ? "btn-primary" : "btn-ghost"}`}
            title={L("cardsView")}
            onClick={() => pickView("cards")}
            style={{ minWidth: 40, padding: "6px 10px" }}>
            ▦
          </button>
        </div>
      )}

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
        ) : cardView && view === "cards" ? (
          /* ق-155: البطاقات — شبكةٌ تتكيّف مع العرض */
          <div style={{
            display: "grid", gap: 12, padding: 14,
            gridTemplateColumns:
              "repeat(auto-fill, minmax(240px, 1fr))",
          }}>
            {paged.map((r) => (
              <div key={String(rowKey(r))}
                   onClick={() => onRowClick?.(r)}
                   style={{
                     border: "1px solid var(--line)",
                     borderRadius: "var(--radius-sm)",
                     padding: 14,
                     cursor: onRowClick ? "pointer" : "default",
                     background: "var(--paper)",
                   }}>
                {cardView(r)}
              </div>
            ))}
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
                {paged.map((row) => (
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

      {/* ق-166: **شريط الترقيم وحجم الصفحة** (بلاغ جواد) */}
      {!busy && !error && visible.length > 0 && (
        <div className="spread" style={{ flexWrap: "wrap", gap: 10 }}>
          <div className="muted" style={{ fontSize: ".85rem" }}>
            {L("total")}:{" "}
            <span className="num">{totalCount}</span> {L("rows")}
            {totalPages > 1 && (
              <> · {L("page")}{" "}
                <span className="num">{safePage}</span>/
                <span className="num">{totalPages}</span>
              </>
            )}
          </div>

          <div className="row" style={{ gap: 10, alignItems: "center" }}>
            {/* ⚠️ **ولا يظهر التنقّل بصفحةٍ واحدة** — فزرٌّ
                معطَّل يُربك */}
            {totalPages > 1 && (
              <div className="row" style={{ gap: 4 }}>
                <button className="btn btn-sm btn-ghost"
                        disabled={safePage <= 1}
                        onClick={() => setPage(safePage - 1)}>
                  {lang === "ar" ? "›" : "‹"}
                </button>
                <button className="btn btn-sm btn-ghost"
                        disabled={safePage >= totalPages}
                        onClick={() => setPage(safePage + 1)}>
                  {lang === "ar" ? "‹" : "›"}
                </button>
              </div>
            )}

            <div className="row" style={{ gap: 6,
                                          alignItems: "center" }}>
              <span className="muted" style={{ fontSize: ".8rem" }}>
                {L("perPage")}
              </span>
              <select className="select" value={pageSize}
                      style={{ width: 78, padding: "5px 8px" }}
                      onChange={(e) => pickSize(Number(e.target.value))}>
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

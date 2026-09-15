"use client";
/**
 * أرصدة الإجازات (ق-172).
 *
 * **بلاغ جواد:** «وين صفحة أرصدة الإجازة لمتابعتها من المشرفين
 * والمديرين والموارد؟»
 *
 * ⚠️ **والنطاق يحسم**: فالمشرف يرى فريقه، والموارد الشركة —
 * **والبوّابة تفعلها، لا شرطٌ هنا**.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أرصدة الإجازات", en: "Leave balances" },
  sub: {
    ar: "المستحق والمستهلك والمتبقّي — يُحتسب حتى اليوم",
    en: "Accrued, used and available — as of today",
  },
  employee: { ar: "الموظف", en: "Employee" },
  department: { ar: "الإدارة", en: "Department" },
  opening: { ar: "افتتاحيّ", en: "Opening" },
  accrued: { ar: "المستحق", en: "Accrued" },
  consumed: { ar: "المستهلك", en: "Used" },
  available: { ar: "المتبقّي", en: "Available" },
  search: { ar: "بحث بالاسم أو الرقم أو الإدارة", en: "Search" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا موظفين", en: "No employees" },
  noTypes: {
    ar: "لا أنواع إجازاتٍ تعاقدية — علّم نوعًا «رصيدًا تعاقديًّا» من إعداداته",
    en: "No contractual leave types",
  },
  total: { ar: "الإجمالي", en: "Total" },
  rows: { ar: "موظفًا", en: "employees" },
  perPage: { ar: "في الصفحة", en: "Per page" },
  page: { ar: "صفحة", en: "Page" },
};

const SIZES = [10, 25, 50, 100];

type Cell = {
  leave_type_id: number; code: string;
  opening: string; accrued: string; consumed: string;
  available: string;
};
type Row = {
  employment_id: number; employee_no: string; name_ar: string;
  department: string; balances: Cell[];
};
type LType = { id: number; code: string; name_ar: string };

export default function LeaveBalancesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [types, setTypes] = useState<LType[]>([]);
  const [meta, setMeta] = useState<
    { total: number; pages: number; page: number } | null>(null);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  // ⚠️ **وبمهلةٍ قصيرة** — فطلبٌ مع كل حرفٍ يُثقل الخادم
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => { setPage(1); }, [debounced, size]);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const d = await apiGet<{
        rows: Row[]; types: LType[];
        meta: { total: number; pages: number; page: number };
      }>(`/leaves/balances/team/${qs({
        page, page_size: size,
        ...(debounced ? { q: debounced } : {}),
      })}`);
      setRows(d.rows || []);
      setTypes(d.types || []);
      setMeta(d.meta || null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [page, size, debounced]);

  useEffect(() => { load(); }, [load]);

  const cell = (r: Row, typeId: number) =>
    r.balances.find((b) => b.leave_type_id === typeId);

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <IcAlert /> {error}
        </div>
      )}

      <input className="input" style={{ maxWidth: 380 }}
             value={search} placeholder={L("search")}
             onChange={(e) => setSearch(e.target.value)} />

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>{L("loading")}</div>
        ) : types.length === 0 ? (
          <div style={{ padding: 36, textAlign: "center",
                        color: "var(--ink-3)", lineHeight: 1.9 }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("noTypes")}</div>
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>{L("empty")}</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 180 }}>{L("employee")}</th>
                  <th style={{ width: 150 }}>{L("department")}</th>
                  {types.map((t) => (
                    <th key={t.id} colSpan={4}
                        style={{ textAlign: "center" }}>
                      {t.name_ar}
                    </th>
                  ))}
                </tr>
                <tr>
                  <th /><th />
                  {types.map((t) => (
                    <>
                      <th key={`${t.id}-o`} style={{ width: 90,
                        fontSize: ".78rem" }}>{L("opening")}</th>
                      <th key={`${t.id}-a`} style={{ width: 90,
                        fontSize: ".78rem" }}>{L("accrued")}</th>
                      <th key={`${t.id}-c`} style={{ width: 90,
                        fontSize: ".78rem" }}>{L("consumed")}</th>
                      <th key={`${t.id}-v`} style={{ width: 95,
                        fontSize: ".78rem" }}>{L("available")}</th>
                    </>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.employment_id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.name_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>
                        {r.employee_no}
                      </div>
                    </td>
                    <td className="muted">{r.department || "—"}</td>
                    {types.map((t) => {
                      const c = cell(r, t.id);
                      const avail = Number(c?.available ?? 0);
                      return (
                        <>
                          <td key={`${t.id}-o`}>
                            <span className="num muted">
                              {c?.opening ?? "—"}
                            </span>
                          </td>
                          <td key={`${t.id}-a`}>
                            <span className="num">
                              {c?.accrued ?? "—"}
                            </span>
                          </td>
                          <td key={`${t.id}-c`}>
                            <span className="num muted">
                              {c?.consumed ?? "—"}
                            </span>
                          </td>
                          <td key={`${t.id}-v`}>
                            {/* ⚠️ **والمتبقّي بارز** — فهو ما
                                يُبحث عنه */}
                            <span className="num" style={{
                              fontWeight: 600,
                              color: avail <= 0 ? "var(--danger)"
                                : undefined }}>
                              {c?.available ?? "—"}
                            </span>
                          </td>
                        </>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!busy && meta && rows.length > 0 && (
        <div className="spread" style={{ flexWrap: "wrap", gap: 10 }}>
          <div className="muted" style={{ fontSize: ".85rem" }}>
            {L("total")}: <span className="num">{meta.total}</span>{" "}
            {L("rows")}
            {meta.pages > 1 && (
              <> · {L("page")}{" "}
                <span className="num">{meta.page}</span>/
                <span className="num">{meta.pages}</span></>
            )}
          </div>
          <div className="row" style={{ gap: 10, alignItems: "center" }}>
            {meta.pages > 1 && (
              <div className="row" style={{ gap: 4 }}>
                <button className="btn btn-sm btn-ghost"
                        disabled={meta.page <= 1}
                        onClick={() => setPage(meta.page - 1)}>›</button>
                <button className="btn btn-sm btn-ghost"
                        disabled={meta.page >= meta.pages}
                        onClick={() => setPage(meta.page + 1)}>‹</button>
              </div>
            )}
            <div className="row" style={{ gap: 6, alignItems: "center" }}>
              <span className="muted" style={{ fontSize: ".8rem" }}>
                {L("perPage")}
              </span>
              <select className="select" value={size}
                      style={{ width: 78, padding: "5px 8px" }}
                      onChange={(e) => setSize(Number(e.target.value))}>
                {SIZES.map((n) => (
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

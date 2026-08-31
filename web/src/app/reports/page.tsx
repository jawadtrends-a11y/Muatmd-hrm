"use client";

/**
 * شاشة التقارير (ق-40).
 *
 * الواجهة تُبنى تلقائيًا من المعايير التي يعلنها كل تقرير —
 * فإضافة تقرير في الخادم تظهر هنا بلا كتابة سطر واجهة.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { apiGet, downloadFile, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcChart, IcDownload, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "التقارير", en: "Reports" },
  subtitle: {
    ar: "تُصدَّر إلى إكسل أو PDF",
    en: "Exportable to Excel or PDF",
  },
  run: { ar: "عرض", en: "Run" },
  running: { ar: "جارٍ التشغيل…", en: "Running…" },
  excel: { ar: "إكسل", en: "Excel" },
  pdf: { ar: "PDF", en: "PDF" },
  back: { ar: "رجوع للقائمة", en: "Back to list" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا بيانات", en: "No data" },
  rows: { ar: "سجل", en: "records" },
  total: { ar: "الإجمالي", en: "Total" },
  truncated: {
    ar: "عُرض جزء من النتائج — صدّر الملف للحصول عليها كاملة",
    en: "Partial results shown — export for the full set",
  },
  required: { ar: "مطلوب", en: "required" },
  selectReport: { ar: "اختر تقريرًا", en: "Select a report" },
  notes: { ar: "ملاحظات", en: "Notes" },
};

type Param = {
  key: string;
  label_ar: string;
  kind: string;
  required: boolean;
  default: unknown;
  options: { value: string; label: string }[];
  help_ar: string;
};

type ReportMeta = {
  key: string;
  title_ar: string;
  permission: string;
  params: Param[];
};

type Group = {
  group: string;
  group_ar: string;
  reports: ReportMeta[];
};

type ReportResult = {
  key: string;
  title_ar: string;
  subtitle_ar: string;
  company: string;
  columns: { key: string; label_ar: string; kind: string; total: boolean }[];
  rows: Record<string, unknown>[];
  totals: Record<string, string>;
  row_count: number;
  truncated: boolean;
  notes: string[];
};

function fmt(value: unknown, kind: string): string {
  if (value == null || value === "") return "—";
  if (kind === "money" || kind === "number") {
    const n = Number(value);
    return Number.isFinite(n)
      ? n.toLocaleString("en-US", { minimumFractionDigits: kind === "money" ? 2 : 0,
                                    maximumFractionDigits: 2 })
      : String(value);
  }
  return String(value);
}


/* ══ نموذج المعايير — يُبنى من params تلقائيًا ══ */

function ParamField({
  param, value, onChange, L,
}: {
  param: Param;
  value: string;
  onChange: (v: string) => void;
  L: (k: string, f?: string) => string;
}) {
  const label = (
    <label className="label">
      {param.label_ar}
      {param.required && (
        <span style={{ color: "var(--danger)", marginInlineStart: 4 }}>*</span>
      )}
    </label>
  );

  if (param.kind === "select") {
    return (
      <div className="field" style={{ minWidth: 170 }}>
        {label}
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          {param.options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        {param.help_ar && <div className="hint">{param.help_ar}</div>}
      </div>
    );
  }

  if (param.kind === "bool") {
    return (
      <div className="field" style={{ minWidth: 150 }}>
        {label}
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          <option value="true">نعم</option>
          <option value="false">لا</option>
        </select>
      </div>
    );
  }

  return (
    <div className="field" style={{ minWidth: 160, maxWidth: 200 }}>
      {label}
      <input
        className="input"
        type={param.kind === "date" ? "date" : "text"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {param.help_ar && <div className="hint">{param.help_ar}</div>}
    </div>
  );
}

/* ══ جدول النتائج ══ */

function ResultTable({
  result, L,
}: {
  result: ReportResult;
  L: (k: string, f?: string) => string;
}) {
  if (result.rows.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("empty")}
      </div>
    );
  }

  const hasTotals = Object.keys(result.totals).length > 0;

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <thead>
          <tr>
            {result.columns.map((c) => (
              <th key={c.key} style={{
                textAlign: c.kind === "money" || c.kind === "number"
                  ? "end" : "start",
              }}>
                {c.label_ar}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {result.columns.map((c) => {
                const numeric = c.kind === "money" || c.kind === "number";
                const text = fmt(row[c.key], c.kind);
                return (
                  <td key={c.key}
                    style={{ textAlign: numeric ? "end" : "start" }}>
                    {numeric && text !== "—"
                      ? <span className="num">{text}</span>
                      : text}
                  </td>
                );
              })}
            </tr>
          ))}

          {hasTotals && (
            <tr style={{
              background: "var(--paper-2)", fontWeight: 600,
            }}>
              {result.columns.map((c, i) => (
                <td key={c.key} style={{
                  textAlign: c.total ? "end" : i === 0 ? "start" : "end",
                }}>
                  {i === 0 ? L("total")
                    : c.total && result.totals[c.key]
                    ? <span className="num">
                        {fmt(result.totals[c.key], "money")}
                      </span>
                    : ""}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}


/* ══ الشاشة ══ */

export default function ReportsPage() {
  const { L } = useT(T);

  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<ReportMeta | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ReportResult | null>(null);
  const [busy, setBusy] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<{ groups: Group[] }>("/reports/")
      .then((d) => { setGroups(d.groups); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });
  }, []);

  const pick = useCallback((r: ReportMeta) => {
    setSelected(r);
    setResult(null);
    setError("");
    const init: Record<string, string> = {};
    for (const p of r.params) {
      init[p.key] = p.default != null ? String(p.default) : "";
    }
    setValues(init);
  }, []);

  const missing = useMemo(
    () => (selected?.params ?? []).filter(
      (p) => p.required && !values[p.key]?.trim()),
    [selected, values],
  );

  async function run() {
    if (!selected || missing.length > 0) return;
    setRunning(true);
    setError("");
    try {
      setResult(await apiGet<ReportResult>(
        `/reports/${selected.key}/${qs(values)}`));
    } catch (e) {
      setError((e as ApiError).message);
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  async function exportAs(format: "xlsx" | "pdf") {
    if (!selected) return;
    try {
      await downloadFile(
        `/reports/${selected.key}/${qs({ ...values, export: format })}`);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  /* ── قائمة التقارير ── */
  if (!selected) {
    return (
      <div className="stack">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".9rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>

        {error && (
          <div style={{
            background: "var(--danger-soft)", color: "var(--danger)",
            padding: "10px 14px", borderRadius: "var(--radius-sm)",
          }}>
            {error}
          </div>
        )}

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 16,
        }}>
          {groups.map((g) => (
            <div key={g.group} className="card" style={{ padding: 18 }}>
              <h2 style={{
                fontSize: "1rem", color: "var(--teal)", marginBottom: 12,
              }}>
                {g.group_ar}
              </h2>
              <div className="stack" style={{ gap: 2 }}>
                {g.reports.map((r) => (
                  <button
                    key={r.key}
                    className="btn btn-ghost"
                    style={{ justifyContent: "flex-start", height: 36 }}
                    onClick={() => pick(r)}
                  >
                    <IcDoc size={17} />
                    {r.title_ar}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ── تقرير مختار ── */
  return (
    <div className="stack">
      <div className="spread">
        <div>
          <button className="btn btn-sm btn-ghost"
            onClick={() => { setSelected(null); setResult(null); }}>
            ← {L("back")}
          </button>
          <h1 style={{ marginTop: 8 }}>{selected.title_ar}</h1>
          {result?.subtitle_ar && (
            <div className="muted" style={{ fontSize: ".9rem" }}>
              {result.subtitle_ar}
            </div>
          )}
        </div>

        {result && result.rows.length > 0 && (
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-sm" onClick={() => exportAs("xlsx")}>
              <IcDownload size={16} />
              {L("excel")}
            </button>
            <button className="btn btn-sm" onClick={() => exportAs("pdf")}>
              <IcDownload size={16} />
              {L("pdf")}
            </button>
          </div>
        )}
      </div>

      {/* المعايير */}
      <div className="card" style={{ padding: 18 }}>
        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          {selected.params.map((p) => (
            <ParamField
              key={p.key}
              param={p}
              value={values[p.key] ?? ""}
              onChange={(v) => setValues((s) => ({ ...s, [p.key]: v }))}
              L={L}
            />
          ))}
          <button
            className="btn btn-primary"
            onClick={run}
            disabled={running || missing.length > 0}
          >
            <IcChart size={17} />
            {running ? L("running") : L("run")}
          </button>
        </div>

        {missing.length > 0 && (
          <div className="hint" style={{ marginTop: 10, color: "var(--copper)" }}>
            {missing.map((p) => p.label_ar).join("، ")} — {L("required")}
          </div>
        )}
      </div>

      {error && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
        }}>
          <IcAlert size={17} /> {error}
        </div>
      )}

      {result && (
        <>
          <div className="card" style={{ overflow: "hidden" }}>
            <ResultTable result={result} L={L} />
          </div>

          <div className="spread">
            <span className="muted" style={{ fontSize: ".85rem" }}>
              {L("total")}: <span className="num">{result.row_count}</span>{" "}
              {L("rows")}
            </span>
            {result.truncated && (
              <span className="badge badge-warn">{L("truncated")}</span>
            )}
          </div>

          {result.notes.length > 0 && (
            <div className="card" style={{ padding: 16 }}>
              <div className="muted" style={{
                fontSize: ".82rem", marginBottom: 6,
              }}>
                {L("notes")}
              </div>
              {result.notes.map((n, i) => (
                <div key={i} className="muted" style={{ fontSize: ".88rem" }}>
                  • {n}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

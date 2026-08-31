"use client";

/**
 * تفاصيل المسير — التبويبات الستة (ق-40).
 *
 * شاشات اطلاع لا تُصدَّر: ملخص · كشف الرواتب · المستبعدون ·
 * الحسومات · التأمينات · المقارنة. والتصدير لمُدد والبنك منفصل.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { apiGet, apiPost, downloadFile, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDownload } from "@/components/Icons";

const T: Dict = {
  back: { ar: "رجوع", en: "Back" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا بيانات", en: "No data" },
  // التبويبات
  summary: { ar: "ملخص", en: "Summary" },
  payslips: { ar: "كشف الرواتب", en: "Payslips" },
  excluded: { ar: "المستبعدون", en: "Excluded" },
  adjustments: { ar: "الحسومات والإضافات", en: "Adjustments" },
  gosi: { ar: "التأمينات", en: "GOSI" },
  comparison: { ar: "المقارنة", en: "Comparison" },
  // الملخص
  netTotal: { ar: "صافي الأجور", en: "Net total" },
  deductionsTotal: { ar: "الحسومات", en: "Deductions" },
  overtimeTotal: { ar: "الإضافي", en: "Overtime" },
  basicTotal: { ar: "الرواتب الأساسية", en: "Basic salaries" },
  allowancesTotal: { ar: "البدلات", en: "Allowances" },
  deductionBreakdown: { ar: "توزيع الحسومات", en: "Deductions breakdown" },
  // الأعمدة
  employee: { ar: "الموظف", en: "Employee" },
  reason: { ar: "السبب", en: "Reason" },
  amount: { ar: "المبلغ", en: "Amount" },
  explanation: { ar: "الاحتساب", en: "Calculation" },
  basic: { ar: "الأساسي", en: "Basic" },
  gross: { ar: "الاستحقاقات", en: "Gross" },
  deductions: { ar: "الاستقطاعات", en: "Deductions" },
  net: { ar: "الصافي", en: "Net" },
  inWps: { ar: "حماية الأجور", en: "WPS" },
  variance: { ar: "فرق", en: "Variance" },
  type: { ar: "النوع", en: "Type" },
  percent: { ar: "النسبة", en: "Percent" },
  // التأمينات
  saudis: { ar: "حسومات السعوديين", en: "Saudi employees" },
  nonSaudis: { ar: "حسومات غير السعوديين", en: "Non-Saudi employees" },
  employerShare: { ar: "مساهمة المنشأة", en: "Employer contribution" },
  totalDue: { ar: "إجمالي المستحق", en: "Total due" },
  // المقارنة
  previousNet: { ar: "الشهر السابق", en: "Previous" },
  currentNet: { ar: "الشهر الحالي", en: "Current" },
  difference: { ar: "الفرق", en: "Difference" },
  // التصدير
  exports: { ar: "التصدير", en: "Exports" },
  wpsFile: { ar: "ملف حماية الأجور", en: "WPS file" },
  bankFile: { ar: "ملف البنك", en: "Bank file" },
  exportHint: {
    ar: "التصدير متاح بعد اعتماد المسير",
    en: "Export available after approval",
  },
  excludedCount: { ar: "مستبعدون", en: "Excluded" },
  ready: { ar: "جاهز للإرسال", en: "Ready" },
  notReady: { ar: "يحتاج مراجعة", en: "Needs review" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

const TABS = ["summary", "payslips", "excluded", "adjustments",
              "gosi", "comparison"] as const;
type Tab = (typeof TABS)[number];

type Overview = {
  summary: {
    run_no: string;
    period: string;
    run_type: string;
    status: string;
    employee_count: number;
    headline: Record<string, string>;
    deduction_breakdown: { type: string; amount: string; percent: string }[];
    addition_breakdown: { type: string; amount: string; percent: string }[];
    variance_count: number;
    error_count: number;
  };
  tab_counts: Record<string, number>;
  can_export: boolean;
};

function money(v: string | number) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                 maximumFractionDigits: 2 })
    : String(v);
}


/* ══ جدول عام لتبويبات المسير — خارج المكوّن الرئيسي ══ */

type Col = {
  key: string;
  label: string;
  numeric?: boolean;
  width?: number;
  render?: (row: Record<string, unknown>) => React.ReactNode;
};

function TabTable({
  rows, cols, empty,
}: {
  rows: Record<string, unknown>[];
  cols: Col[];
  empty: string;
}) {
  if (!rows || rows.length === 0) {
    return (
      <div style={{ padding: 36, textAlign: "center", color: "var(--ink-3)" }}>
        {empty}
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <colgroup>
          {cols.map((c) => (
            <col key={c.key}
              style={{ width: c.width ? `${c.width}px` : undefined }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key}
                style={{ textAlign: c.numeric ? "end" : "start" }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const raw = c.render ? c.render(row) : row[c.key];
                return (
                  <td key={c.key}
                    style={{ textAlign: c.numeric ? "end" : "start" }}>
                    {c.numeric && raw != null && raw !== "" ? (
                      <span className="num">{raw as React.ReactNode}</span>
                    ) : (
                      (raw as React.ReactNode) ?? "—"
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ══ بطاقات الملخص ══ */

function SummaryCards({
  data, L,
}: {
  data: Overview["summary"];
  L: (k: string, f?: string) => string;
}) {
  const h = data.headline;
  const cards: { key: string; value: string; tone?: string }[] = [
    { key: "netTotal", value: h.net_total },
    { key: "deductionsTotal", value: h.deductions_total, tone: "var(--danger)" },
    { key: "overtimeTotal", value: h.overtime_total, tone: "var(--ok)" },
    { key: "basicTotal", value: h.basic_total },
    { key: "allowancesTotal", value: h.allowances_total },
  ];

  return (
    <>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
        gap: 12,
      }}>
        {cards.map((c) => (
          <div key={c.key} className="card" style={{ padding: "14px 16px" }}>
            <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
              {L(c.key)}
            </div>
            <div style={{
              fontSize: "1.35rem", fontWeight: 600,
              color: c.tone || "var(--ink)",
            }}>
              <span className="num">{money(c.value)}</span>
            </div>
          </div>
        ))}
      </div>

      {data.deduction_breakdown.length > 0 && (
        <div className="card" style={{ padding: 18, marginTop: 16 }}>
          <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>
            {L("deductionBreakdown")}
          </h3>
          <div className="stack" style={{ gap: 10 }}>
            {data.deduction_breakdown.map((d) => (
              <div key={d.type}>
                <div className="spread" style={{ marginBottom: 4 }}>
                  <span>{d.type}</span>
                  <span>
                    <span className="num">{money(d.amount)}</span>
                    <span className="muted" style={{ marginInlineStart: 8 }}>
                      <span className="num">{d.percent}</span>%
                    </span>
                  </span>
                </div>
                <div style={{
                  height: 6, background: "var(--paper-3)", borderRadius: 999,
                  overflow: "hidden",
                }}>
                  <div style={{
                    width: `${d.percent}%`, height: "100%",
                    background: "var(--teal)",
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}


/* ══ الشاشة ══ */

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { L } = useT(T);
  const runId = Number(params.id);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [tabData, setTabData] = useState<Record<string, unknown>[]>([]);
  const [busy, setBusy] = useState(true);
  const [tabBusy, setTabBusy] = useState(false);
  const [error, setError] = useState("");
  const [templates, setTemplates] = useState<{ id: number; name_ar: string }[]>([]);

  useEffect(() => {
    apiGet<Overview>(`/payroll/runs/${runId}/overview/`)
      .then((d) => { setOverview(d); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });

    apiGet<{ id: number; name_ar: string }[]>("/payroll/bank-templates/")
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, [runId]);

  const loadTab = useCallback(async (t: Tab) => {
    if (t === "summary") return;
    setTabBusy(true);
    try {
      const res = await apiGet<{ data: Record<string, unknown>[] }>(
        `/payroll/runs/${runId}/tab/${t}/`);
      setTabData(res.data || []);
    } catch {
      setTabData([]);
    } finally {
      setTabBusy(false);
    }
  }, [runId]);

  useEffect(() => { loadTab(tab); }, [tab, loadTab]);

  const cols: Record<Tab, Col[]> = {
    summary: [],
    payslips: [
      { key: "employee_no", label: "#", numeric: true, width: 90 },
      { key: "name", label: L("employee"), width: 210 },
      { key: "basic", label: L("basic"), numeric: true, width: 120 },
      { key: "gross", label: L("gross"), numeric: true, width: 130 },
      { key: "deductions", label: L("deductions"), numeric: true, width: 130 },
      { key: "net", label: L("net"), numeric: true, width: 130 },
      { key: "in_wps", label: L("inWps"), width: 110,
        render: (r) => (
          <span className={r.in_wps ? "badge badge-ok" : "badge"}>
            {r.in_wps ? L("yes") : L("no")}
          </span>
        ) },
      { key: "has_variance", label: L("variance"), width: 90,
        render: (r) => r.has_variance
          ? <span className="badge badge-warn">!</span> : "—" },
    ],
    excluded: [
      { key: "employee_no", label: "#", numeric: true, width: 90 },
      { key: "name", label: L("employee"), width: 220 },
      { key: "status", label: L("type"), width: 140 },
      { key: "reason", label: L("reason"), width: 380 },
    ],
    adjustments: [
      { key: "employee_no", label: "#", numeric: true, width: 90 },
      { key: "name", label: L("employee"), width: 190 },
      { key: "type", label: L("type"), width: 100 },
      { key: "reason", label: L("reason"), width: 180 },
      { key: "amount", label: L("amount"), numeric: true, width: 120 },
      { key: "explanation", label: L("explanation"), width: 340 },
    ],
    gosi: [],
    comparison: [
      { key: "employee_no", label: "#", numeric: true, width: 90 },
      { key: "name", label: L("employee"), width: 200 },
      { key: "previous_net", label: L("previousNet"), numeric: true, width: 130 },
      { key: "current_net", label: L("currentNet"), numeric: true, width: 130 },
      { key: "difference", label: L("difference"), numeric: true, width: 130,
        render: (r) => {
          const v = Number(r.difference);
          return (
            <span style={{
              color: v < 0 ? "var(--danger)" : v > 0 ? "var(--ok)" : undefined,
            }}>
              {money(r.difference as string)}
            </span>
          );
        } },
      { key: "status", label: L("type"), width: 150 },
    ],
  };

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--danger)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{error || L("empty")}</div>
      </div>
    );
  }

  const s = overview.summary;

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <button className="btn btn-sm btn-ghost"
            onClick={() => router.push("/payroll")}>
            ← {L("back")}
          </button>
          <h1 style={{ marginTop: 8 }}>
            <span className="num">{s.run_no}</span>
          </h1>
          <div className="muted" style={{ fontSize: ".9rem" }}>
            <span className="num">{s.period}</span> · {s.run_type} · {s.status}
          </div>
        </div>

        {overview.can_export && (
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-sm"
              onClick={() => downloadFile(`/payroll/runs/${runId}/wps/download/`)}>
              <IcDownload size={16} />
              {L("wpsFile")}
            </button>
            {templates.map((t) => (
              <button key={t.id} className="btn btn-sm"
                onClick={() => downloadFile(
                  `/payroll/runs/${runId}/bank/${t.id}/download/`)}>
                <IcDownload size={16} />
                {t.name_ar}
              </button>
            ))}
          </div>
        )}
      </div>

      {!overview.can_export && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "9px 14px", borderRadius: "var(--radius-sm)",
          fontWeight: 500, fontSize: ".9rem",
        }}>
          {L("exportHint")}
        </div>
      )}

      {/* التبويبات */}
      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {TABS.map((t) => {
          const n = overview.tab_counts[t];
          return (
            <button key={t}
              className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setTab(t)}>
              {L(t)}
              {n != null && n > 0 && (
                <span className="num" style={{ opacity: .75 }}>({n})</span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "summary" ? (
        <SummaryCards data={s} L={L} />
      ) : tab === "gosi" ? (
        <GosiPanel runId={runId} L={L} />
      ) : (
        <div className="card" style={{ overflow: "hidden" }}>
          {tabBusy ? (
            <div style={{ padding: 36, textAlign: "center", color: "var(--ink-3)" }}>
              {L("loading")}
            </div>
          ) : (
            <TabTable rows={tabData} cols={cols[tab]} empty={L("empty")} />
          )}
        </div>
      )}
    </div>
  );
}

/* ══ لوحة التأمينات ══ */

function GosiPanel({
  runId, L,
}: {
  runId: number;
  L: (k: string, f?: string) => string;
}) {
  const [data, setData] = useState<Record<string, string> | null>(null);

  useEffect(() => {
    apiGet<{ data: Record<string, string> }>(
      `/payroll/runs/${runId}/tab/gosi/`)
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, [runId]);

  if (!data) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  const cards = [
    { key: "saudis", value: data.employee_saudi },
    { key: "nonSaudis", value: data.employee_non_saudi },
    { key: "employerShare", value: data.employer_contribution },
    { key: "totalDue", value: data.total_due, strong: true },
  ];

  return (
    <div className="stack">
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
        gap: 12,
      }}>
        {cards.map((c) => (
          <div key={c.key} className="card" style={{ padding: "16px 18px" }}>
            <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
              {L(c.key)}
            </div>
            <div style={{
              fontSize: c.strong ? "1.5rem" : "1.3rem", fontWeight: 600,
              color: c.strong ? "var(--teal)" : "var(--ink)",
            }}>
              <span className="num">{money(c.value)}</span>
            </div>
          </div>
        ))}
      </div>

      {data.note && (
        <div className="muted" style={{ fontSize: ".88rem" }}>
          {data.note}
        </div>
      )}
    </div>
  );
}

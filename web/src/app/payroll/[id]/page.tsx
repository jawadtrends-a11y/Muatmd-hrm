"use client";

/**
 * تفاصيل المسير — التبويبات الستة (ق-40).
 *
 * شاشات اطلاع لا تُصدَّر: ملخص · كشف الرواتب · المستبعدون ·
 * الحسومات · التأمينات · المقارنة. والتصدير لمُدد والبنك منفصل.
 */
import { useUrlTab } from "@/lib/useUrlTab";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { apiGet, apiPost, downloadFile, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDownload } from "@/components/Icons";

const T: Dict = {
  cancel: { ar: "إلغاء", en: "Cancel" },
  back: { ar: "رجوع", en: "Back" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا بيانات", en: "No data" },
  // التبويبات
  summary: { ar: "ملخص", en: "Summary" },
  payslips: { ar: "كشف الرواتب", en: "Payslips" },
  defer: { ar: "تأجيل", en: "Defer" },
  chain: { ar: "سلسلة الاعتماد", en: "Approval chain" },
  chainDone: { ar: "اكتملت", en: "Complete" },
  chainApprove: { ar: "اعتماد الخطوة", en: "Approve step" },
  chainReject: { ar: "رفض", en: "Reject" },
  chainReason: { ar: "سبب الرفض", en: "Rejection reason" },
  deferTitle: { ar: "تأجيل بند", en: "Defer a line" },
  deferHint: {
    ar: "⚠️ الراتب وبدلاته لا تُؤجَّل — أجرٌ مستحقٌّ في موعده",
    en: "Salary cannot be deferred",
  },
  line: { ar: "البند", en: "Line" },
  toMonth: { ar: "إلى شهر", en: "To month" },
  toYear: { ar: "إلى سنة", en: "To year" },
  deferReason: { ar: "السبب", en: "Reason" },
  noDeferrable: {
    ar: "لا بنود قابلة للتأجيل في هذه القسيمة",
    en: "No deferrable lines",
  },
  deferred: { ar: "أُجِّل البند", en: "Line deferred" },
  excluded: { ar: "المستبعدون", en: "Excluded" },
  adjustments: { ar: "الحسومات والإضافات", en: "Adjustments" },
  gosi: { ar: "التأمينات", en: "GOSI" },
  netSalary: { ar: "صافي الراتب", en: "Net salary" },
  additions: { ar: "الإضافي", en: "Additions" },
  netAmount: { ar: "صافي المبلغ", en: "Net amount" },
  days: { ar: "الأيام", en: "Days" },
  fullMonth: { ar: "شهر كامل", en: "Full month" },
  opDetails: { ar: "تفاصيل العمليات", en: "Details" },
  details: { ar: "تفاصيل", en: "Details" },
  warningsT: { ar: "تنبيهات", en: "Warnings" },
  noDed: { ar: "لا حسومات", en: "No deductions" },
  close: { ar: "إغلاق", en: "Close" },
  searchPh: { ar: "بحث بالاسم أو الرقم…", en: "Search name or number…" },
  allDepts: { ar: "كل الإدارات", en: "All departments" },
  fAll: { ar: "الكل", en: "All" },
  fWarn: { ar: "بتنبيهات", en: "With warnings" },
  fDed: { ar: "بحسومات", en: "With deductions" },
  fAdd: { ar: "بإضافي", en: "With additions" },
  fVar: { ar: "بتباين", en: "With variance" },
  fManual: { ar: "يدويّ", en: "Manual" },
  fAuto: { ar: "آليّ", en: "Automatic" },
  prevT: { ar: "السابق", en: "Previous" },
  currT: { ar: "الحالي", en: "Current" },
  countT: { ar: "عدد الموظفين", en: "Employees" },
  netDiff: { ar: "فرق الصافي", en: "Net change" },
  totalsT: { ar: "الإجماليّات", en: "Totals" },
  byDept: { ar: "الصافي بالإدارة", en: "Net by department" },
  topChanges: { ar: "أكبر التغيّرات", en: "Largest changes" },
  noPrev: { ar: "لا مسير سابق للمقارنة — تُعرض أرقام هذا المسير وحدها",
            en: "No previous run — showing this run only" },
  excludeT: { ar: "استبعاد", en: "Exclude" },
  excludeFrom: { ar: "استبعاد من المسير", en: "Exclude from run" },
  scopeRun: { ar: "هذا المسير فقط", en: "This run only" },
  scopeUntil: { ar: "حتى يُعاد يدويًّا", en: "Until restored" },
  reasonReq: { ar: "السبب (إلزامي)", en: "Reason (required)" },
  restore: { ar: "إعادة", en: "Restore" },
  byT: { ar: "بواسطة", en: "By" },
  scopeT: { ar: "النطاق", en: "Scope" },
  confirmT: { ar: "تأكيد", en: "Confirm" },
  salaryLines: { ar: "بنود الراتب", en: "Salary items" },
  noAdd: { ar: "لا إضافي", en: "No additions" },
  summaryT: { ar: "الخلاصة", en: "Summary" },
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
  glEntry: { ar: "قيد محاسبيّ", en: "GL entry" },
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
  const { L, lang } = useT(T);
  const runId = Number(params.id);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useUrlTab<Tab>(TABS, "summary");
  const [deferring, setDeferring] = useState<number | null>(null);
  const [slipInfo, setSlipInfo] = useState<Record<string, unknown> | null>(null);
  const [excl, setExcl] = useState<Record<string, unknown> | null>(null);
  const [exReason, setExReason] = useState("");
  const [exScope, setExScope] = useState<"run" | "until_revoked">("run");
  const [exErr, setExErr] = useState("");
  const [exBusy, setExBusy] = useState(false);
  // ق-152: قوالب القيد — وإخفاق الجلب قائمةٌ فارغة لا شاشة مكسورة
  // ق-177: ⚠️⚠️ **والتنزيل يعرض سببه** (بلاغ جواد): فالمنع
  // صحيحٌ — **لكنّ صمتَه خطأ**: «لا يعمل» أسوأ من «كل الموظفين
  // مستبعَدون من حماية الأجور».
  const [dlError, setDlError] = useState("");

  const grab = (path: string) => {
    setDlError("");
    downloadFile(path).catch((e) => {
      setDlError(e instanceof ApiError ? e.message : String(e));
      setTimeout(() => setDlError(""), 8000);
    });
  };

  const [glTemplates, setGlTemplates] = useState<
    { id: number; name_ar: string }[]>([]);
  const [tabData, setTabData] = useState<Record<string, unknown>[]>([]);
  const [busy, setBusy] = useState(true);
  const [tabBusy, setTabBusy] = useState(false);
  const [error, setError] = useState("");
  const [templates, setTemplates] = useState<{ id: number; name_ar: string; name_en?: string }[]>([]);

  useEffect(() => {
    apiGet<Overview>(`/payroll/runs/${runId}/overview/`)
      .then((d) => { setOverview(d); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });

    apiGet<{ id: number; name_ar: string; name_en?: string }[]>("/payroll/bank-templates/")
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, [runId]);

  const loadTab = useCallback(async (t: Tab) => {
    // ق-227: ⚠⚠ **والتأمينات لها لوحتها** (`GosiPanel`): فجلبُها
    // هنا ثانيةً **يضع كائنًا في `tabData`** — والتبويب التالي يُصيَّر
    // به قبل جلبه، و`.map` على كائن **يُسقط الصفحة كاملة**.
    if (t === "summary" || t === "gosi") return;
    setTabBusy(true);
    try {
      const res = await apiGet<{ data: Record<string, unknown>[] }>(
        `/payroll/runs/${runId}/tab/${t}/`);
      setTabData(Array.isArray(res.data) ? res.data : []);
    } catch {
      setTabData([]);
    } finally {
      setTabBusy(false);
    }
  }, [runId]);

  useEffect(() => { loadTab(tab); }, [tab, loadTab]);

  // ق-230: \u26a0 **البحث والفلترة في كل التبويبات** (بلاغ جواد) — في
  // المتصفّح على ما جُلب: فالتبويب يجلب صفوفه كاملة، والفلترة فوقها فورية.
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [quick, setQuick] = useState("");
  useEffect(() => { setQ(""); setDept(""); setQuick(""); }, [tab]);

  const qn = q.trim().toLowerCase();
  const qKey = tab === "adjustments" ? "type" : "status";
  const filtered = (tabData || []).filter((r) => {
    if (qn) {
      const hay = `${r.name ?? ""} ${r.employee_no ?? ""} ${r.reason ?? ""}`
        .toLowerCase();
      if (!hay.includes(qn)) return false;
    }
    if (dept && String(r.department ?? "") !== dept) return false;
    if (!quick) return true;
    if (tab === "payslips") {
      if (quick === "warn") return Number(r.warnings_count) > 0;
      if (quick === "ded") return Number(r.deductions) > 0;
      if (quick === "add") return Number(r.additions) > 0;
      if (quick === "var") return !!r.has_variance;
      return true;
    }
    if (tab === "excluded") return quick === "manual" ? !!r.manual : !r.manual;
    return String(r[qKey] ?? "") === quick;
  });
  const depts = Array.from(new Set((tabData || [])
    .map((r) => String(r.department ?? "")).filter(Boolean))).sort();
  const quickOpts: [string, string][] =
    tab === "payslips"
      ? [["warn", L("fWarn")], ["ded", L("fDed")], ["add", L("fAdd")],
         ["var", L("fVar")]]
      : tab === "excluded"
        ? [["manual", L("fManual")], ["auto", L("fAuto")]]
        : Array.from(new Set((tabData || [])
            .map((r) => String(r[qKey] ?? "")).filter(Boolean)))
            .map((v) => [v, v] as [string, string]);

  useEffect(() => {
    apiGet<{ templates: { id: number; name_ar: string }[] }>(
      "/payroll/gl/templates/")
      .then((d) => setGlTemplates(d.templates || []))
      .catch(() => setGlTemplates([]));
  }, []);

  const cols: Record<Tab, Col[]> = {
    summary: [],
    // ق-227: \u26a0\u26a0 **والكشف كان رقمًا بلا تفصيل** (بلاغ جواد):
    // فالحسومات بلا بنودها، والتنبيهات **في القسيمة ولا تُرى**،
    // والتأجيل ينادي `r.id` **والصفّ لا يحمل إلا `payslip_id`**.
    payslips: [
      { key: "name", label: L("employee"), width: 220,
        render: (r) => (
          <div>
            <div style={{ fontWeight: 600 }}>{String(r.name)}</div>
            <div className="muted num" style={{ fontSize: ".78rem" }}>
              {String(r.employee_no)}
            </div>
            {/* ق-227: والتنبيه بنصٍّ صريح تحت الاسم — فرقمٌ في عمودٍ
                بلا عنوان **يُقرأ من العمود المجاور** (بلاغ جواد) */}
            {Number(r.warnings_count) > 0 && (
              <button className="btn btn-ghost btn-sm"
                      onClick={() => setSlipInfo(r)}
                      style={{ padding: 0, height: "auto", fontSize: ".74rem",
                               color: "var(--copper)" }}>
                ⚠ {L("warningsT")} ({String(r.warnings_count)})
              </button>
            )}
          </div>
        ) },
      { key: "gross", label: L("gross"), numeric: true, width: 120 },
      { key: "net_salary", label: L("netSalary"), numeric: true, width: 120 },
      { key: "additions", label: L("additions"), numeric: true, width: 110,
        render: (r) => (
          <span style={{ color: "var(--ok)" }}>{String(r.additions)}</span>
        ) },
      { key: "deductions", label: L("deductions"), numeric: true, width: 130,
        render: (r) => {
          const n = ((r.deduction_lines as unknown[]) || []).length;
          return (
            <div>
              <div style={{ color: "var(--danger)" }}>{String(r.deductions)}</div>
              {n > 0 && (
                <button className="btn btn-ghost btn-sm"
                        style={{ fontSize: ".72rem", padding: 0, height: "auto" }}
                        onClick={() => setSlipInfo(r)}>
                  {L("opDetails")}
                </button>
              )}
            </div>
          );
        } },
      { key: "net", label: L("netAmount"), numeric: true, width: 130,
        render: (r) => <b className="num">{String(r.net)}</b> },
      { key: "worked_days", label: L("days"), numeric: true, width: 90,
        render: (r) => Number(r.worked_days) > 0
          ? <span className="num">{String(r.worked_days)}</span>
          : <span className="muted" style={{ fontSize: ".8rem" }}>{L("fullMonth")}</span> },
      { key: "actions", label: "", width: 170,
        render: (r) => (
          <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
            <button className="btn btn-sm" onClick={() => setSlipInfo(r)}>
              {L("details")}
            </button>
            <button className="btn btn-sm btn-ghost"
                    onClick={() => setDeferring(Number(r.payslip_id))}>
              {L("defer")}
            </button>
            <button className="btn btn-sm btn-ghost"
                    style={{ color: "var(--danger)" }}
                    onClick={() => { setExcl(r); setExReason("");
                                     setExScope("run"); setExErr(""); }}>
              {L("excludeT")}
            </button>
          </div>
        ) },
    ],
    // ق-228: والمستبعَد يدويًّا يُعرض بسببه ونطاقه وفاعله — ويُعاد
    excluded: [
      { key: "employee_no", label: "#", numeric: true, width: 90 },
      { key: "name", label: L("employee"), width: 200 },
      { key: "reason", label: L("reason"), width: 240 },
      { key: "scope", label: L("scopeT"), width: 140,
        render: (r) => r.scope ? String(r.scope) : "—" },
      { key: "by", label: L("byT"), width: 110,
        render: (r) => r.by ? String(r.by) : "—" },
      { key: "restore", label: "", width: 100,
        render: (r) => r.manual ? (
          <button className="btn btn-sm" onClick={async () => {
            try {
              await apiPost(`/payroll/exclusions/${r.exclusion_id}/revoke/`,
                            { run_id: runId });
              window.location.reload();
            } catch (e) { alert((e as ApiError).message); }
          }}>{L("restore")}</button>
        ) : null },
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
        {/* ق-177: ⚠️ **وسبب المنع يُعرض** — فالصمت يُقرأ عطلًا */}
      {dlError && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {dlError}
        </div>
      )}
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
              onClick={() => grab(`/payroll/runs/${runId}/wps/download/`)}>
              <IcDownload size={16} />
              {L("wpsFile")}
            </button>
            {templates.map((t) => (
              <button key={t.id} className="btn btn-sm"
                onClick={() => grab(
                  `/payroll/runs/${runId}/bank/${t.id}/download/`)}>
                <IcDownload size={16} />
                {(lang === "en" ? t.name_en : t.name_ar) || t.name_ar}
              </button>
            ))}
            {/* ق-180: ⚠️ **والزرّ باسم غرضه لا باسم قالبه**
                (بلاغ جواد): فـ«قالب عامّ» **أوهم أنه قالب تصدير
                المسير** — وهو قيدٌ محاسبيّ لنظام ERP. */}
            {glTemplates.map((t) => (
              <button key={`gl-${t.id}`} className="btn btn-sm"
                title={t.name_ar}
                onClick={() => grab(
                  `/payroll/runs/${runId}/gl/${t.id}/download/`)}>
                <IcDownload size={16} />
                {L("glEntry")}
                {glTemplates.length > 1 ? ` — ${t.name_ar}` : ""}
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
        <div className="stack">
        <div className="card" style={{ padding: 12 }}>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <input className="input" placeholder={L("searchPh")} value={q}
                   onChange={(e) => setQ(e.target.value)}
                   style={{ flex: "1 1 220px", minWidth: 180 }} />
            {depts.length > 1 && (
              <select className="input" value={dept} style={{ width: 180 }}
                      onChange={(e) => setDept(e.target.value)}>
                <option value="">{L("allDepts")}</option>
                {depts.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}
            {quickOpts.length > 0 && (
              <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
                <button className={`btn btn-sm ${!quick ? "btn-primary" : "btn-ghost"}`}
                        onClick={() => setQuick("")}>{L("fAll")}</button>
                {quickOpts.map(([v, lab]) => (
                  <button key={v} onClick={() => setQuick(v)}
                          className={`btn btn-sm ${quick === v ? "btn-primary" : "btn-ghost"}`}>
                    {lab}</button>
                ))}
              </div>
            )}
            <span className="muted num" style={{ fontSize: ".82rem",
                                                 marginInlineStart: "auto" }}>
              {filtered.length} / {(tabData || []).length}
            </span>
          </div>
        </div>
        <div className="card" style={{ overflow: "hidden" }}>
          {tabBusy ? (
            <div style={{ padding: 36, textAlign: "center", color: "var(--ink-3)" }}>
              {L("loading")}
            </div>
          ) : (
            <TabTable rows={filtered} cols={cols[tab]} empty={L("empty")} />
          )}
        </div>
        {/* ق-230: البحث ثم الجدول ثم الرسوم (قرار جواد) — فمن جاء
            يبحث عن موظفٍ يجده أولًا، والصورة الكاملة بعده */}
        {tab === "comparison" && <ComparisonCharts runId={runId} L={L} />}
        </div>
      )}

      {/* ق-140: سلسلة الاعتماد — من ينتظر يعرف عند من وقف */}
      <ChainStrip runId={runId} L={L} />

      {slipInfo && (() => {
        type Ln = { name: string; amount: string; explanation: string;
                    is_addition?: boolean };
        const earn = (slipInfo.earning_lines as Ln[]) || [];
        const fixed = earn.filter((x) => !x.is_addition);
        const adds = earn.filter((x) => x.is_addition);
        const deds = (slipInfo.deduction_lines as Ln[]) || [];
        const warns = (slipInfo.warnings as string[]) || [];
        const Section = ({ title, items, empty, color }: {
          title: string; items: Ln[]; empty: string; color?: string }) => (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8, fontSize: ".95rem" }}>
              {title}</div>
            {items.length === 0 ? (
              <div className="muted" style={{ fontSize: ".86rem" }}>{empty}</div>
            ) : items.map((d, k) => (
              <div key={k} className="spread" style={{
                padding: "7px 0", borderBottom: "1px solid var(--line)" }}>
                <div>
                  <div>{d.name}</div>
                  {d.explanation && (
                    <div className="muted" style={{ fontSize: ".76rem" }}>
                      {d.explanation}</div>)}
                </div>
                <span className="num" style={{ color }}>{d.amount}</span>
              </div>
            ))}
          </div>
        );
        const Row = ({ k, v, strong }: { k: string; v: unknown;
                                        strong?: boolean }) => (
          <div className="spread" style={{ padding: "5px 0",
                                           fontWeight: strong ? 700 : 400 }}>
            <span>{k}</span><span className="num">{String(v)}</span>
          </div>
        );
        return (
          <div onClick={() => setSlipInfo(null)} style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,.4)",
            display: "grid", placeItems: "center", zIndex: 60, padding: 16 }}>
            <div className="card" onClick={(e) => e.stopPropagation()}
                 style={{ padding: 24, width: "100%", maxWidth: 680,
                          maxHeight: "88vh", overflowY: "auto" }}>
              <div className="spread" style={{ marginBottom: 18 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>
                    {String(slipInfo.name)}</div>
                  <div className="muted num" style={{ fontSize: ".82rem" }}>
                    {String(slipInfo.employee_no)}
                    {slipInfo.department ? ` · ${String(slipInfo.department)}` : ""}
                  </div>
                </div>
                <b className="num" style={{ fontSize: "1.2rem" }}>
                  {String(slipInfo.net)}</b>
              </div>

              <Section title={L("salaryLines")} items={fixed} empty="—" />
              <Section title={L("additions")} items={adds} empty={L("noAdd")}
                       color="var(--ok)" />
              <Section title={L("deductions")} items={deds} empty={L("noDed")}
                       color="var(--danger)" />

              <div style={{ background: "var(--paper-2)", borderRadius:
                            "var(--radius-sm)", padding: "10px 14px",
                            marginBottom: 16 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>
                  {L("summaryT")}</div>
                <Row k={L("gross")} v={slipInfo.gross} />
                <Row k={L("netSalary")} v={slipInfo.net_salary} />
                <Row k={L("additions")} v={slipInfo.additions} />
                <Row k={L("deductions")} v={slipInfo.deductions} />
                <Row k={L("netAmount")} v={slipInfo.net} strong />
              </div>

              {warns.length > 0 && (
                <div style={{ background: "var(--copper-soft)", borderRadius:
                              "var(--radius-sm)", padding: "10px 14px",
                              marginBottom: 16 }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>
                    {L("warningsT")}</div>
                  <ul style={{ margin: 0, paddingInlineStart: 18,
                               fontSize: ".86rem" }}>
                    {warns.map((w, k) => <li key={k}>{w}</li>)}
                  </ul>
                </div>
              )}

              <button className="btn" onClick={() => setSlipInfo(null)}
                      style={{ width: "100%" }}>{L("close")}</button>
            </div>
          </div>
        );
      })()}

      {excl && (
        <div onClick={() => setExcl(null)} style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,.4)",
          display: "grid", placeItems: "center", zIndex: 60, padding: 16 }}>
          <div className="card" onClick={(e) => e.stopPropagation()}
               style={{ padding: 22, width: "100%", maxWidth: 480 }}>
            <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>
              {L("excludeFrom")}</div>
            <div className="muted" style={{ marginBottom: 14, fontSize: ".86rem" }}>
              {String(excl.name)} · {String(excl.employee_no)}</div>

            <div className="stack" style={{ gap: 8, marginBottom: 14 }}>
              {(["run", "until_revoked"] as const).map((v) => (
                <label key={v} className="row" style={{ gap: 8, cursor: "pointer" }}>
                  <input type="radio" checked={exScope === v}
                         onChange={() => setExScope(v)} />
                  {v === "run" ? L("scopeRun") : L("scopeUntil")}
                </label>
              ))}
            </div>

            <label className="label">{L("reasonReq")}</label>
            <textarea className="input" rows={3} value={exReason}
                      onChange={(e) => setExReason(e.target.value)}
                      style={{ width: "100%", marginBottom: 12 }} />

            {exErr && (
              <div style={{ background: "var(--danger-soft)", color: "var(--danger)",
                            padding: "8px 12px", borderRadius: "var(--radius-sm)",
                            marginBottom: 12, fontSize: ".86rem" }}>{exErr}</div>
            )}

            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setExcl(null)}>
                {L("close")}</button>
              <button className="btn btn-primary"
                      disabled={exBusy || !exReason.trim()}
                      style={{ background: "var(--danger)", borderColor: "var(--danger)" }}
                      onClick={async () => {
                        setExBusy(true); setExErr("");
                        try {
                          await apiPost(`/payroll/runs/${runId}/exclude/`, {
                            employment_id: excl.employment_id,
                            scope: exScope, reason: exReason.trim() });
                          window.location.reload();
                        } catch (e) {
                          setExErr((e as ApiError).message);
                        } finally { setExBusy(false); }
                      }}>
                {L("confirmT")}</button>
            </div>
          </div>
        </div>
      )}

      {deferring !== null && (
        <DeferDialog payslipId={deferring} L={L}
                     onClose={() => setDeferring(null)}
                     onSaved={() => { setDeferring(null);
                                      loadTab(tab); }} />
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


/* ══ نافذة تأجيل بند (ق-136) ══ */

function DeferDialog({ payslipId, L, onClose, onSaved }: {
  payslipId: number;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const now = new Date();
  const [lines, setLines] = useState<{ component_code: string;
                                       name_ar: string;
                                       amount: string }[]>([]);
  const [code, setCode] = useState("");
  const [year, setYear] = useState(String(now.getFullYear()));
  const [month, setMonth] = useState(String(now.getMonth() + 2));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiGet<{ lines: typeof lines }>(`/payslips/${payslipId}/deferrable/`)
      .then((d) => setLines(d.lines || []))
      .catch((e) => setErr(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [payslipId]);

  const submit = async () => {
    setSaving(true); setErr("");
    try {
      await apiPost("/deferrals/", {
        payslip_id: payslipId, component_code: code,
        to_year: Number(year), to_month: Number(month), reason,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("deferTitle")}</h3>
        <div className="muted" style={{ fontSize: ".8rem", marginTop: 4 }}>
          {L("deferHint")}
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        {busy ? (
          <div className="muted" style={{ marginTop: 18 }}>…</div>
        ) : lines.length === 0 ? (
          <div className="muted" style={{ marginTop: 18,
                                          textAlign: "center" }}>
            {L("noDeferrable")}
          </div>
        ) : (
          <div className="stack" style={{ gap: 12, marginTop: 16 }}>
            <label className="field">
              <span className="label">{L("line")}</span>
              <select className="select" value={code}
                      onChange={(e) => setCode(e.target.value)}>
                <option value="">—</option>
                {lines.map((l) => (
                  <option key={l.component_code} value={l.component_code}>
                    {l.name_ar} — {l.amount}
                  </option>
                ))}
              </select>
            </label>

            <div className="row" style={{ gap: 12 }}>
              <label className="field" style={{ width: 120 }}>
                <span className="label">{L("toYear")}</span>
                <input className="input num" type="number" value={year}
                       onChange={(e) => setYear(e.target.value)} />
              </label>
              <label className="field" style={{ width: 110 }}>
                <span className="label">{L("toMonth")}</span>
                <input className="input num" type="number" min={1} max={12}
                       value={month}
                       onChange={(e) => setMonth(e.target.value)} />
              </label>
            </div>

            <label className="field">
              <span className="label">{L("deferReason")}</span>
              <input className="input" value={reason}
                     onChange={(e) => setReason(e.target.value)} />
            </label>
          </div>
        )}

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          {lines.length > 0 && (
            <button className="btn btn-primary"
                    disabled={saving || !code || !reason.trim()}
                    onClick={submit}>
              {saving ? "…" : L("defer")}
            </button>
          )}
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


/* ══ شريط سلسلة الاعتماد (ق-140) ══ */

function ChainStrip({ runId, L }: {
  runId: number;
  L: (k: string, f?: string) => string;
}) {
  const [state, setState] = useState<{
    has_chain: boolean; current_step: number | null; completed: boolean;
    can_decide: boolean;
    steps: { step_order: number; title: string; role: string;
             decision: string; decided_by: string; note: string }[];
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setState(await apiGet(`/payroll/runs/${runId}/chain/`));
    } catch {
      setState(null);
    }
  }, [runId]);

  useEffect(() => { load(); }, [load]);

  const decide = async (approve: boolean) => {
    setBusy(true); setErr("");
    try {
      const note = approve ? "" : (prompt(L("chainReason")) || "");
      await apiPost(`/payroll/runs/${runId}/chain/`, { approve, note });
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  if (!state?.has_chain) return null;

  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="spread">
        <strong style={{ fontSize: ".92rem" }}>{L("chain")}</strong>
        {state.completed && (
          <span className="badge badge-ok">{L("chainDone")}</span>
        )}
      </div>

      {err && (
        <div style={{ color: "var(--danger)", fontSize: ".84rem",
                      marginTop: 8 }}>{err}</div>
      )}

      <div className="row" style={{ gap: 8, marginTop: 12,
                                    flexWrap: "wrap" }}>
        {state.steps.map((st) => (
          <div key={st.step_order} style={{
            padding: "8px 12px", borderRadius: "var(--radius-sm)",
            background: st.decision === "approved" ? "var(--ok-soft)"
              : st.decision === "rejected" ? "var(--danger-soft)"
              : st.step_order === state.current_step
                ? "var(--copper-soft)" : "var(--paper-2)",
            fontSize: ".84rem", minWidth: 150,
          }}>
            <div style={{ fontWeight: 500 }}>
              {st.step_order}. {st.title}
            </div>
            <div className="muted" style={{ fontSize: ".76rem" }}>
              {st.decided_by || st.role}
            </div>
            {st.note && (
              <div style={{ fontSize: ".75rem", marginTop: 3,
                            color: "var(--danger)" }}>{st.note}</div>
            )}
          </div>
        ))}
      </div>

      {state.can_decide && (
        <div className="row" style={{ gap: 8, marginTop: 14 }}>
          <button className="btn btn-sm btn-primary" disabled={busy}
                  onClick={() => decide(true)}>{L("chainApprove")}</button>
          <button className="btn btn-sm btn-danger" disabled={busy}
                  onClick={() => decide(false)}>{L("chainReject")}</button>
        </div>
      )}
    </div>
  );
}


/* ══ ق-230: رسوم المقارنة — بلا مكتبة: ألوان النظام والوضع الليلي تلقائيًّا ══ */

function ComparisonCharts({
  runId, L,
}: {
  runId: number;
  L: (k: string, f?: string) => string;
}) {
  type Tot = { count: number; gross: string; deductions: string; net: string };
  type Sum = {
    has_previous: boolean; previous_period: string; current_period: string;
    previous: Tot; current: Tot;
    by_department: { department: string; previous: string; current: string }[];
    top_changes: { name: string; employee_no: string; difference: string }[];
  };
  const [d, setD] = useState<Sum | null>(null);

  useEffect(() => {
    apiGet<{ data: Sum }>(`/payroll/runs/${runId}/tab/comparison_summary/`)
      .then((r) => setD(r.data)).catch(() => setD(null));
  }, [runId]);

  if (!d) return null;

  const n = (x: string | number) => Number(x) || 0;
  const fmt = (x: string | number) =>
    n(x).toLocaleString("en-US", { maximumFractionDigits: 2 });
  const PREV = "var(--copper)";
  const CURR = "var(--teal)";

  const Bar = ({ v, max, color }: { v: number; max: number; color: string }) => (
    <div style={{ background: "var(--paper-2)", borderRadius: 4, height: 12,
                  flex: 1, overflow: "hidden" }}>
      <div style={{ width: `${max > 0 ? Math.max(v ? 2 : 0, (Math.abs(v) / max) * 100) : 0}%`,
                    height: "100%", background: color, borderRadius: 4 }} />
    </div>
  );

  const metrics: [string, keyof Tot][] = [
    [L("gross"), "gross"], [L("deductions"), "deductions"], [L("netAmount"), "net"]];
  const mMax = Math.max(1, ...metrics.flatMap(([, k]) =>
    [n(d.previous[k]), n(d.current[k])]));
  const dMax = Math.max(1, ...d.by_department.flatMap((x) =>
    [n(x.previous), n(x.current)]));
  const cMax = Math.max(1, ...d.top_changes.map((x) => Math.abs(n(x.difference))));
  const diff = n(d.current.net) - n(d.previous.net);

  const Legend = () => (
    <div className="row" style={{ gap: 14, fontSize: ".78rem" }}>
      <span className="row" style={{ gap: 5 }}>
        <span style={{ width: 10, height: 10, background: PREV, borderRadius: 2 }} />
        {L("prevT")} {d.previous_period}</span>
      <span className="row" style={{ gap: 5 }}>
        <span style={{ width: 10, height: 10, background: CURR, borderRadius: 2 }} />
        {L("currT")} {d.current_period}</span>
    </div>
  );

  const kpis: [string, string, string?][] = [
    [L("countT"), `${d.current.count}`, d.has_previous ? `${d.previous.count}` : undefined],
    [L("netAmount"), fmt(d.current.net), d.has_previous ? fmt(d.previous.net) : undefined],
    [L("gross"), fmt(d.current.gross), d.has_previous ? fmt(d.previous.gross) : undefined],
    [L("netDiff"), d.has_previous ? `${diff > 0 ? "+" : ""}${fmt(diff)}` : "—"],
  ];

  return (
    <div className="stack">
      {!d.has_previous && (
        <div className="card" style={{ padding: "10px 14px",
                                       background: "var(--copper-soft)" }}>
          {L("noPrev")} ({d.previous_period})
        </div>
      )}

      <div style={{ display: "grid", gap: 12,
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        {kpis.map(([k, v, before], i) => (
          <div key={i} className="card" style={{ padding: 16 }}>
            <div className="muted" style={{ fontSize: ".8rem" }}>{k}</div>
            <div className="num" style={{ fontWeight: 700, fontSize: "1.25rem",
              color: i === 3 && d.has_previous
                ? (diff < 0 ? "var(--danger)" : "var(--ok)") : undefined }}>
              {v}</div>
            {before !== undefined && (
              <div className="muted num" style={{ fontSize: ".76rem" }}>
                {L("prevT")}: {before}</div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gap: 12,
                    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        <div className="card" style={{ padding: 16 }}>
          <div className="spread" style={{ marginBottom: 12 }}>
            <b>{L("totalsT")}</b><Legend />
          </div>
          {metrics.map(([label, k]) => (
            <div key={k} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: ".84rem", marginBottom: 4 }}>{label}</div>
              {d.has_previous && (
                <div className="row" style={{ gap: 8, marginBottom: 3 }}>
                  <Bar v={n(d.previous[k])} max={mMax} color={PREV} />
                  <span className="num muted" style={{ width: 100, fontSize: ".76rem" }}>
                    {fmt(d.previous[k])}</span>
                </div>
              )}
              <div className="row" style={{ gap: 8 }}>
                <Bar v={n(d.current[k])} max={mMax} color={CURR} />
                <span className="num" style={{ width: 100, fontSize: ".76rem" }}>
                  {fmt(d.current[k])}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="card" style={{ padding: 16 }}>
          <div className="spread" style={{ marginBottom: 12 }}>
            <b>{L("byDept")}</b><Legend />
          </div>
          {d.by_department.map((x) => (
            <div key={x.department} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: ".84rem", marginBottom: 4 }}>{x.department}</div>
              {d.has_previous && (
                <div className="row" style={{ gap: 8, marginBottom: 3 }}>
                  <Bar v={n(x.previous)} max={dMax} color={PREV} />
                  <span className="num muted" style={{ width: 100, fontSize: ".76rem" }}>
                    {fmt(x.previous)}</span>
                </div>
              )}
              <div className="row" style={{ gap: 8 }}>
                <Bar v={n(x.current)} max={dMax} color={CURR} />
                <span className="num" style={{ width: 100, fontSize: ".76rem" }}>
                  {fmt(x.current)}</span>
              </div>
            </div>
          ))}
        </div>

        {d.has_previous && d.top_changes.length > 0 && (
          <div className="card" style={{ padding: 16 }}>
            <b style={{ display: "block", marginBottom: 12 }}>{L("topChanges")}</b>
            {d.top_changes.map((x, i) => {
              const v = n(x.difference);
              return (
                <div key={i} className="row" style={{ gap: 8, marginBottom: 7 }}>
                  <span className="truncate" style={{ width: 140, fontSize: ".82rem" }}
                        title={x.name}>{x.name}</span>
                  <Bar v={v} max={cMax}
                       color={v < 0 ? "var(--danger)" : "var(--ok)"} />
                  <span className="num" style={{ width: 90, fontSize: ".76rem",
                    color: v < 0 ? "var(--danger)" : "var(--ok)" }}>
                    {v > 0 ? "+" : ""}{fmt(v)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

/**
 * شاشة المسيرات — دورة كاملة:
 *   إنشاء ← احتساب ← مراجعة ← رفع ← اعتماد ← تصدير
 *
 * المسير المعتمد سجل مالي نهائي لا يُعاد احتسابه.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiGet, apiPost, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcPayroll, IcPlus } from "@/components/Icons";

const T: Dict = {
  title: { ar: "مسيرات الرواتب", en: "Payroll Runs" },
  subtitle: {
    ar: "المسير المعتمد سجل مالي نهائي لا يُعاد احتسابه",
    en: "An approved run is a final financial record",
  },
  newRun: { ar: "مسير جديد", en: "New run" },
  runNo: { ar: "رقم المسير", en: "Run No." },
  period: { ar: "الفترة", en: "Period" },
  type: { ar: "النوع", en: "Type" },
  status: { ar: "الحالة", en: "Status" },
  employees: { ar: "الموظفون", en: "Employees" },
  gross: { ar: "الاستحقاقات", en: "Gross" },
  deductions: { ar: "الاستقطاعات", en: "Deductions" },
  net: { ar: "الصافي", en: "Net" },
  variances: { ar: "فروقات", en: "Variances" },
  errors: { ar: "أخطاء", en: "Errors" },
  calculate: { ar: "احتساب", en: "Calculate" },
  submit: { ar: "رفع للاعتماد", en: "Submit" },
  approve: { ar: "اعتماد", en: "Approve" },
  open: { ar: "فتح", en: "Open" },
  year: { ar: "السنة", en: "Year" },
  month: { ar: "الشهر", en: "Month" },
  create: { ar: "إنشاء", en: "Create" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا مسيرات", en: "No runs" },
  emptyHint: {
    ar: "أنشئ أول مسير لهذا الشهر",
    en: "Create the first run for this month",
  },
  calculating: { ar: "جارٍ الاحتساب…", en: "Calculating…" },
  calcDone: { ar: "اكتمل الاحتساب", en: "Calculation complete" },
  calcFailed: { ar: "موظفًا فشل احتسابهم", en: "employees failed" },
  submitted: { ar: "رُفع للاعتماد", en: "Submitted" },
  approved: { ar: "اعتُمد المسير", en: "Run approved" },
  needsBasis: {
    ar: "يجب تحديد ما يدخل في أجر المكافأة من إعدادات الرواتب أولًا",
    en: "Set the EOSB wage basis in payroll settings first",
  },
  regular: { ar: "عام", en: "Regular" },
  supplementary: { ar: "إضافي", en: "Supplementary" },
  settlement: { ar: "مستحقات", en: "Settlement" },
};

type Run = {
  id: number;
  run_no: string;
  period: string;
  period_year: number;
  period_month: number;
  run_type: string;
  run_type_label: string;
  status: string;
  status_label: string;
  employee_count: number;
  total_gross: string;
  total_deductions: string;
  total_net: string;
  variance_count: number;
  error_count: number;
  payment_date: string | null;
};

const STATUS_TONE: Record<string, string> = {
  draft: "badge",
  calculating: "badge-warn",
  calculated: "badge-teal",
  submitted: "badge-warn",
  approved: "badge-ok",
  paid: "badge-ok",
};

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                 maximumFractionDigits: 2 })
    : v;
}


/* ══ نافذة إنشاء مسير — خارج المكوّن الرئيسي ══ */

function NewRunDialog({
  L, onCreate, onClose, busy,
}: {
  L: (k: string, f?: string) => string;
  onCreate: (year: number, month: number, runType: string) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [runType, setRunType] = useState("regular");

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", zIndex: 60, padding: 20,
    }}>
      <div className="card" style={{ width: "100%", maxWidth: 380, padding: 24 }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: 18 }}>{L("newRun")}</h2>

        <div className="stack">
          <div className="field">
            <label className="label">{L("year")}</label>
            <input type="number" className="input" value={year}
              onChange={(e) => setYear(Number(e.target.value))} />
          </div>

          <div className="field">
            <label className="label">{L("month")}</label>
            <select className="select" value={month}
              onChange={(e) => setMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="label">{L("type")}</label>
            <select className="select" value={runType}
              onChange={(e) => setRunType(e.target.value)}>
              <option value="regular">{L("regular")}</option>
              <option value="supplementary">{L("supplementary")}</option>
            </select>
          </div>

          <div className="row" style={{ marginTop: 6 }}>
            <button className="btn btn-primary" disabled={busy}
              onClick={() => onCreate(year, month, runType)}>
              {L("create")}
            </button>
            <button className="btn btn-ghost" onClick={onClose}>
              {L("cancel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══ صف مسير بأزراره ══ */

function RunRow({
  run, L, onAction, busyId,
}: {
  run: Run;
  L: (k: string, f?: string) => string;
  onAction: (id: number, action: "calculate" | "submit" | "approve") => void;
  busyId: number | null;
}) {
  const router = useRouter();
  const busy = busyId === run.id;

  return (
    <tr>
      <td style={{ textAlign: "end" }}>
        <span className="num">{run.run_no}</span>
      </td>
      <td style={{ textAlign: "end" }}>
        <span className="num">{run.period}</span>
      </td>
      <td>{run.run_type_label}</td>
      <td>
        <span className={`badge ${STATUS_TONE[run.status] || "badge"}`}>
          {run.status_label}
        </span>
      </td>
      <td style={{ textAlign: "end" }}>
        <span className="num">{run.employee_count}</span>
      </td>
      <td style={{ textAlign: "end" }}>
        <span className="num">{money(run.total_net)}</span>
      </td>
      <td style={{ textAlign: "end" }}>
        {run.variance_count > 0 ? (
          <span className="badge badge-warn">
            <span className="num">{run.variance_count}</span>
          </span>
        ) : "—"}
      </td>
      <td style={{ textAlign: "end" }}>
        {run.error_count > 0 ? (
          <span className="badge badge-danger">
            <span className="num">{run.error_count}</span>
          </span>
        ) : "—"}
      </td>
      <td>
        <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
          {run.status === "draft" && (
            <button className="btn btn-sm btn-primary" disabled={busy}
              onClick={() => onAction(run.id, "calculate")}>
              {L("calculate")}
            </button>
          )}
          {run.status === "calculated" && (
            <>
              <button className="btn btn-sm" disabled={busy}
                onClick={() => onAction(run.id, "calculate")}>
                {L("calculate")}
              </button>
              <button className="btn btn-sm btn-primary" disabled={busy}
                onClick={() => onAction(run.id, "submit")}>
                {L("submit")}
              </button>
            </>
          )}
          {run.status === "submitted" && (
            <button className="btn btn-sm btn-primary" disabled={busy}
              onClick={() => onAction(run.id, "approve")}>
              <IcCheck size={15} />
              {L("approve")}
            </button>
          )}
          <button className="btn btn-sm btn-ghost"
            onClick={() => router.push(`/payroll/${run.id}`)}>
            {L("open")}
          </button>
        </div>
      </td>
    </tr>
  );
}


/* ══ الشاشة ══ */

export default function PayrollPage() {
  const { L } = useT(T);
  const [runs, setRuns] = useState<Run[]>([]);
  const [year, setYear] = useState(new Date().getFullYear());
  const [busy, setBusy] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [dialog, setDialog] = useState(false);
  const [toast, setToast] = useState("");
  const [toastTone, setToastTone] = useState<"ok" | "warn" | "danger">("ok");

  const notify = (msg: string, tone: "ok" | "warn" | "danger" = "ok") => {
    setToast(msg);
    setToastTone(tone);
    setTimeout(() => setToast(""), 5000);
  };

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRuns(await apiGet<Run[]>(`/payroll/runs/${qs({ year })}`));
    } catch (e) {
      notify((e as ApiError).message, "danger");
    } finally {
      setBusy(false);
    }
  }, [year]);

  useEffect(() => { load(); }, [load]);

  async function createRun(y: number, m: number, runType: string) {
    setBusyId(-1);
    try {
      await apiPost("/payroll/runs/", { year: y, month: m, run_type: runType });
      setDialog(false);
      await load();
    } catch (e) {
      const err = e as ApiError;
      notify(err.message, err.isConflict ? "warn" : "danger");
    } finally {
      setBusyId(null);
    }
  }

  async function action(
    id: number,
    kind: "calculate" | "submit" | "approve",
  ) {
    setBusyId(id);
    if (kind === "calculate") notify(L("calculating"), "warn");

    try {
      const res = await apiPost<{ calculated?: number; failed?: number }>(
        `/payroll/runs/${id}/${kind}/`, {});

      if (kind === "calculate") {
        const failed = res.failed ?? 0;
        notify(
          failed > 0
            ? `${L("calcDone")} — ${failed} ${L("calcFailed")}`
            : L("calcDone"),
          failed > 0 ? "warn" : "ok",
        );
      } else {
        notify(kind === "submit" ? L("submitted") : L("approved"));
      }
      await load();
    } catch (e) {
      const err = e as ApiError;
      notify(
        err.code === "eosb_basis_not_set" ? L("needsBasis") : err.message,
        "danger",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog(true)}>
          <IcPlus size={17} />
          {L("newRun")}
        </button>
      </div>

      {toast && (
        <div style={{
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          background: toastTone === "danger" ? "var(--danger-soft)"
            : toastTone === "warn" ? "var(--copper-soft)" : "var(--ok-soft)",
          color: toastTone === "danger" ? "var(--danger)"
            : toastTone === "warn" ? "var(--copper)" : "var(--ok)",
          fontWeight: 500,
        }}>
          {toast}
        </div>
      )}

      <div className="row">
        <div className="field" style={{ maxWidth: 130 }}>
          <label className="label">{L("year")}</label>
          <input type="number" className="input" value={year}
            onChange={(e) => setYear(Number(e.target.value))} />
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcPayroll size={26} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
            <div style={{ fontSize: ".88rem", marginTop: 4 }}>
              {L("emptyHint")}
            </div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                <col style={{ width: "170px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "140px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "80px" }} />
                <col style={{ width: "290px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("runNo")}</th>
                  <th style={{ textAlign: "end" }}>{L("period")}</th>
                  <th>{L("type")}</th>
                  <th>{L("status")}</th>
                  <th style={{ textAlign: "end" }}>{L("employees")}</th>
                  <th style={{ textAlign: "end" }}>{L("net")}</th>
                  <th style={{ textAlign: "end" }}>{L("variances")}</th>
                  <th style={{ textAlign: "end" }}>{L("errors")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <RunRow key={r.id} run={r} L={L}
                    onAction={action} busyId={busyId} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {dialog && (
        <NewRunDialog L={L} onCreate={createRun}
          onClose={() => setDialog(false)} busy={busyId === -1} />
      )}
    </div>
  );
}

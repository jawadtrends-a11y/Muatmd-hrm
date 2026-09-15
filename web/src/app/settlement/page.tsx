"use client";
/**
 * تسوية نهاية الخدمة (ق-175).
 *
 * ⚠️⚠️ **والمسار كان مبنيًّا بلا شاشة**: فالمخالصة تُحتسب ولا
 * تُعرض — **ونهاية الخدمة ركنٌ أساسيّ**.
 *
 * ⚠️ **والمعاينة قبل الإنشاء**: فكل بندٍ بشرح احتسابه — **ومن
 * يراجع بعد سنة يحتاج معرفة كيف حُسب** (ق-٨٠).
 */
import { useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import EmployeePicker, { type PickedEmployee }
  from "@/components/EmployeePicker";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تسوية نهاية الخدمة", en: "End of service" },
  sub: {
    ar: "احسب المستحقات وراجع كل بندٍ قبل الإنشاء",
    en: "Compute and review before creating",
  },
  employee: { ar: "الموظف", en: "Employee" },
  endDate: { ar: "تاريخ انتهاء الخدمة", en: "Termination date" },
  reason: { ar: "سبب الانتهاء", en: "Reason" },
  pickReason: { ar: "اختر السبب", en: "Select reason" },
  monthSalary: { ar: "احتساب راتب الشهر", en: "Include month salary" },
  leaveDays: { ar: "رصيد الإجازة (يومًا)", en: "Leave balance (days)" },
  leaveHint: {
    ar: "اتركه فارغًا ليُحتسب من النظام",
    en: "Empty = computed",
  },
  agreed: { ar: "تعويض متّفق عليه", en: "Agreed compensation" },
  remaining: { ar: "الأشهر المتبقّية بالعقد", en: "Remaining months" },
  compute: { ar: "احسب المعاينة", en: "Compute" },
  service: { ar: "مدّة الخدمة", en: "Service" },
  days: { ar: "يومًا", en: "days" },
  years: { ar: "سنة", en: "years" },
  item: { ar: "البند", en: "Item" },
  explanation: { ar: "الاحتساب", en: "Calculation" },
  amount: { ar: "المبلغ", en: "Amount" },
  earnings: { ar: "إجمالي المستحقات", en: "Total earnings" },
  deductions: { ar: "إجمالي الاستقطاعات", en: "Total deductions" },
  net: { ar: "الصافي المستحق", en: "Net due" },
  create: { ar: "إنشاء مسير المستحقات", en: "Create settlement run" },
  created: { ar: "أُنشئ المسير", en: "Run created" },
  confirmCreate: {
    ar: "⚠️ سيُنشأ مسيرُ مستحقاتٍ بقسيمته — أمتأكّد؟",
    en: "A settlement run will be created — are you sure?",
  },
  warnings: { ar: "تنبيهات", en: "Warnings" },
  basisMissing: {
    ar: "أساس مكافأة نهاية الخدمة غير محدَّد — اضبطه من إعدادات الرواتب",
    en: "EOSB basis not set",
  },
  goSettings: { ar: "فتح الإعدادات", en: "Open settings" },
  needEmployee: { ar: "اختر الموظف والتاريخ أولًا", en: "Pick first" },
};

type Line = {
  code: string; name_ar: string; kind: string;
  amount: string; explanation: string;
};
type Preview = {
  employee_no: string; name: string; termination_date: string;
  reason_label: string; service_days: number; service_years: string;
  lines: Line[];
  total_earnings: string; total_deductions: string; net_due: string;
  warnings: string[];
};
type Reason = { code: string; label: string };

export default function SettlementPage() {
  const { L } = useT(T);
  const [emp, setEmp] = useState<PickedEmployee | null>(null);
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [reasons, setReasons] = useState<Reason[]>([]);
  const [monthSalary, setMonthSalary] = useState(true);
  const [leaveDays, setLeaveDays] = useState("");
  const [agreed, setAgreed] = useState("");
  const [remaining, setRemaining] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [basisMissing, setBasisMissing] = useState(false);

  useEffect(() => {
    apiGet<{ reasons: Reason[] } | Reason[]>("/settlement/reasons/")
      .then((d) => setReasons(Array.isArray(d) ? d : (d.reasons || [])))
      .catch(() => setReasons([]));
  }, []);

  // ⚠️ **وتغيّر المدخلات يمسح المعاينة**: فمعاينةٌ قديمة **يُبنى
  // عليها قرارٌ خاطئ**.
  useEffect(() => { setPreview(null); },
            [emp, endDate, reason, monthSalary, leaveDays,
             agreed, remaining]);

  const body = () => ({
    termination_date: endDate,
    reason_code: reason,
    include_month_salary: monthSalary,
    ...(leaveDays !== "" ? { leave_balance_days: leaveDays } : {}),
    ...(agreed !== "" ? { agreed_compensation: agreed } : {}),
    ...(remaining !== "" ? { remaining_contract_months: remaining }
                         : {}),
  });

  const compute = async () => {
    if (!emp || !endDate) { setErr(L("needEmployee")); return; }
    setBusy(true); setErr(""); setMsg(""); setBasisMissing(false);
    try {
      setPreview(await apiPost<Preview>(
        `/employees/${emp.id}/settlement/preview/`, body()));
    } catch (e) {
      const ae = e as ApiError;
      // ⚠️ **وأساسٌ غير مضبوط يُوجَّه لإعداده** — لا رسالةٌ مبهمة
      if ((ae as unknown as { code?: string })?.code
          === "eosb_basis_not_set") {
        setBasisMissing(true);
      }
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const create = async () => {
    if (!emp || !preview) return;
    if (!confirm(L("confirmCreate"))) return;
    setBusy(true); setErr("");
    try {
      await apiPost(`/employees/${emp.id}/settlement/create/`, body());
      setMsg(L("created"));
      setPreview(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <IcAlert /> {err}
          {basisMissing && (
            <a className="btn btn-sm" style={{ marginInlineStart: 10 }}
               href="/settings">{L("goSettings")}</a>
          )}
        </div>
      )}

      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: "grid", gap: 14,
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <div className="field">
            <label className="label">{L("employee")}</label>
            <EmployeePicker value={emp} onChange={setEmp} />
          </div>

          <div className="field">
            <label className="label">{L("endDate")}</label>
            <DateField value={endDate} onChange={setEndDate} />
          </div>

          <label className="field">
            <span className="label">{L("reason")}</span>
            <select className="select" value={reason}
                    onChange={(e) => setReason(e.target.value)}>
              <option value="">{L("pickReason")}</option>
              {reasons.map((r) => (
                <option key={r.code} value={r.code}>{r.label}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">{L("leaveDays")}</span>
            <input className="input num" type="number" step="0.5"
                   value={leaveDays}
                   onChange={(e) => setLeaveDays(e.target.value)} />
            <span className="muted" style={{ fontSize: ".76rem" }}>
              {L("leaveHint")}
            </span>
          </label>

          <label className="field">
            <span className="label">{L("agreed")}</span>
            <input className="input num" type="number" step="0.01"
                   value={agreed}
                   onChange={(e) => setAgreed(e.target.value)} />
          </label>

          <label className="field">
            <span className="label">{L("remaining")}</span>
            <input className="input num" type="number" step="0.5"
                   value={remaining}
                   onChange={(e) => setRemaining(e.target.value)} />
          </label>
        </div>

        <label className="row" style={{ gap: 8, marginTop: 14,
                                        cursor: "pointer" }}>
          <input type="checkbox" checked={monthSalary}
                 onChange={(e) => setMonthSalary(e.target.checked)} />
          <span>{L("monthSalary")}</span>
        </label>

        <button className="btn btn-primary" style={{ marginTop: 16 }}
                disabled={busy || !emp || !endDate}
                onClick={compute}>
          {busy ? "…" : L("compute")}
        </button>
      </div>

      {preview && (
        <>
          <div className="card" style={{ padding: 18 }}>
            <div className="spread">
              <div>
                <strong>{preview.name}</strong>
                <div className="muted num" style={{ fontSize: ".78rem" }}>
                  {preview.employee_no} · {preview.reason_label}
                </div>
              </div>
              <div className="muted" style={{ fontSize: ".85rem" }}>
                {L("service")}:{" "}
                <span className="num">{preview.service_years}</span>{" "}
                {L("years")} (
                <span className="num">{preview.service_days}</span>{" "}
                {L("days")})
              </div>
            </div>
          </div>

          {/* ⚠️ **والتنبيهات قبل الأرقام** — فمن يقرّر يقرؤها */}
          {preview.warnings?.length > 0 && (
            <div style={{ background: "var(--copper-soft)",
                          color: "var(--copper)", padding: "11px 14px",
                          borderRadius: "var(--radius-sm)",
                          fontSize: ".84rem", lineHeight: 1.9 }}>
              <strong>{L("warnings")}:</strong>
              <ul style={{ margin: "6px 0 0", paddingInlineStart: 18 }}>
                {preview.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          <div className="card" style={{ overflow: "hidden" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("item")}</th>
                  <th>{L("explanation")}</th>
                  <th style={{ width: 130 }}>{L("amount")}</th>
                </tr>
              </thead>
              <tbody>
                {preview.lines.map((l, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{l.name_ar}</td>
                    {/* ⚠️ **والشرح مع كل بند** — فمن يراجع بعد سنة
                        يحتاج معرفة كيف حُسب (ق-٨٠) */}
                    <td className="muted" style={{ fontSize: ".83rem" }}>
                      {l.explanation || "—"}
                    </td>
                    <td>
                      <span className="num" style={{
                        color: l.kind === "deduction"
                          ? "var(--danger)" : undefined }}>
                        {l.amount}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={2} style={{ fontWeight: 600 }}>
                    {L("earnings")}
                  </td>
                  <td><span className="num">
                    {preview.total_earnings}
                  </span></td>
                </tr>
                <tr>
                  <td colSpan={2} style={{ fontWeight: 600 }}>
                    {L("deductions")}
                  </td>
                  <td><span className="num"
                            style={{ color: "var(--danger)" }}>
                    {preview.total_deductions}
                  </span></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="card" style={{
            padding: 18, background: "var(--teal)", color: "#fff" }}>
            <div className="spread">
              <strong style={{ fontSize: "1.05rem" }}>{L("net")}</strong>
              <span className="num" style={{ fontSize: "1.4rem",
                                             fontWeight: 700 }}>
                {preview.net_due}
              </span>
            </div>
          </div>

          <button className="btn btn-primary" disabled={busy}
                  onClick={create}>
            <IcDoc size={17} /> {busy ? "…" : L("create")}
          </button>
        </>
      )}
    </div>
  );
}

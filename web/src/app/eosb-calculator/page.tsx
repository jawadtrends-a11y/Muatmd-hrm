"use client";
/**
 * حاسبة مكافأة نهاية الخدمة (ق-188).
 *
 * ⚠️⚠️ **والمسار كان مبنيًّا بلا شاشة** — كشفه الجرد: «مطابقة
 * للحاسبة الحكومية (ق-25)، **تُرجع شرح الاحتساب كاملًا ليعيد
 * الموظف الحساب بورقة وقلم**».
 *
 * ⚠️ **وهي حاسبةٌ لا قرار**: **لا تمسّ مسيرًا ولا سجلًّا** —
 * فالمخالصة الفعلية في شاشة نهاية الخدمة.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcChart } from "@/components/Icons";

const T: Dict = {
  title: { ar: "حاسبة نهاية الخدمة", en: "End-of-service calculator" },
  sub: {
    ar: "احسب المكافأة بشرح خطواتها — مطابقة للحاسبة الحكومية",
    en: "Computed with a full explanation",
  },
  hint: {
    ar: "⚠️ حاسبةٌ للاطّلاع — لا تمسّ مسيرًا ولا سجلًّا",
    en: "Informational only",
  },
  joinDate: { ar: "تاريخ المباشرة", en: "Join date" },
  endDate: { ar: "تاريخ انتهاء الخدمة", en: "End date" },
  wage: { ar: "الأجر المحتسب للمكافأة", en: "EOSB wage" },
  reason: { ar: "سبب الانتهاء", en: "Reason" },
  pickReason: { ar: "اختر السبب", en: "Select" },
  unpaid: { ar: "أيام إجازة بلا أجر", en: "Unpaid leave days" },
  compute: { ar: "احسب", en: "Compute" },
  service: { ar: "مدّة الخدمة", en: "Service" },
  days: { ar: "يومًا", en: "days" },
  years: { ar: "سنة", en: "years" },
  gross: { ar: "المكافأة قبل النسبة", en: "Gross award" },
  ratio: { ar: "نسبة الاستحقاق", en: "Entitlement" },
  net: { ar: "المستحق", en: "Net award" },
  explanation: { ar: "شرح الاحتساب", en: "Calculation" },
  warnings: { ar: "تنبيهات", en: "Warnings" },
  article77: { ar: "تعويض المادة ٧٧", en: "Article 77" },
  basisMissing: { ar: "فتح إعدادات الرواتب", en: "Open settings" },
  needed: { ar: "أكمل التواريخ والأجر", en: "Fill the fields" },
};

type Reason = { code: string; label: string };
type Result = {
  service_days: number; service_years: string;
  eosb_wage: string; gross_award: string;
  entitlement_ratio: string; net_award: string;
  reason_label: string; explanation: string[] | string;
  warnings: string[];
  compensation_article_77?: { amount?: string;
                              explanation?: string } | null;
};

export default function EosbCalculatorPage() {
  const { L } = useT(T);
  const [join, setJoin] = useState("");
  const [end, setEnd] = useState("");
  const [wage, setWage] = useState("");
  const [reason, setReason] = useState("");
  const [unpaid, setUnpaid] = useState("0");
  const [reasons, setReasons] = useState<Reason[]>([]);
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [basisMissing, setBasisMissing] = useState(false);

  useEffect(() => {
    apiGet<{ reasons: Reason[] } | Reason[]>("/settlement/reasons/")
      .then((d) => setReasons(Array.isArray(d) ? d : (d.reasons || [])))
      .catch(() => setReasons([]));
  }, []);

  // ⚠️ **وتغيّر المدخلات يمسح النتيجة**: فنتيجةٌ قديمة **يُبنى
  // عليها فهمٌ خاطئ**.
  useEffect(() => { setRes(null); }, [join, end, wage, reason, unpaid]);

  const compute = async () => {
    if (!join || !end || !wage) { setErr(L("needed")); return; }
    setBusy(true);
    setErr("");
    setBasisMissing(false);
    try {
      setRes(await apiPost<Result>("/payroll/eosb/calculate/", {
        join_date: join, end_date: end, eosb_wage: wage,
        reason_code: reason,
        unpaid_leave_days: Number(unpaid) || 0,
      }));
    } catch (e) {
      const code = (e as unknown as { code?: string })?.code;
      if (code === "eosb_basis_not_set") setBasisMissing(true);
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const steps = !res ? [] : (Array.isArray(res.explanation)
    ? res.explanation
    : String(res.explanation || "").split("\n").filter(Boolean));

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem",
                                        marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      <div style={{ background: "var(--copper-soft)",
                    color: "var(--copper)", padding: "10px 13px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: ".83rem", lineHeight: 1.9 }}>
        {L("hint")}
      </div>

      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
          {basisMissing && (
            <a className="btn btn-sm" style={{ marginInlineStart: 10 }}
               href="/settings">{L("basisMissing")}</a>
          )}
        </div>
      )}

      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: "grid", gap: 14,
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(210px, 1fr))" }}>
          <div className="field">
            <label className="label">{L("joinDate")}</label>
            <DateField value={join} onChange={setJoin} />
          </div>

          <div className="field">
            <label className="label">{L("endDate")}</label>
            <DateField value={end} onChange={setEnd} />
          </div>

          <label className="field">
            <span className="label">{L("wage")}</span>
            <input className="input num" type="number" step="0.01"
                   value={wage}
                   onChange={(e) => setWage(e.target.value)} />
          </label>

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
            <span className="label">{L("unpaid")}</span>
            <input className="input num" type="number" min={0}
                   value={unpaid}
                   onChange={(e) => setUnpaid(e.target.value)} />
          </label>
        </div>

        <button className="btn btn-primary" style={{ marginTop: 16 }}
                disabled={busy || !join || !end || !wage}
                onClick={compute}>
          <IcChart size={17} /> {busy ? "…" : L("compute")}
        </button>
      </div>

      {res && (
        <>
          <div className="card" style={{ padding: 18 }}>
            <div style={{ display: "grid", gap: 14,
                          gridTemplateColumns:
                            "repeat(auto-fit, minmax(150px, 1fr))" }}>
              <Cell label={L("service")}
                    value={`${res.service_years} ${L("years")}`} />
              <Cell label={L("days")}
                    value={String(res.service_days)} />
              <Cell label={L("gross")} value={res.gross_award} />
              <Cell label={L("ratio")} value={res.entitlement_ratio} />
            </div>
          </div>

          {/* ⚠️ **والتنبيهات قبل الرقم** — فمن يقرأ يقرّر */}
          {res.warnings?.length > 0 && (
            <div style={{ background: "var(--copper-soft)",
                          color: "var(--copper)", padding: "11px 14px",
                          borderRadius: "var(--radius-sm)",
                          fontSize: ".84rem", lineHeight: 1.9 }}>
              <strong>{L("warnings")}:</strong>
              <ul style={{ margin: "6px 0 0", paddingInlineStart: 18 }}>
                {res.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* ⚠️⚠️ **وشرح الاحتساب** — **ليعيد الموظف الحساب بورقة
              وقلم** (ق-25) */}
          {steps.length > 0 && (
            <div className="card" style={{ padding: 18 }}>
              <h3 style={{ margin: "0 0 10px", fontSize: "1rem" }}>
                {L("explanation")}
              </h3>
              <ol style={{ margin: 0, paddingInlineStart: 20,
                           lineHeight: 2.1, fontSize: ".88rem" }}>
                {steps.map((line, i) => <li key={i}>{line}</li>)}
              </ol>
            </div>
          )}

          {res.compensation_article_77?.amount && (
            <div className="card" style={{ padding: 16 }}>
              <div className="spread">
                <strong>{L("article77")}</strong>
                <span className="num">
                  {res.compensation_article_77.amount}
                </span>
              </div>
              {res.compensation_article_77.explanation && (
                <div className="muted" style={{ fontSize: ".82rem",
                                                marginTop: 6 }}>
                  {res.compensation_article_77.explanation}
                </div>
              )}
            </div>
          )}

          <div className="card" style={{
            padding: 18, background: "var(--teal)", color: "#fff" }}>
            <div className="spread">
              <strong style={{ fontSize: "1.05rem" }}>{L("net")}</strong>
              <span className="num" style={{ fontSize: "1.4rem",
                                             fontWeight: 700 }}>
                {res.net_award}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: ".76rem",
                                      marginBottom: 3 }}>
        {label}
      </div>
      <div className="num">{value}</div>
    </div>
  );
}

"use client";
/**
 * صفحة الأسعار العامّة (ق-116).
 *
 * تُفتح **قبل التسجيل** ويُربط إليها من الموقع الرئيسيّ — فلا
 * توثيق لها ولا تقرأ بيانات أحد: الزائر يكتب عدد موظفيه فيرى
 * سعره، ثم يبدأ.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الأسعار", en: "Pricing" },
  sub: {
    ar: "السعر لكل موظف — والأسعار غير شاملة ضريبة القيمة المضافة",
    en: "Price per employee — VAT not included",
  },
  monthly: { ar: "شهريًّا", en: "Monthly" },
  annual: { ar: "سنويًّا", en: "Annual" },
  perEmp: { ar: "للموظف في الشهر", en: "per employee / month" },
  perEmpY: { ar: "للموظف في السنة", en: "per employee / year" },
  employees: { ar: "عدد الموظفين", en: "Employees" },
  includes: { ar: "تشمل الباقة", en: "Includes" },
  inherits: { ar: "تشمل مزايا", en: "Includes everything in" },
  plus: { ar: "بالإضافة إلى:", en: "plus:" },
  setup: { ar: "إعداد أوّليّ للنظام", en: "One-time setup" },
  setupHint: {
    ar: "اختياريّ — يُدفع مرّة واحدة ولا يدخل التجديد",
    en: "Optional — charged once, never in renewals",
  },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  vat: { ar: "ضريبة القيمة المضافة", en: "VAT" },
  total: { ar: "الإجمالي", en: "Total" },
  start: { ar: "ابدأ الآن", en: "Start now" },
  trial: { ar: "جرّبه {d} أيام مجانًا", en: "{d}-day free trial" },
  sar: { ar: "ريال", en: "SAR" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  login: { ar: "تسجيل الدخول", en: "Sign in" },
  toSite: { ar: "الموقع الرئيسي", en: "Main site" },
  toAcc: { ar: "معتمد المحاسبي", en: "Muatmd Accounting" },
};

type Feat = { key: string; name_ar: string; name_en: string;
              value: string; value_type: string };
type Plan = {
  id: number; code: string; name_ar: string; name_en: string;
  monthly: string | null; annual: string | null; setup_fee: string;
  min_employees: number; features_new: Feat[]; inherits_from: string;
};
type Quote = {
  subscription: string; setup_fee: string; vat: string; total: string;
};

export default function PricingPage() {
  const { L, lang } = useT(T);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [trialDays, setTrialDays] = useState(7);
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [count, setCount] = useState(10);
  const [setup, setSetup] = useState<Record<number, boolean>>({});
  const [quotes, setQuotes] = useState<Record<number, Quote>>({});
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    try {
      const d = await apiGet<{ plans: Plan[]; trial_days: number }>(
        "/pricing/");
      setPlans(d.plans);
      if (d.trial_days) setTrialDays(d.trial_days);
    } catch {
      /* الصفحة تبقى بلا باقات لا مكسورة */
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!plans.length || count < 1) return;
    let cancelled = false;
    (async () => {
      const out: Record<number, Quote> = {};
      await Promise.all(plans.map(async (p) => {
        const q = await apiGet<Quote>(
          `/pricing/quote/?plan_id=${p.id}&employees=${count}`
          + `&cycle=${cycle}&with_setup=${setup[p.id] ? "1" : "0"}`
        ).catch(() => null);
        if (q) out[p.id] = q;
      }));
      if (!cancelled) setQuotes(out);
    })();
    return () => { cancelled = true; };
  }, [plans, count, cycle, setup]);

  const money = (v?: string | null) =>
    v ? Number(v).toLocaleString("en-US", { minimumFractionDigits: 2,
                                            maximumFractionDigits: 2 }) : "—";

  return (
    <div style={{ minHeight: "100vh", padding: "32px 20px 60px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <img src="/logo.png" alt="معتمد"
               style={{ height: 78, margin: "0 auto 12px", display: "block" }} />
          <h1 style={{ margin: 0, fontSize: "1.6rem" }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".92rem", marginTop: 6 }}>
            {L("sub")}
          </div>
          <div style={{ marginTop: 10, display: "inline-block",
                        padding: "5px 14px", borderRadius: 999,
                        background: "var(--teal-soft)", color: "var(--teal)",
                        fontSize: ".85rem" }}>
            {L("trial").replace("{d}", String(trialDays))}
          </div>
        </div>

        <div className="card" style={{ padding: 18, marginBottom: 22 }}>
          <div className="row" style={{ gap: 16, flexWrap: "wrap",
                                        alignItems: "flex-end",
                                        justifyContent: "center" }}>
            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("employees")}</label>
              <input className="input num" type="number" min={1} value={count}
                     onChange={(e) =>
                       setCount(Math.max(1, +e.target.value || 1))} />
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className={`btn btn-sm ${cycle === "monthly" ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setCycle("monthly")}>{L("monthly")}</button>
              <button className={`btn btn-sm ${cycle === "annual" ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setCycle("annual")}>{L("annual")}</button>
            </div>
          </div>
        </div>

        {busy ? (
          <div className="card" style={{ padding: 40, textAlign: "center",
                                         color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : (
          <div style={{ display: "grid", gap: 14,
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(270px, 1fr))" }}>
            {plans.map((p) => {
              const q = quotes[p.id];
              const unit = cycle === "monthly" ? p.monthly : p.annual;
              return (
                <div key={p.id} className="card" style={{
                  padding: 22, display: "flex", flexDirection: "column",
                }}>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>
                      {(lang === "en" ? p.name_en : p.name_ar) || p.name_ar}
                    </div>
                    <div className="num" style={{ fontSize: "2.1rem",
                                                  fontWeight: 700,
                                                  color: "var(--teal)",
                                                  marginTop: 8 }}>
                      {money(unit)}
                    </div>
                    <div className="muted" style={{ fontSize: ".82rem" }}>
                      {L("sar")} ·{" "}
                      {cycle === "monthly" ? L("perEmp") : L("perEmpY")}
                    </div>
                  </div>

                  <div style={{ borderTop: "1px solid var(--line)",
                                margin: "16px 0 12px" }} />

                  <div style={{ fontSize: ".85rem", fontWeight: 600,
                                marginBottom: 8 }}>
                    {p.inherits_from
                      ? `${L("inherits")} «${p.inherits_from}» ${L("plus")}`
                      : L("includes")}
                  </div>
                  <div style={{ display: "grid", gap: 6, flex: 1 }}>
                    {p.features_new.map((f) => (
                      <div key={f.key} className="row"
                           style={{ gap: 7, fontSize: ".85rem" }}>
                        <span style={{ color: "var(--ok)" }}>
                          <IcCheck size={14} />
                        </span>
                        <span>
                          {(lang === "en" ? f.name_en : f.name_ar) || f.name_ar}
                          {f.value_type !== "bool" && f.value !== "0" && (
                            <span className="muted"> ({f.value})</span>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>

                  {Number(p.setup_fee) > 0 && (
                    <label className="row" style={{ gap: 8, marginTop: 14,
                                                    cursor: "pointer",
                                                    fontSize: ".85rem" }}>
                      <input type="checkbox" checked={!!setup[p.id]}
                             onChange={(e) => setSetup({
                               ...setup, [p.id]: e.target.checked })} />
                      <span>
                        {L("setup")} (
                        <span className="num">{money(p.setup_fee)}</span>)
                        <div className="muted" style={{ fontSize: ".76rem" }}>
                          {L("setupHint")}
                        </div>
                      </span>
                    </label>
                  )}

                  {q && (
                    <div style={{ marginTop: 14, paddingTop: 12,
                                  borderTop: "1px solid var(--line)",
                                  display: "grid", gap: 5,
                                  fontSize: ".85rem" }}>
                      <div className="spread">
                        <span className="muted">{L("subscription")}</span>
                        <span className="num">{money(q.subscription)}</span>
                      </div>
                      {Number(q.setup_fee) > 0 && (
                        <div className="spread">
                          <span className="muted">{L("setup")}</span>
                          <span className="num">{money(q.setup_fee)}</span>
                        </div>
                      )}
                      <div className="spread">
                        <span className="muted">{L("vat")}</span>
                        <span className="num">{money(q.vat)}</span>
                      </div>
                      <div className="spread" style={{ fontWeight: 700,
                                                       fontSize: "1rem",
                                                       marginTop: 4 }}>
                        <span>{L("total")}</span>
                        <span className="num">
                          {money(q.total)} {L("sar")}
                        </span>
                      </div>
                    </div>
                  )}

                  <Link href="/signup" className="btn btn-primary"
                        style={{ marginTop: 16, width: "100%", height: 42,
                                 display: "grid", placeItems: "center" }}>
                    {L("start")}
                  </Link>
                </div>
              );
            })}
          </div>
        )}

        <div className="row" style={{ justifyContent: "center", gap: 8,
                                      marginTop: 30, flexWrap: "wrap" }}>
          <Link href="/login" className="btn btn-ghost btn-sm">
            {L("login")}
          </Link>
          <a href="https://muatmd.sa" className="btn btn-ghost btn-sm">
            {L("toSite")}
          </a>
          <a href="https://acc.muatmd.sa" className="btn btn-ghost btn-sm">
            {L("toAcc")}
          </a>
        </div>
      </div>
    </div>
  );
}

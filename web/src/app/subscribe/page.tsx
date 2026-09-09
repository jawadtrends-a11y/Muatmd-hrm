"use client";
/**
 * الباقات والاشتراك (ق-108).
 *
 * سعر واحد للموظف: يكتب العميل عدده فيرى الإجمالي بالضريبة قبل
 * أن يدفع — فلا مفاجأة عند الفاتورة.
 *
 * والمزايا تراكمية: الباقة الأعلى «تشمل ما قبلها بالإضافة إلى…».
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الباقات", en: "Plans" },
  subtitle: {
    ar: "السعر لكل موظف — والأسعار غير شاملة ضريبة القيمة المضافة",
    en: "Price per employee — VAT not included",
  },
  monthly: { ar: "شهريًّا", en: "Monthly" },
  annual: { ar: "سنويًّا", en: "Annual" },
  perEmp: { ar: "للموظف في الشهر", en: "per employee / month" },
  perEmpY: { ar: "للموظف في السنة", en: "per employee / year" },
  employees: { ar: "عدد الموظفين", en: "Employees" },
  current: { ar: "لديك الآن", en: "You have" },
  includes: { ar: "تشمل الباقة", en: "Includes" },
  inherits: { ar: "تشمل مزايا", en: "Includes everything in" },
  plus: { ar: "بالإضافة إلى:", en: "plus:" },
  setup: { ar: "إعداد أوّليّ للنظام", en: "One-time setup" },
  setupHint: {
    ar: "يُدفع مرّة واحدة فقط — ولا يدخل فاتورة التجديد",
    en: "Charged once — never in renewals",
  },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  vat: { ar: "ضريبة القيمة المضافة", en: "VAT" },
  total: { ar: "الإجمالي", en: "Total" },
  renewal: { ar: "ويتجدّد بـ", en: "Renews at" },
  start: { ar: "ابدأ الآن", en: "Start now" },
  sar: { ar: "ريال", en: "SAR" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  soon: {
    ar: "الدفع قيد الإعداد — تواصل معنا لتفعيل اشتراكك",
    en: "Payment coming soon — contact us to activate",
  },
  activeSub: { ar: "اشتراكك الحالي", en: "Your subscription" },
  daysLeft: { ar: "يومًا متبقّية", en: "days remaining" },
  payTitle: { ar: "إتمام الاشتراك", en: "Complete subscription" },
  payFor: { ar: "مرجع العملية", en: "Reference" },
  payAmount: { ar: "المبلغ المستحقّ", en: "Amount due" },
  payHint: {
    ar: "بيانات بطاقتك تُرسل لبوابة الدفع مباشرةً — ولا تمرّ بخوادمنا",
    en: "Card details go straight to the payment gateway",
  },
  preparing: { ar: "جارٍ التجهيز…", en: "Preparing…" },
  close: { ar: "إغلاق", en: "Close" },
};

type Feat = { key: string; name_ar: string; name_en: string;
              value: string; value_type: string };
type Plan = {
  id: number; code: string; name_ar: string; name_en: string;
  monthly: string | null; annual: string | null; setup_fee: string;
  trial_days: number; min_employees: number;
  features_new: Feat[]; inherits_from: string;
};
type Quote = {
  subscription: string; setup_fee: string; subtotal: string;
  vat: string; total: string; renewal_total: string;
  unit_price: string; billable_employees: number;
};
type Checkout = {
  invoice_id: number; invoice_no: string; total: string;
  publishable_key: string; callback_url: string;
  amount_halalas: number; employees: number;
};
type Sub = {
  has_subscription: boolean; active_employees: number;
  plan?: string; state_label?: string; days_remaining?: number;
  subscribed_employees?: number;
};

export default function SubscribePage() {
  const { L, lang } = useT(T);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Sub | null>(null);
  const [cycle, setCycle] = useState<"monthly" | "annual">("monthly");
  const [count, setCount] = useState(1);
  const [setup, setSetup] = useState<Record<number, boolean>>({});
  const [quotes, setQuotes] = useState<Record<number, Quote>>({});
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [paying, setPaying] = useState<number | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [p, s] = await Promise.all([
        apiGet<{ plans: Plan[] }>("/plans/"),
        apiGet<Sub>("/account/my-subscription/").catch(() => null),
      ]);
      setPlans(p.plans);
      setSub(s);
      if (s?.active_employees) setCount(s.active_employees);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // السعر يُحسب في الخادم لا في الشاشة: فالضريبة ورسم الإعداد
  // وحدود الباقة قرارات نظامية، وحسابها مرّتين يفتح باب اختلافهما.
  useEffect(() => {
    if (!plans.length || count < 1) return;
    let cancelled = false;
    (async () => {
      const out: Record<number, Quote> = {};
      await Promise.all(plans.map(async (p) => {
        const q = await apiPost<Quote>("/plans/quote/", {
          plan_id: p.id, employees: count, cycle,
          with_setup: !!setup[p.id],
        }).catch(() => null);
        if (q) out[p.id] = q;
      }));
      if (!cancelled) setQuotes(out);
    })();
    return () => { cancelled = true; };
  }, [plans, count, cycle, setup]);

  const startCheckout = async (p: Plan) => {
    setPaying(p.id); setErr("");
    try {
      const d = await apiPost<Checkout>("/account/checkout/", {
        plan_code: p.code, cycle, employees: count,
        with_setup: !!setup[p.id],
      });
      setCheckout(d);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setPaying(null); }
  };

  // نموذج ميسر الجاهز: بيانات البطاقة تذهب إليه مباشرةً ولا تمرّ
  // بخوادمنا (ق-47). ونحمّل نصّه عند الحاجة لا في كل صفحة.
  useEffect(() => {
    if (!checkout) return;
    const CSS = "https://cdn.moyasar.com/mpf/1.15.0/moyasar.css";
    const JS = "https://cdn.moyasar.com/mpf/1.15.0/moyasar.js";

    if (!document.querySelector(`link[href="${CSS}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet"; l.href = CSS;
      document.head.appendChild(l);
    }

    const init = () => {
      const w = window as unknown as {
        Moyasar?: { init: (o: Record<string, unknown>) => void };
      };
      if (!w.Moyasar) return;
      w.Moyasar.init({
        element: ".mysr-form",
        amount: checkout.amount_halalas,
        currency: "SAR",
        description: `اشتراك معتمد HRM — ${checkout.invoice_no}`,
        publishable_api_key: checkout.publishable_key,
        callback_url: checkout.callback_url,
        // البطاقة وحدها الآن: Apple Pay يشترط تسجيل النطاق في
        // ميسر ومعرّف التاجر — وبدونها يحجب حقول البطاقة بأخطائه.
        methods: ["creditcard"],
        metadata: { invoice_id: checkout.invoice_id },
      });
    };

    const existing = document.querySelector(`script[src="${JS}"]`);
    if (existing) { init(); return; }
    const sc = document.createElement("script");
    sc.src = JS;
    sc.onload = init;
    document.body.appendChild(sc);
  }, [checkout]);

  const money = (v?: string) =>
    v ? Number(v).toLocaleString("en-US", { minimumFractionDigits: 2,
                                            maximumFractionDigits: 2 }) : "—";

  if (busy) return <div className="card" style={{ padding: 40,
    textAlign: "center", color: "var(--ink-3)" }}>{L("loading")}</div>;

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}
      {msg && <div className="card" style={{ borderColor: "var(--teal)" }}>
        {msg}
      </div>}

      {sub?.has_subscription && (
        <div className="card" style={{ padding: 16,
                                       borderColor: "var(--teal)" }}>
          <div className="spread">
            <span>
              <b>{L("activeSub")}:</b> {sub.plan} · {sub.state_label}
            </span>
            <span className="muted">
              <span className="num">{sub.days_remaining}</span> {L("daysLeft")}
            </span>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 18 }}>
        <div className="row" style={{ gap: 16, flexWrap: "wrap",
                                      alignItems: "flex-end" }}>
          <div className="field" style={{ minWidth: 200 }}>
            <label className="label">{L("employees")}</label>
            <input className="input num" type="number" min={1}
                   value={count}
                   onChange={(e) => setCount(Math.max(1, +e.target.value || 1))} />
            {sub?.active_employees ? (
              <span className="muted" style={{ fontSize: ".8rem" }}>
                {L("current")} <span className="num">{sub.active_employees}</span>
              </span>
            ) : null}
          </div>
          <div className="row" style={{ gap: 6 }}>
            <button className={`btn btn-sm ${cycle === "monthly" ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setCycle("monthly")}>{L("monthly")}</button>
            <button className={`btn btn-sm ${cycle === "annual" ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setCycle("annual")}>{L("annual")}</button>
          </div>
        </div>
      </div>

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
                  {money(unit || undefined)}
                </div>
                <div className="muted" style={{ fontSize: ".82rem" }}>
                  {L("sar")} · {cycle === "monthly" ? L("perEmp") : L("perEmpY")}
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
                  <div key={f.key} className="row" style={{ gap: 7,
                                                            fontSize: ".85rem" }}>
                    <span style={{ color: "var(--ok)" }}><IcCheck size={14} /></span>
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
                         onChange={(e) => setSetup({ ...setup,
                                                     [p.id]: e.target.checked })} />
                  <span>
                    {L("setup")} (<span className="num">{money(p.setup_fee)}</span>)
                    <div className="muted" style={{ fontSize: ".76rem" }}>
                      {L("setupHint")}
                    </div>
                  </span>
                </label>
              )}

              {q && (
                <div style={{ marginTop: 14, paddingTop: 12,
                              borderTop: "1px solid var(--line)",
                              display: "grid", gap: 5, fontSize: ".85rem" }}>
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
                    <span className="num">{money(q.total)} {L("sar")}</span>
                  </div>
                  {Number(q.setup_fee) > 0 && (
                    <div className="muted" style={{ fontSize: ".76rem" }}>
                      {L("renewal")} <span className="num">
                        {money(q.renewal_total)}
                      </span> {L("sar")}
                    </div>
                  )}
                </div>
              )}

              <button className="btn btn-primary"
                      style={{ marginTop: 16, width: "100%", height: 42 }}
                      disabled={paying !== null}
                      onClick={() => startCheckout(p)}>
                {paying === p.id ? L("preparing") : L("start")}
              </button>
            </div>
          );
        })}
      </div>

      {checkout && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 80,
          overflowY: "auto",
        }}>
          <div className="card" style={{ padding: 24, maxWidth: 460,
                                         width: "100%" }}>
            <div className="spread">
              <h3 style={{ margin: 0 }}>{L("payTitle")}</h3>
              <button className="btn btn-ghost btn-sm"
                      onClick={() => setCheckout(null)}>
                {L("close")}
              </button>
            </div>

            <div style={{ marginTop: 14, display: "grid", gap: 6,
                          fontSize: ".9rem" }}>
              <div className="spread">
                <span className="muted">{L("payFor")}</span>
                <span className="num">{checkout.invoice_no}</span>
              </div>
              <div className="spread" style={{ fontWeight: 700 }}>
                <span>{L("payAmount")}</span>
                <span className="num">
                  {money(checkout.total)} {L("sar")}
                </span>
              </div>
            </div>

            <div className="mysr-form" style={{ marginTop: 18 }} />

            <div className="muted" style={{ fontSize: ".78rem",
                                            marginTop: 12,
                                            textAlign: "center" }}>
              {L("payHint")}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

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
import { apiGet, apiPost, ApiError, openForView } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";
import PromoBanner from "@/components/PromoBanner";

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
    ar: "يُدفع مرّة واحدة فقط — ولا يدخل إيصال التجديد",
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
  payMethod: { ar: "طريقة الدفع", en: "Payment method" },
  payCard: { ar: "بطاقة", en: "Card" },
  payBank: { ar: "تحويل بنكي", en: "Bank transfer" },
  bankName: { ar: "البنك", en: "Bank" },
  bankIban: { ar: "الآيبان", en: "IBAN" },
  bankBenef: { ar: "المستفيد", en: "Beneficiary" },
  bankNote: {
    ar: "حوّل المبلغ ثم أرسل الإيصال على info@muatmd.cloud — ويُفعَّل اشتراكك بعد التحقّق",
    en: "Transfer the amount then send the receipt to info@muatmd.cloud",
  },
  copied: { ar: "نُسخ", en: "Copied" },
  couponApply: { ar: "تطبيق", en: "Apply" },
  couponChecking: { ar: "جارٍ…", en: "Checking…" },
  couponOk: { ar: "الكود صالح", en: "Code applied" },
  couponLabel: { ar: "كود خصم (اختياري)", en: "Discount code (optional)" },
  couponPlaceholder: { ar: "أدخل الكود إن كان لديك", en: "Enter your code" },
  invTitle: { ar: "تفاصيل الإيصال", en: "Receipt details" },
  invPeriod: { ar: "الفترة", en: "Period" },
  invLines: { ar: "البنود", en: "Line items" },
  invBefore: { ar: "قبل الضريبة", en: "Before VAT" },
  invVat: { ar: "ضريبة القيمة المضافة", en: "VAT" },
  invTotal: { ar: "الإجمالي", en: "Total" },
  invZatca: { ar: "الفاتورة الضريبية", en: "Tax invoice" },
  invPrint: { ar: "طباعة", en: "Print" },
  invLoading: { ar: "جارٍ…", en: "Loading…" },
  payHint: {
    ar: "بيانات بطاقتك تُرسل لبوابة الدفع مباشرةً — ولا تمرّ بخوادمنا",
    en: "Card details go straight to the payment gateway",
  },
  invoices: { ar: "الإيصالات", en: "Receipts" },
  estimateTitle: { ar: "تقدير مستحقّ الفترة", en: "Period estimate" },
  estEmployees: { ar: "الموظفون", en: "Employees" },
  estUnit: { ar: "سعر الموظف", en: "Per employee" },
  estSubtotal: { ar: "قبل الضريبة", en: "Subtotal" },
  estVat: { ar: "الضريبة", en: "VAT" },
  estTotal: { ar: "الإجمالي المتوقَّع", en: "Estimated total" },
  payNow: { ar: "دفع", en: "Pay" },
  autoRenew: { ar: "التجديد التلقائيّ", en: "Auto-renew" },
  autoRenewOn: { ar: "مفعّل", en: "On" },
  autoRenewOff: { ar: "موقوف", en: "Off" },
  autoRenewHint: {
    ar: "⚠️ يُجدَّد الاشتراك تلقائيًّا في نهاية الفترة — وإيقافه خيارك",
    en: "Renews automatically at period end",
  },
  invoiceNo: { ar: "رقم الإيصال", en: "Receipt no." },
  period: { ar: "الفترة", en: "Period" },
  status: { ar: "الحالة", en: "Status" },
  view: { ar: "عرض", en: "View" },
  cards: { ar: "البطاقات المحفوظة", en: "Saved cards" },
  defaultCard: { ar: "الافتراضية", en: "Default" },
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
  // ق-٢٧٦: التحويل البنكيّ — يُدار من لوحة المنصّة، وقد يكون معطَّلًا
  bank_transfer?: {
    enabled: boolean; bank_name?: string;
    iban?: string; beneficiary?: string;
  };
  gateway_enabled?: boolean;
};
type Sub = {
  has_subscription: boolean; active_employees: number;
  plan?: string; state_label?: string; days_remaining?: number;
  subscribed_employees?: number;
};

type CouponRes = { valid: boolean; reason?: string; name?: string };

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
  // ق-٢٧٦: البطاقة هي الافتراض — والتحويل خيارٌ لمن يفضّله
  const [payBy, setPayBy] = useState<"card" | "bank">("card");
  // ⚠️⚠️ ق-٢٨١: **كود الخصم كان بلا حقل** — يقبله الخادم
  // (`resolve_discount`) واللوحة تُنشئه، **ولا سبيل للعميل
  // ليُدخله**. فكودٌ يُعلَن عنه ولا يُستعمل.
  const [coupon, setCoupon] = useState("");
  // ⚠️⚠️ ق-٢٨٢: **كودٌ يُكتب ولا يُتحقَّق منه** — فيكتشف خطأه عند الدفع
  const [couponRes, setCouponRes] = useState<CouponRes | null>(null);
  const [couponBusy, setCouponBusy] = useState(false);

  // ⚠️ **الكود قد يكون مقيَّدًا بدورة** — فتبديلها يُبطل نتيجةً سابقة
  useEffect(() => { setCouponRes(null); }, [cycle]);

  async function checkCoupon() {
    const code = coupon.trim();
    if (!code) { setCouponRes(null); return; }
    setCouponBusy(true);
    try {
      setCouponRes(await apiPost<CouponRes>(
        "/coupon/check/", { code, cycle }));
    } catch {
      setCouponRes({ valid: false, reason: "تعذّر التحقّق" });
    } finally { setCouponBusy(false); }
  }
  // ⚠️⚠️ ق-٢٧٧: **زرّ «عرض» كان يفتح مسار JSON** — فيرى العميل نصًّا
  // خامًّا. و`openForView` للمرفقات (PDF وصور) لا للمسارات.
  const [invView, setInvView] = useState<InvoiceDetail | null>(null);
  const [invBusy, setInvBusy] = useState(false);

  async function showInvoice(id: number) {
    setInvBusy(true);
    try {
      setInvView(await apiGet<InvoiceDetail>(`/account/invoices/${id}/`));
    } catch { setInvView(null); } finally { setInvBusy(false); }
  }
  // ⚠️ **البطاقة مطفأة → يُفتح على التحويل**: فلا شاشةَ فارغة
  useEffect(() => {
    if (checkout && checkout.gateway_enabled === false) setPayBy("bank");
  }, [checkout]);
  // ق-225: واختيار الزائر من صفحة الأسعار يُستأنف هنا — فالعدد
  // والدورة يُملآن، ولا يُعيد ما اختاره قبل التسجيل.
  const [picked, setPicked] = useState<string>("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem("pick_plan");
      if (!raw) return;
      const v = JSON.parse(raw) as {
        code?: string; employees?: number; cycle?: string };
      if (v.employees && v.employees > 0) setCount(v.employees);
      if (v.cycle === "annual" || v.cycle === "monthly") setCycle(v.cycle);
      if (v.code) setPicked(v.code);
      localStorage.removeItem("pick_plan");
    } catch { /* اختيارٌ تالف لا يكسر الصفحة */ }
  }, []);
  const [paying, setPaying] = useState<number | null>(null);

  // ق-181: **الفواتير والبطاقات** — كشفهما الجرد يتيمَين.
  //
  // ⚠️ **والعميل يرى ما يدفع**: فاشتراكٌ بلا سجلٍّ **يُدفع على
  // الثقة وحدها**.
  type Invoice = {
    id: number; invoice_no: string; period: string;
    total: string; status: string; status_label?: string;
    issued_at?: string; paid_at?: string | null;
    // ق-182: **الفاتورة الزكاتية** من «معتمد المحاسبيّ»
    zatca_invoice_no?: string; zatca_issued_at?: string | null;
  };
  // ق-٢٧٧: تفاصيل الفاتورة — بنودٌ وضريبة، تُجلب عند العرض لا مع القائمة
  type InvoiceDetail = Invoice & {
    lines?: { description: string; amount: string;
              note?: string; is_setup_fee?: boolean }[];
    before_vat?: string; vat_rate?: string; vat_amount?: string;
    note?: string;
  };
  type Card = {
    id: number; brand?: string; last4?: string;
    exp_month?: number; exp_year?: number; is_default?: boolean;
  };
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  // ق-206: **تقدير المستحقّ والتجديد التلقائيّ** — ⚠️ **شفافيةٌ
  // تمنع النزاعات**: فالعميل يعرف **ما سيُحاسب به قبل الفاتورة**.
  const [estimate, setEstimate] = useState<{
    period: string; employees: number; plan: string;
    unit_price: string; subtotal: string; vat: string;
    total: string; note?: string } | null>(null);
  const [autoRenew, setAutoRenew] = useState<boolean | null>(null);
  const [renewBusy, setRenewBusy] = useState(false);

  // ق-208: **مزايا باقتك** — ⚠️ **والمقفلة تُعرض لا تُخفى**:
  // **فإخفاؤها يُضيّع فرصة بيع** (ق-161).
  const [feat, setFeat] = useState<{
    key: string; name_ar: string; module: string;
    is_core: boolean; enabled: boolean }[]>([]);
  const [lockedCount, setLockedCount] = useState(0);
  const [showLocked, setShowLocked] = useState(false);

  /** ⚠️ **والتجديد خيار العميل** (ق-48) — لا يُفرض */
  const toggleRenew = async (on: boolean) => {
    setRenewBusy(true);
    setErr("");
    try {
      await apiPost("/account/auto-renew/", { auto_renew: on });
      setAutoRenew(on);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setRenewBusy(false); }
  };

  /** دفعُ فاتورةٍ غير مدفوعة */
  const payInvoice = async (invId: number) => {
    setErr("");
    try {
      const out = await apiPost<{ redirect_url?: string }>(
        `/account/invoices/${invId}/pay/`, {});
      if (out?.redirect_url) window.location.href = out.redirect_url;
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };
  const [cards, setCards] = useState<Card[]>([]);

  useEffect(() => {
    apiGet<Invoice[] | { rows: Invoice[] }>("/account/invoices/")
      .then((d) => setInvoices(Array.isArray(d) ? d : (d.rows || [])))
      .catch(() => setInvoices([]));
    apiGet<Card[] | { rows: Card[] }>("/account/cards/")
      .then((d) => setCards(Array.isArray(d) ? d : (d.rows || [])))
      .catch(() => setCards([]));
    // ⚠️ **و٤٠٤ تعني: لا اشتراكَ نشطًا** — لا خطأً
    apiGet<typeof estimate>("/billing/estimate/")
      .then(setEstimate)
      .catch(() => setEstimate(null));

    apiGet<{ features: typeof feat; locked_count: number }>(
      "/billing/subscription/")
      .then((d) => {
        setFeat(d.features || []);
        setLockedCount(d.locked_count || 0);
      })
      .catch(() => setFeat([]));
  }, []);

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
        // ق-٢٨١: كود الخصم — يُرسَل فارغًا كـundefined فلا يُفسّر كودًا خاطئًا
        coupon_code: coupon.trim() || undefined,
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
      {/* ق-٢٨١: شريط العرض — يُدار من لوحة المنصّة، ولا يظهر إن عُطّل */}
      <PromoBanner />
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
        
        {/* ⚠️⚠️ ق-٢٨١: **كود الخصم كان بلا حقل** — يقبله الخادم وتُنشئه
            اللوحة، **ولا سبيل للعميل ليُدخله**. */}
        <div style={{ marginTop: 12, maxWidth: 320 }}>
          <label className="muted" style={{ fontSize: ".82rem" }}>
            {L("couponLabel")}
          </label>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <input className="input grow" value={coupon} dir="ltr"
                   placeholder={L("couponPlaceholder")}
                   style={{ textTransform: "uppercase" }}
                   onChange={(e) => {
                     setCoupon(e.target.value.toUpperCase());
                     setCouponRes(null);
                   }}
                   onKeyDown={(e) => e.key === "Enter" && checkCoupon()} />
            <button className="btn btn-sm" type="button"
                    disabled={couponBusy || !coupon.trim()}
                    onClick={checkCoupon}>
              {couponBusy ? L("couponChecking") : L("couponApply")}
            </button>
          </div>
          {couponRes && (
            <div style={{ fontSize: ".82rem", marginTop: 6,
                          color: couponRes.valid
                                 ? "var(--ok, #0a7a3f)"
                                 : "var(--danger, #b42318)" }}>
              {couponRes.valid
                ? `${L("couponOk")} — ${couponRes.name || ""}`
                : couponRes.reason}
            </div>
          )}
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
              // ق-225: والباقة التي اختارها قبل التسجيل تُبرَز —
              // فلا يبحث عنها من جديد.
              ...(picked && picked === p.code
                ? { borderColor: "var(--teal)",
                    boxShadow: "0 0 0 2px var(--teal-soft)" }
                : {}),
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

      {/* ق-٢٧٧: عرض الفاتورة في الشاشة — لا مسارًا خامًّا في تبويب */}
      {invView && (
        <div onClick={() => setInvView(null)}
             style={{ position: "fixed", inset: 0, zIndex: 90,
                      background: "rgba(16,28,38,.5)", display: "grid",
                      placeItems: "center", padding: 20, overflowY: "auto" }}>
          <div className="card" onClick={(e) => e.stopPropagation()}
               style={{ padding: 24, maxWidth: 520, width: "100%" }}>
            <div className="spread">
              <h3 style={{ margin: 0 }}>{L("invTitle")}</h3>
              <span className="num muted">{invView.invoice_no}</span>
            </div>

            <div style={{ marginTop: 14, display: "grid", gap: 6,
                          fontSize: ".9rem" }}>
              <div className="spread">
                <span className="muted">{L("invPeriod")}</span>
                <span>{invView.period}</span>
              </div>
              {invView.status_label && (
                <div className="spread">
                  <span className="muted">{L("status")}</span>
                  <span>{invView.status_label}</span>
                </div>
              )}
            </div>

            {!!invView.lines?.length && (
              <div style={{ marginTop: 16 }}>
                <div className="muted" style={{ fontSize: ".82rem",
                                                marginBottom: 6 }}>
                  {L("invLines")}
                </div>
                {invView.lines.map((ln, i) => (
                  <div key={i} className="spread"
                       style={{ padding: "8px 0", fontSize: ".9rem",
                                borderBottom: "1px solid var(--line)" }}>
                    <div>
                      <div>{ln.description}</div>
                      {ln.note && (
                        <div className="muted" style={{ fontSize: ".78rem" }}>
                          {ln.note}
                        </div>
                      )}
                    </div>
                    <span className="num">{money(ln.amount)}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 14, display: "grid", gap: 6,
                          fontSize: ".9rem" }}>
              {invView.before_vat && (
                <div className="spread">
                  <span className="muted">{L("invBefore")}</span>
                  <span className="num">{money(invView.before_vat)}</span>
                </div>
              )}
              {invView.vat_amount && (
                <div className="spread">
                  <span className="muted">
                    {L("invVat")} {invView.vat_rate
                      ? `(${invView.vat_rate}%)` : ""}
                  </span>
                  <span className="num">{money(invView.vat_amount)}</span>
                </div>
              )}
              <div className="spread" style={{ fontWeight: 700,
                                               fontSize: "1rem" }}>
                <span>{L("invTotal")}</span>
                <span className="num">
                  {money(invView.total)} {L("sar")}
                </span>
              </div>
            </div>

            {/* ⚠️ **الفاتورة الضريبية من «معتمد المحاسبيّ»** (ق-١٨٢) —
                وهذا عرضٌ للاشتراك لا مستندٌ ضريبيّ. */}
            {invView.note && (
              <div className="muted" style={{ fontSize: ".78rem",
                                              marginTop: 14 }}>
                {invView.note}
              </div>
            )}

            <div style={{ display: "flex", gap: 8, marginTop: 18,
                          justifyContent: "flex-end" }}>
              <button className="btn btn-sm"
                      onClick={() => window.print()}>
                {L("invPrint")}
              </button>
              <button className="btn btn-sm btn-ghost"
                      onClick={() => setInvView(null)}>
                {L("close")}
              </button>
            </div>
          </div>
        </div>
      )}

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

            {/* ⚠️ ق-٢٧٦: **لا يُعرض خيارٌ لا يعمل** — فتظهر المتاحة
                وحدها، ولا أزرارَ أصلًا إن كانت واحدة. */}
            {checkout.bank_transfer?.enabled
             && checkout.gateway_enabled !== false && (
              <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                {(["card", "bank"] as const).map((m) => (
                  <button key={m} type="button"
                    className={`btn btn-sm ${payBy === m ? "btn-primary" : ""}`}
                    style={{ flex: 1 }}
                    onClick={() => setPayBy(m)}>
                    {L(m === "card" ? "payCard" : "payBank")}
                  </button>
                ))}
              </div>
            )}

            <div className="mysr-form"
                 style={{ marginTop: 18,
                          display: (payBy === "card"
                                    && checkout.gateway_enabled !== false)
                                   ? undefined : "none" }} />

            {/* ⚠️ ق-٢٧٦: **التحويل يتمّ خارج معتمد** (قرار جواد): تُعرض
                البيانات وملخّص الدفع، **ولا تُنشأ فاتورة هنا**، والتفعيل
                بيد المشرف بعد التحقّق من التحويل. */}
            {payBy === "bank" && checkout.bank_transfer?.enabled && (
              <div style={{ marginTop: 18, display: "grid", gap: 10 }}>
                {([["bankName", checkout.bank_transfer.bank_name],
                   ["bankIban", checkout.bank_transfer.iban],
                   ["bankBenef", checkout.bank_transfer.beneficiary]] as const)
                  .filter(([, v]) => !!v)
                  .map(([k, v]) => (
                    <div key={k} className="spread"
                         style={{ fontSize: ".9rem", gap: 8 }}>
                      <span className="muted">{L(k)}</span>
                      <span className="num" dir="ltr"
                            style={{ fontWeight: 600, wordBreak: "break-all",
                                     cursor: "pointer" }}
                            title={L("copied")}
                            onClick={() => navigator.clipboard
                              ?.writeText(String(v))}>
                        {v}
                      </span>
                    </div>
                  ))}
                <div className="muted"
                     style={{ fontSize: ".8rem", marginTop: 6,
                              lineHeight: 1.7 }}>
                  {L("bankNote")}
                </div>
              </div>
            )}

            <div className="muted" style={{ fontSize: ".78rem",
                                            marginTop: 12,
                                            textAlign: "center" }}>
              {/* ⚠️ ق-٢٨٥: **لا تُوعَد ببوابةٍ لا تعمل** — كانت الجملة
                  تظهر مع التحويل البنكيّ أيضًا، وحتى مع إيقاف البطاقة. */}
              {payBy === "card" && checkout.gateway_enabled !== false
                ? L("payHint") : null}
            </div>
          </div>
        </div>
      )}

      {/* ق-206: **تقدير مستحقّ الفترة** — ⚠️ **شفافيةٌ تمنع
          النزاعات**: فالعميل يعرف ما سيُحاسب به **قبل الفاتورة** */}
      {estimate && (
        <div className="card" style={{ padding: 18 }}>
          <div className="spread" style={{ marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: "1rem" }}>
              {L("estimateTitle")}
            </h3>
            <span className="muted num" style={{ fontSize: ".82rem" }}>
              {estimate.period}
            </span>
          </div>

          <div style={{ display: "grid", gap: 12,
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(120px, 1fr))" }}>
            {([[L("estEmployees"), String(estimate.employees)],
               [L("estUnit"), estimate.unit_price],
               [L("estSubtotal"), estimate.subtotal],
               [L("estVat"), estimate.vat]] as const).map(
              ([lbl, val]) => (
              <div key={lbl}>
                <div className="muted" style={{ fontSize: ".74rem",
                                                marginBottom: 3 }}>
                  {lbl}
                </div>
                <div className="num">{val}</div>
              </div>
            ))}
          </div>

          <div className="spread" style={{ marginTop: 14,
                paddingTop: 10,
                borderTop: "1px solid var(--line)" }}>
            <strong>{L("estTotal")}</strong>
            <span className="num" style={{ fontSize: "1.15rem",
                                           fontWeight: 700 }}>
              {estimate.total}
            </span>
          </div>

          {estimate.note && (
            <div className="muted" style={{ fontSize: ".78rem",
                                            marginTop: 8 }}>
              {estimate.note}
            </div>
          )}

          {/* ق-206: ⚠️ **والتجديد خيار العميل** (ق-48) */}
          <div className="spread" style={{ marginTop: 14,
                paddingTop: 10,
                borderTop: "1px solid var(--line)" }}>
            <div>
              <strong style={{ fontSize: ".9rem" }}>
                {L("autoRenew")}
              </strong>
              <div className="muted" style={{ fontSize: ".76rem",
                                              marginTop: 2 }}>
                {L("autoRenewHint")}
              </div>
            </div>
            <button className="btn btn-sm"
                    disabled={renewBusy}
                    onClick={() => toggleRenew(!autoRenew)}>
              {renewBusy ? "…"
                : autoRenew ? L("autoRenewOn") : L("autoRenewOff")}
            </button>
          </div>
        </div>
      )}

      {/* ق-181: **الفواتير** — فالعميل يرى ما يدفع */}
      {invoices.length > 0 && (
        <div className="card" style={{ overflow: "hidden" }}>
          <div style={{ padding: "14px 18px 0" }}>
            <h3 style={{ margin: 0, fontSize: "1rem" }}>
              {L("invoices")}
            </h3>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>{L("invoiceNo")}</th>
                <th>{L("period")}</th>
                <th style={{ width: 120 }}>{L("total")}</th>
                <th style={{ width: 110 }}>{L("status")}</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    {/* ⚠️ **والزكاتية أوّلًا** — فهي المعتمدة
                        نظامًا، والداخليّ مرجعُ الدفع */}
                    <span className="num">
                      {inv.zatca_invoice_no || inv.invoice_no}
                    </span>
                    {inv.zatca_invoice_no && (
                      <div className="muted num"
                           style={{ fontSize: ".72rem" }}>
                        {inv.invoice_no}
                      </div>
                    )}
                  </td>
                  <td className="muted" style={{ fontSize: ".84rem" }}>
                    {inv.period}
                  </td>
                  <td><span className="num">{inv.total}</span></td>
                  <td>
                    <span className={`badge ${
                      inv.status === "paid" ? "badge-ok" : "badge-warn"}`}>
                      {inv.status_label || inv.status}
                    </span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    <div className="row" style={{ gap: 5,
                           justifyContent: "flex-end" }}>
                      {/* ق-206: **ودفعُ فاتورةٍ غير مدفوعة** */}
                      {inv.status !== "paid" && (
                        <button className="btn btn-sm btn-primary"
                                onClick={() => payInvoice(inv.id)}>
                          {L("payNow")}
                        </button>
                      )}
                      <button className="btn btn-sm btn-ghost"
                        disabled={invBusy}
                        onClick={() => showInvoice(inv.id)}>
                        {invBusy ? L("invLoading") : L("view")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ق-181: **البطاقات المحفوظة** */}
      {cards.length > 0 && (
        <div className="card" style={{ padding: 18 }}>
          <h3 style={{ margin: "0 0 10px", fontSize: "1rem" }}>
            {L("cards")}
          </h3>
          {cards.map((c) => (
            <div key={c.id} className="row"
                 style={{ gap: 10, alignItems: "center",
                          padding: "7px 0" }}>
              <span className="num">
                {(c.brand || "").toUpperCase()} ···· {c.last4 || "----"}
              </span>
              {c.exp_month && (
                <span className="muted num" style={{ fontSize: ".8rem" }}>
                  {String(c.exp_month).padStart(2, "0")}/{c.exp_year}
                </span>
              )}
              {c.is_default && (
                <span className="badge badge-ok">{L("defaultCard")}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

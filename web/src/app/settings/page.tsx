"use client";

/**
 * الإعدادات — ثلاثة أقسام:
 *   إعدادات الرواتب · الاشتراك · الفريق والصلاحيات
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcPayroll, IcUsers, IcWallet } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الإعدادات", en: "Settings" },
  general: { ar: "إعدادات عامة", en: "General" },
  users: { ar: "المستخدمون", en: "Users" },
  company: { ar: "بيانات المنشأة", en: "Company details" },
  holidays: { ar: "العطل الرسمية", en: "Public holidays" },
  exemptions: { ar: "الإعفاء من البصمة", en: "Attendance exemptions" },
  exemptionsHint: {
    ar: "من لا يُطالَب ببصمة ولا يُعدّ غائبًا",
    en: "Employees not required to punch",
  },
  holidaysHint: {
    ar: "عطل الشركة — لا تُخصم من الرصيد ولا من الأجر",
    en: "Company holidays — not deducted from balance or pay",
  },
  companyHint: {
    ar: "السجل التجاري والأرقام النظامية وبريد التواصل",
    en: "Registration, statutory numbers and contact email",
  },
  notifTpl: { ar: "قوالب الإشعارات", en: "Notification templates" },
  notifTplHint: {
    ar: "نصّ كل إشعار في قنواته",
    en: "Text of each notification",
  },
  bankTpl: { ar: "قوالب البنوك", en: "Bank templates" },
  bankTplHint: {
    ar: "صيغة ملف الرواتب لكل بنك",
    en: "Payroll file format per bank",
  },
  grades: { ar: "السلّم الوظيفي", en: "Job scale" },
  gradesHint: {
    ar: "المراتب ودرجاتها — اختياري",
    en: "Grades and steps — optional",
  },
  payComponents: { ar: "بنود الأجر", en: "Pay components" },
  payComponentsHint: {
    ar: "الاستحقاقات والاستقطاعات وأعلامها",
    en: "Earnings, deductions and flags",
  },
  devices: { ar: "أجهزة البصمة", en: "Punch devices" },
  devicesHint: {
    ar: "الأجهزة المصرَّح لها بإرسال البصمات",
    en: "Devices allowed to submit punches",
  },
  shifts: { ar: "فترات العمل", en: "Shifts" },
  shiftsHint: {
    ar: "أوقات الدوام وأيامه وفترات السماح",
    en: "Working hours, days and grace",
  },
  chains: { ar: "سلاسل الاعتماد", en: "Approval chains" },
  chainsHint: {
    ar: "من يعتمد كل نوع من الطلبات",
    en: "Who approves each request type",
  },
  leaveTypes: { ar: "أنواع الإجازات", en: "Leave types" },
  leaveTypesHint: {
    ar: "سياسات الاستحقاق والأجر والترحيل",
    en: "Entitlement and pay policies",
  },
  usersHint: {
    ar: "حسابات الدخول وصلاحياتها",
    en: "Login accounts and permissions",
  },
  payroll: { ar: "الإعدادات العامة", en: "General settings" },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت التغييرات", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا صلاحية لهذا القسم", en: "No access to this section" },
  noSub: { ar: "لا اشتراك لهذا الحساب بعد", en: "No subscription yet" },
  browsePlans: { ar: "عرض الباقات والاشتراك", en: "View plans" },
  noSubHint: {
    ar: "يُفعّله مدير المنصة — راجعه لتفعيل اشتراك منشأتك",
    en: "Activated by the platform administrator",
  },
  // إعدادات الرواتب
  eosbBasis: { ar: "أجر مكافأة نهاية الخدمة", en: "EOSB wage basis" },
  eosbHint: {
    ar: "يجب تحديده قبل أول مسير مستحقات — الصمت هنا قرار مالي لم يتخذه أحد",
    en: "Must be set before the first settlement run",
  },
  basicHousingTransport: {
    ar: "الراتب الأساسي + بدل السكن والمواصلات",
    en: "Basic + housing and transport",
  },
  basicAll: {
    ar: "الراتب الأساسي + جميع البدلات",
    en: "Basic + all allowances",
  },
  mobilePunch: { ar: "بصمة الجوال", en: "Mobile punch" },
  mobilePunchHint: {
    ar: "الافتراضي للشركة — وفترة العمل وملف الموظف يغلبانه",
    en: "Company default — shift and employee override it",
  },
  enabled: { ar: "مفعّلة", en: "Enabled" },
  disabled: { ar: "معطّلة", en: "Disabled" },
  basicOnly: { ar: "الأساسي فقط", en: "Basic only" },
  basicHousing: { ar: "الأساسي + السكن", en: "Basic + housing" },
  flagged: { ar: "حسب أعلام المكوّنات", en: "By component flags" },
  notSet: { ar: "لم يُحدَّد بعد", en: "Not set" },
  daysPerMonth: { ar: "أيام الشهر للاحتساب", en: "Days per month" },
  varianceThreshold: { ar: "عتبة تنبيه الفروقات %", en: "Variance threshold %" },
  advancesEnabled: { ar: "تمكين نظام السلف", en: "Enable advances" },
  advanceMax: { ar: "الحد الأقصى للسلفة", en: "Max advance amount" },
  advanceMaxMonths: { ar: "الحد بعدد الرواتب", en: "Max in salary months" },
  advanceBlock: {
    ar: "منع سلفة ثانية قبل سداد الأولى",
    en: "Block second advance while one is outstanding",
  },
  payslipGosi: {
    ar: "عرض حصة صاحب العمل في القسيمة",
    en: "Show employer GOSI share on payslip",
  },
  payslipLeave: {
    ar: "عرض رصيد الإجازات في القسيمة",
    en: "Show leave balance on payslip",
  },
  payslipPrev: {
    ar: "عرض مقارنة بالشهر السابق",
    en: "Show previous month comparison",
  },
  payslipHint: {
    ar: "القسيمة للراتب وحده — كل بند إضافي يفتح بابًا لسؤال جديد",
    en: "The payslip is for pay only",
  },
  // الاشتراك
  plan: { ar: "الباقة", en: "Plan" },
  state: { ar: "الحالة", en: "State" },
  cycle: { ar: "الدورة", en: "Cycle" },
  periodEnd: { ar: "ينتهي في", en: "Ends on" },
  daysLeft: { ar: "المتبقي", en: "Days left" },
  days: { ar: "يوم", en: "days" },
  autoRenew: { ar: "التجديد التلقائي", en: "Auto renewal" },
  paymentMethod: { ar: "طريقة الدفع", en: "Payment method" },
  savedCard: { ar: "البطاقة المحفوظة", en: "Saved card" },
  invoices: { ar: "سجلّ المدفوعات", en: "Payment history" },
  payDate: { ar: "التاريخ", en: "Date" },
  payMethod: { ar: "الوسيلة", en: "Method" },
  payPeriod: { ar: "الفترة", en: "Period" },
  invoiceNote: {
    ar: "تصلك الفاتورة الضريبية بالبريد فور نجاح الدفع",
    en: "Your tax invoice arrives by email once payment succeeds",
  },
  amount: { ar: "المبلغ", en: "Amount" },
  status: { ar: "الحالة", en: "Status" },
  dueDate: { ar: "الاستحقاق", en: "Due" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  none: { ar: "لا شيء", en: "None" },
  empty: { ar: "لا سجلات", en: "No records" },
};

const SECTIONS = ["payroll", "subscription"] as const;
type Section = (typeof SECTIONS)[number];

type PayrollSettings = {
  eosb_wage_basis: string;
  allow_mobile_punch: boolean;
  payroll_days_per_month: number;
  variance_threshold_percent: string;
  advances_enabled: boolean;
  advance_max_amount: string | null;
  advance_max_months_of_salary: string | null;
  advance_block_if_outstanding: boolean;
  payslip_show_employer_gosi: boolean;
  payslip_show_leave_balance: boolean;
  payslip_show_previous_month: boolean;
  [k: string]: unknown;
};

type Subscription = {
  state: string;
  state_label: string;
  plan: string | null;
  cycle_label: string;
  payment_method: string;
  auto_renew: boolean;
  period_end: string | null;
  days_left: number | null;
  saved_card: { brand: string; last_four: string } | null;
};

type PaymentRow = {
  id: number; date: string; amount: string;
  status: string; status_label: string; paid: boolean;
  period: string; method: string; last4: string;
};


function money(v: unknown) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : String(v ?? "—");
}


/* ══ صف إعداد — خارج المكوّن الرئيسي ══ */

function Row({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{
      padding: "12px 0", borderBottom: "1px solid var(--line)",
    }}>
      <div className="spread" style={{ gap: 16 }}>
        <div className="grow">
          <div style={{ fontWeight: 500 }}>{label}</div>
          {hint && (
            <div className="muted" style={{ fontSize: ".82rem", marginTop: 2 }}>
              {hint}
            </div>
          )}
        </div>
        <div style={{ minWidth: 180 }}>{children}</div>
      </div>
    </div>
  );
}

/* ══ إعدادات الرواتب ══ */

function PayrollPanel({
  L,
}: {
  L: (k: string, f?: string) => string;
}) {
  const [data, setData] = useState<PayrollSettings | null>(null);
  /**
   * البند الذي يظهر ثم يُمنع عند الدخول يوهم بقدرة لا يملكها
   * المستخدم — فما لا يملكه لا يراه.
   */
  const [perms, setPerms] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [denied, setDenied] = useState(false);


  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) => setPerms(new Set(d.permissions || [])))
      .catch(() => setPerms(new Set()));
  }, []);
  useEffect(() => {
    apiGet<PayrollSettings>("/payroll/settings/")
      .then((d) => { setData(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.isForbidden);
        setBusy(false);
      });
  }, []);

  const set = (k: string, v: unknown) =>
    setData((s) => (s ? { ...s, [k]: v } : s));

  async function save() {
    if (!data) return;
    setSaving(true);
    setMsg("");
    try {
      await apiPut("/payroll/settings/", data);
      setMsg(L("saved"));
      setTimeout(() => setMsg(""), 3000);
    } catch (e) {
      setMsg((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (busy) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (denied || !data) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("noAccess")}
      </div>
    );
  }

  const basisNotSet = data.eosb_wage_basis === "not_set";

  return (
    <div className="stack">
      {basisNotSet && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "11px 15px", borderRadius: "var(--radius-sm)",
          fontWeight: 500, display: "flex", alignItems: "center", gap: 8,
        }}>
          <IcAlert size={18} />
          {L("eosbHint")}
        </div>
      )}

      {/* ══ إعدادات عامة ══
          بطاقات مجمّعة لا تبويبات: البنود تكثر مع نمو النظام،
          والتبويب يضيق بها. */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <h3 style={{
          fontSize: "1rem", padding: "14px 20px",
          borderBottom: "1px solid var(--line)", color: "var(--teal)",
        }}>
          {L("general")}
        </h3>
        {perms.has("company.view") && (
        <Link href="/settings/company" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("company")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("companyHint")}
          </span>
        </Link>
        )}
        {perms.has("attendance.view") && (
        <Link href="/settings/exemptions" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("exemptions")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("exemptionsHint")}
          </span>
        </Link>
        )}
        {perms.has("org.view") && (
        <Link href="/settings/holidays" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("holidays")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("holidaysHint")}
          </span>
        </Link>
        )}
        {perms.has("access.view") && (
        <Link href="/settings/users" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("users")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("usersHint")}
          </span>
        </Link>
        )}
        {/* البنود تظهر لمن يقرأ — والوجود ثابت، والقدرة
            على التعديل هي المتغيّرة (ق-76) */}
        {perms.has("company.view") && (
        <Link href="/settings/notification-templates" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("notifTpl")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("notifTplHint")}
          </span>
        </Link>
        )}
        {perms.has("payroll.view") && (
        <Link href="/settings/bank-templates" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("bankTpl")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("bankTplHint")}
          </span>
        </Link>
        )}
        {perms.has("employees.view") && (
        <Link href="/settings/job-grades" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("grades")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("gradesHint")}
          </span>
        </Link>
        )}
        {perms.has("payroll.view") && (
        <Link href="/settings/pay-components" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("payComponents")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("payComponentsHint")}
          </span>
        </Link>
        )}
        {perms.has("sites.view") && (
        <Link href="/settings/devices" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("devices")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("devicesHint")}
          </span>
        </Link>
        )}
        {perms.has("attendance.view") && (
        <Link href="/settings/shifts" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("shifts")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("shiftsHint")}
          </span>
        </Link>
        )}
        {perms.has("leaves.view") && (
        <Link href="/settings/approval-chains" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
          borderBottom: "1px solid var(--line)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("chains")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("chainsHint")}
          </span>
        </Link>
        )}
        {perms.has("leaves.view") && (
        <Link href="/settings/leave-types" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("leaveTypes")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("leaveTypesHint")}
          </span>
        </Link>
        )}
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 6 }}>{L("payroll")}</h3>

        <Row label={L("eosbBasis")} hint={L("eosbHint")}>
          <select className="select" value={data.eosb_wage_basis}
            onChange={(e) => set("eosb_wage_basis", e.target.value)}>
            {data.eosb_wage_basis === "not_set" && (
              <option value="not_set">{L("notSet")}</option>
            )}
            <option value="basic_only">{L("basicOnly")}</option>
            <option value="basic_housing">{L("basicHousing")}</option>
            <option value="basic_housing_transport">
              {L("basicHousingTransport")}
            </option>
            <option value="basic_all">{L("basicAll")}</option>
            {data.eosb_wage_basis === "flagged" && (
              <option value="flagged">{L("flagged")}</option>
            )}
          </select>
        </Row>

        <Row label={L("mobilePunch")} hint={L("mobilePunchHint")}>
          <select className="select"
            value={data.allow_mobile_punch ? "1" : "0"}
            onChange={(e) =>
              set("allow_mobile_punch", e.target.value === "1")}>
            <option value="1">{L("enabled")}</option>
            <option value="0">{L("disabled")}</option>
          </select>
        </Row>

        <Row label={L("daysPerMonth")}>
          <input type="number" className="input"
            value={data.payroll_days_per_month}
            onChange={(e) => set("payroll_days_per_month",
                                 Number(e.target.value))} />
        </Row>

        <Row label={L("varianceThreshold")}>
          <input type="number" className="input"
            value={data.variance_threshold_percent}
            onChange={(e) => set("variance_threshold_percent",
                                 e.target.value)} />
        </Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 6 }}>
          {L("advancesEnabled")}
        </h3>

        <Row label={L("advancesEnabled")}>
          <select className="select"
            value={data.advances_enabled ? "1" : "0"}
            onChange={(e) => set("advances_enabled", e.target.value === "1")}>
            <option value="1">{L("yes")}</option>
            <option value="0">{L("no")}</option>
          </select>
        </Row>

        {data.advances_enabled && (
          <>
            <Row label={L("advanceMax")}>
              <input type="number" className="input"
                value={data.advance_max_amount ?? ""}
                onChange={(e) => set("advance_max_amount",
                                     e.target.value || null)} />
            </Row>
            <Row label={L("advanceMaxMonths")}>
              <input type="number" className="input"
                value={data.advance_max_months_of_salary ?? ""}
                onChange={(e) => set("advance_max_months_of_salary",
                                     e.target.value || null)} />
            </Row>
            <Row label={L("advanceBlock")}>
              <select className="select"
                value={data.advance_block_if_outstanding ? "1" : "0"}
                onChange={(e) => set("advance_block_if_outstanding",
                                     e.target.value === "1")}>
                <option value="1">{L("yes")}</option>
                <option value="0">{L("no")}</option>
              </select>
            </Row>
          </>
        )}
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>
          {L("payslipHint")}
        </h3>

        {[
          ["payslip_show_employer_gosi", "payslipGosi"],
          ["payslip_show_leave_balance", "payslipLeave"],
          ["payslip_show_previous_month", "payslipPrev"],
        ].map(([key, label]) => (
          <Row key={key} label={L(label)}>
            <select className="select"
              value={data[key] ? "1" : "0"}
              onChange={(e) => set(key, e.target.value === "1")}>
              <option value="1">{L("yes")}</option>
              <option value="0">{L("no")}</option>
            </select>
          </Row>
        ))}
      </div>

      <div className="row">
        {perms.has("company.edit") && (
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          <IcCheck size={17} />
          {saving ? L("saving") : L("save")}
        </button>
        )}
        {msg && <span className="badge badge-ok">{msg}</span>}
      </div>
    </div>
  );
}


/* ══ لوحة الاشتراك ══ */

function SubscriptionPanel({
  L,
}: {
  L: (k: string, f?: string) => string;
}) {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Subscription>("/account/subscription/").catch(() => null),
      apiGet<PaymentRow[]>("/account/payments/").catch(() => []),
    ]).then(([s, inv]) => {
      setSub(s);
      setPayments(inv);
      setBusy(false);
    });
  }, []);

  if (busy) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (!sub) {
    // «لا اشتراك» ليست «لا صلاحية»: من لا اشتراك لحسابه سيظنّ
    // أنه ممنوع فيراجع مديره بلا سبب.
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <div style={{ fontWeight: 500 }}>{L("noSub")}</div>
        <div style={{ fontSize: ".86rem", marginTop: 6 }}>
          {L("noSubHint")}
        </div>
        <Link href="/subscribe" className="btn btn-primary"
              style={{ marginTop: 16 }}>
          {L("browsePlans")}
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="card" style={{ padding: 20 }}>
        <Row label={L("plan")}>
          <strong>{sub.plan || L("none")}</strong>
        </Row>
        <Row label={L("state")}>
          <span className={
            sub.state === "active" ? "badge badge-ok"
              : sub.state === "trial" ? "badge badge-teal"
              : "badge badge-warn"
          }>
            {sub.state_label}
          </span>
        </Row>
        <Row label={L("cycle")}>{sub.cycle_label}</Row>
        <Row label={L("periodEnd")}>
          {sub.period_end
            ? <span className="num">{sub.period_end}</span> : "—"}
        </Row>
        {sub.days_left != null && (
          <Row label={L("daysLeft")}>
            <span className="num" style={{
              color: sub.days_left <= 5 ? "var(--copper)" : undefined,
              fontWeight: 600,
            }}>
              {sub.days_left}
            </span>{" "}
            {L("days")}
          </Row>
        )}
        <Row label={L("autoRenew")}>
          <span className={sub.auto_renew ? "badge badge-ok" : "badge"}>
            {sub.auto_renew ? L("yes") : L("no")}
          </span>
        </Row>
        <Row label={L("savedCard")}>
          {sub.saved_card
            ? <span className="num">
                {sub.saved_card.brand} •••• {sub.saved_card.last_four}
              </span>
            : L("none")}
        </Row>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h3 style={{ fontSize: "1rem", margin: 0 }}>{L("invoices")}</h3>
            <div className="muted" style={{ fontSize: ".8rem", marginTop: 2 }}>
              {L("invoiceNote")}
            </div>
          </div>
        </div>
        {payments.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ textAlign: "end" }}>{L("payDate")}</th>
                <th style={{ textAlign: "end" }}>{L("amount")}</th>
                <th style={{ textAlign: "end" }}>{L("payPeriod")}</th>
                <th>{L("payMethod")}</th>
                <th>{L("status")}</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{p.date}</span>
                  </td>
                  <td style={{ textAlign: "end", fontWeight: 600 }}>
                    <span className="num">{money(p.amount)}</span>
                  </td>
                  <td style={{ textAlign: "end" }} className="muted">
                    <span className="num">{p.period || "—"}</span>
                  </td>
                  <td className="muted">
                    {p.method ? `${p.method} ••${p.last4}` : "—"}
                  </td>
                  <td>
                    <span className={p.paid ? "badge badge-ok" : "badge"}>
                      {p.status_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ══ الشاشة ══ */

export default function SettingsPage() {
  const { L } = useT(T);
  // التبويب في الرابط لا في الحالة: يبقى عند التحديث، ويُفتح
  // مباشرةً من قائمة الحساب (?tab=subscription).
  const params = useSearchParams();
  const router = useRouter();
  const fromUrl = params.get("tab") as Section | null;
  const [section, setSectionState] = useState<Section>(
    fromUrl && SECTIONS.includes(fromUrl) ? fromUrl : "payroll");

  const setSection = (s: Section) => {
    setSectionState(s);
    router.replace(s === "payroll" ? "/settings" : `/settings?tab=${s}`,
                   { scroll: false });
  };

  useEffect(() => {
    if (fromUrl && SECTIONS.includes(fromUrl) && fromUrl !== section) {
      setSectionState(fromUrl);
    }
  }, [fromUrl, section]);

  const ICONS: Record<Section, React.ComponentType<{ size?: number }>> = {
    payroll: IcPayroll,
    subscription: IcWallet,
  };

  return (
    <div className="stack">
      <h1>{L("title")}</h1>

      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {SECTIONS.map((s) => {
          const Icon = ICONS[s];
          return (
            <button key={s}
              className={`btn btn-sm ${section === s ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setSection(s)}>
              <Icon size={16} />
              {L(s)}
            </button>
          );
        })}
      </div>

      {section === "payroll" && <PayrollPanel L={L} />}
      {section === "subscription" && <SubscriptionPanel L={L} />}
    </div>
  );
}

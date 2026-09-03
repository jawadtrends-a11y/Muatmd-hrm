"use client";

/**
 * الإعدادات — ثلاثة أقسام:
 *   إعدادات الرواتب · الاشتراك · الفريق والصلاحيات
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcPayroll, IcUsers, IcWallet } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الإعدادات", en: "Settings" },
  general: { ar: "إعدادات عامة", en: "General" },
  users: { ar: "المستخدمون", en: "Users" },
  usersHint: {
    ar: "حسابات الدخول وصلاحياتها",
    en: "Login accounts and permissions",
  },
  payroll: { ar: "إعدادات الرواتب", en: "Payroll settings" },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  team: { ar: "الفريق", en: "Team" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت التغييرات", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا صلاحية لهذا القسم", en: "No access to this section" },
  // إعدادات الرواتب
  eosbBasis: { ar: "أجر مكافأة نهاية الخدمة", en: "EOSB wage basis" },
  eosbHint: {
    ar: "يجب تحديده قبل أول مسير مستحقات — الصمت هنا قرار مالي لم يتخذه أحد",
    en: "Must be set before the first settlement run",
  },
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
  invoices: { ar: "الفواتير", en: "Invoices" },
  invoiceNo: { ar: "رقم الفاتورة", en: "Invoice No." },
  amount: { ar: "المبلغ", en: "Amount" },
  status: { ar: "الحالة", en: "Status" },
  dueDate: { ar: "الاستحقاق", en: "Due" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  none: { ar: "لا شيء", en: "None" },
  empty: { ar: "لا سجلات", en: "No records" },
};

const SECTIONS = ["payroll", "subscription", "team"] as const;
type Section = (typeof SECTIONS)[number];

type PayrollSettings = {
  eosb_wage_basis: string;
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

type Invoice = {
  id: number;
  invoice_no: string;
  total: string;
  status_label: string;
  due_date: string | null;
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
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [denied, setDenied] = useState(false);

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
        <Link href="/settings/users" className="spread" style={{
          padding: "13px 20px", color: "var(--ink-2)",
        }}>
          <span style={{ fontWeight: 500 }}>{L("users")}</span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {L("usersHint")}
          </span>
        </Link>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 6 }}>{L("payroll")}</h3>

        <Row label={L("eosbBasis")} hint={L("eosbHint")}>
          <select className="select" value={data.eosb_wage_basis}
            onChange={(e) => set("eosb_wage_basis", e.target.value)}>
            <option value="not_set">{L("notSet")}</option>
            <option value="basic_only">{L("basicOnly")}</option>
            <option value="basic_housing">{L("basicHousing")}</option>
            <option value="flagged">{L("flagged")}</option>
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
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          <IcCheck size={17} />
          {saving ? L("saving") : L("save")}
        </button>
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
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Subscription>("/account/subscription/").catch(() => null),
      apiGet<Invoice[]>("/account/invoices/").catch(() => []),
    ]).then(([s, inv]) => {
      setSub(s);
      setInvoices(inv);
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
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("noAccess")}
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
          <h3 style={{ fontSize: "1rem" }}>{L("invoices")}</h3>
        </div>
        {invoices.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ textAlign: "end" }}>{L("invoiceNo")}</th>
                <th style={{ textAlign: "end" }}>{L("amount")}</th>
                <th style={{ textAlign: "end" }}>{L("dueDate")}</th>
                <th>{L("status")}</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id}>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{i.invoice_no}</span>
                  </td>
                  <td style={{ textAlign: "end", fontWeight: 600 }}>
                    <span className="num">{money(i.total)}</span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    {i.due_date ? <span className="num">{i.due_date}</span> : "—"}
                  </td>
                  <td><span className="badge">{i.status_label}</span></td>
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
  const [section, setSection] = useState<Section>("payroll");

  const ICONS: Record<Section, React.ComponentType<{ size?: number }>> = {
    payroll: IcPayroll,
    subscription: IcWallet,
    team: IcUsers,
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
      {section === "team" && (
        <div className="card" style={{
          padding: 36, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("soon", "قريبًا")}
        </div>
      )}
    </div>
  );
}

"use client";

/**
 * إعدادات المنصة (ق-50).
 *
 * كل ما قرره المالك صار إعدادًا لا كودًا: نسبة الضريبة، وأيام
 * التجربة، والمهل، والتنبيهات، ومحاولات الدفع.
 */
import { useEffect, useState } from "react";

import { pGet, pPut, AdminError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "إعدادات المنصة", en: "Platform settings" },
  vat: { ar: "الضريبة", en: "VAT" },
  vatRate: { ar: "نسبة ضريبة القيمة المضافة %", en: "VAT rate %" },
  vatHint: {
    ar: "تغيّرت من 5% إلى 15% في 2020 — قد تتغير مجددًا",
    en: "Changed from 5% to 15% in 2020",
  },
  vatNumber: { ar: "الرقم الضريبي للمنصة", en: "Platform VAT number" },
  trial: { ar: "التجربة المجانية", en: "Free trial" },
  trialDays: { ar: "أيام التجربة", en: "Trial days" },
  trialMax: { ar: "حد موظفي التجربة", en: "Trial employee limit" },
  renewal: { ar: "التجديد والتنبيهات", en: "Renewal & alerts" },
  graceDays: { ar: "مهلة السماح بعد الانتهاء", en: "Grace days" },
  graceHint: {
    ar: "يعمل الحساب فيها ثم يصير للقراءة",
    en: "Account works during grace, then read-only",
  },
  alertMonthly: { ar: "التنبيه قبل (شهري)", en: "Alert before (monthly)" },
  alertAnnual: { ar: "التنبيه قبل (سنوي)", en: "Alert before (annual)" },
  invoiceDue: { ar: "مهلة سداد الفاتورة", en: "Invoice due days" },
  payments: { ar: "محاولات الدفع", en: "Payment retries" },
  retryLimit: { ar: "محاولات الدفع اليدوي", en: "Manual retry limit" },
  cooldown: { ar: "مهلة الحظر بعدها (ساعات)", en: "Cooldown hours" },
  autoRetry: { ar: "جدول إعادة المحاولة التلقائية", en: "Auto retry schedule" },
  autoRetryHint: {
    ar: "ساعات بين المحاولات — 12,24 يعني بعد 12 ثم بعد 24",
    en: "Hours between retries",
  },
  notifTitle: { ar: "إشعارات المنصّة", en: "Platform notifications" },
  notifEmail: { ar: "بريد الإشعارات", en: "Notification email" },
  notifHint: {
    ar: "يصله كل تسجيلٍ جديد — واتركه فارغًا لإيقاف الإشعارات",
    en: "Receives every new signup — leave empty to disable",
  },
  promoTitle: { ar: "شريط العرض", en: "Promo banner" },
  promoOn: { ar: "إظهار الشريط", en: "Show banner" },
  promoText: { ar: "نصّ العرض", en: "Promo text" },
  promoCode: { ar: "كود العرض", en: "Promo code" },
  promoHint: {
    ar: "يظهر في شاشتي الأسعار — والكود يُنسخ بنقرة، ويجب أن يكون قائمًا في الخصومات",
    en: "Shown on both pricing screens — the code must exist in Discounts",
  },
  payTitle: { ar: "طرق الدفع", en: "Payment methods" },
  payGateway: { ar: "الدفع بالبطاقة (ميسر)", en: "Card payment (Moyasar)" },
  payBankOn: { ar: "التحويل البنكي", en: "Bank transfer" },
  payBankHint: {
    ar: "تُعرض بياناته للعميل — والتفعيل بيدك بعد التحقّق من التحويل",
    en: "Details shown to the client — you activate after verifying",
  },
  bankName: { ar: "اسم البنك", en: "Bank name" },
  bankIban: { ar: "الآيبان", en: "IBAN" },
  bankBenef: { ar: "اسم المستفيد", en: "Beneficiary" },
  support: { ar: "الدعم", en: "Support" },
  supportEmail: { ar: "بريد الدعم", en: "Support email" },
  supportMobile: { ar: "جوال الدعم", en: "Support mobile" },
  accounting: { ar: "الربط بالمحاسبي", en: "Accounting link" },
  accountingUrl: { ar: "رابط محاسبة معتمد", en: "Accounting API URL" },
  accountingEnabled: { ar: "مزامنة الفواتير", en: "Sync invoices" },
  accHint: {
    ar: "عند تفعيلها تصدر فاتورة زكاتية من معتمد المحاسبي فور نجاح كل دفعة",
    en: "Issues a ZATCA invoice from Muatmd Accounting on each payment",
  },
  accBlocked: {
    ar: "⚠️ مقفلة في هذه البيئة — لا فاتورة تصدر ولو فُعّلت المزامنة",
    en: "Locked in this environment — no invoice is issued",
  },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت التغييرات", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا صلاحية", en: "No access" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

type Settings = Record<string, string | number | boolean>;

function Row({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
      <div className="spread" style={{ gap: 16 }}>
        <div className="grow">
          <div style={{ fontWeight: 500 }}>{label}</div>
          {hint && (
            <div className="muted" style={{ fontSize: ".82rem", marginTop: 2 }}>
              {hint}
            </div>
          )}
        </div>
        <div style={{ minWidth: 170 }}>{children}</div>
      </div>
    </div>
  );
}

export default function PlatformSettingsPage() {
  const { L } = useT(T);
  const [s, setS] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    pGet<Settings>("/platform/settings/")
      .then((d) => { setS(d); setBusy(false); })
      .catch((e: AdminError) => { setDenied(e.isForbidden); setBusy(false); });
  }, []);

  const set = (k: string, v: string | number | boolean) =>
    setS((old) => (old ? { ...old, [k]: v } : old));

  async function save() {
    if (!s) return;
    setSaving(true);
    setMsg("");
    try {
      await pPut("/platform/settings/", s);
      setMsg(L("saved"));
      setTimeout(() => setMsg(""), 3000);
    } catch (e) {
      setMsg((e as AdminError).message);
    } finally {
      setSaving(false);
    }
  }

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  if (denied || !s) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  const num = (k: string) => (
    <input type="number" className="input" value={String(s[k] ?? "")}
      onChange={(e) => set(k, e.target.value)} />
  );
  const text = (k: string) => (
    <input className="input" value={String(s[k] ?? "")} dir="ltr"
      onChange={(e) => set(k, e.target.value)} />
  );
  const bool = (k: string) => (
    <select className="select" value={s[k] ? "1" : "0"}
      onChange={(e) => set(k, e.target.value === "1")}>
      <option value="1">{L("yes")}</option>
      <option value="0">{L("no")}</option>
    </select>
  );

  return (
    <div className="stack">
      <h1>{L("title")}</h1>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("vat")}</h2>
        <Row label={L("vatRate")} hint={L("vatHint")}>{num("vat_rate")}</Row>
        <Row label={L("vatNumber")}>{text("vat_number")}</Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("trial")}</h2>
        <Row label={L("trialDays")}>{num("trial_days")}</Row>
        <Row label={L("trialMax")}>{num("trial_max_employees")}</Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("renewal")}</h2>
        <Row label={L("graceDays")} hint={L("graceHint")}>
          {num("grace_days_after_expiry")}
        </Row>
        <Row label={L("alertMonthly")}>{num("renewal_alert_monthly")}</Row>
        <Row label={L("alertAnnual")}>{num("renewal_alert_annual")}</Row>
        <Row label={L("invoiceDue")}>{num("invoice_due_days")}</Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("payments")}</h2>
        <Row label={L("retryLimit")}>{num("manual_retry_limit")}</Row>
        <Row label={L("cooldown")}>{num("manual_retry_cooldown_hours")}</Row>
        <Row label={L("autoRetry")} hint={L("autoRetryHint")}>
          {text("auto_retry_hours")}
        </Row>
      </div>

      {/* ⚠️⚠️ ق-٢٧٦: **تسجيلٌ جديد بلا إشعارٍ يضيع** — يسجّل العميل
          وينتظر ولا أحد يعلم. */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>
          {L("notifTitle")}
        </h2>
        <Row label={L("notifEmail")} hint={L("notifHint")}>
          {text("notify_email")}
        </Row>
      </div>

      {/* ⚠️ **ولا يُطفأ الدفع بالبطاقة والتحويل معًا** — فلن يشترك أحد.
          والخادم يرفض ذلك، ويرفض تحويلًا بلا آيبان. */}
      {/* ⚠️⚠️ ق-٢٨١: **كودٌ لا يعرفه أحدٌ لا يُستعمل** — فيُعلَن عنه هنا */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("promoTitle")}</h2>
        <Row label={L("promoOn")} hint={L("promoHint")}>
          {bool("promo_enabled")}
        </Row>
        {s.promo_enabled ? (
          <>
            <Row label={L("promoText")}>{text("promo_text")}</Row>
            <Row label={L("promoCode")}>{text("promo_code")}</Row>
          </>
        ) : null}
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("payTitle")}</h2>
        <Row label={L("payGateway")}>{bool("gateway_enabled")}</Row>
        <Row label={L("payBankOn")} hint={L("payBankHint")}>
          {bool("bank_transfer_enabled")}
        </Row>
        {s.bank_transfer_enabled ? (
          <>
            <Row label={L("bankName")}>{text("bank_name")}</Row>
            <Row label={L("bankIban")}>{text("bank_iban")}</Row>
            <Row label={L("bankBenef")}>{text("bank_beneficiary")}</Row>
          </>
        ) : null}
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("support")}</h2>
        <Row label={L("supportEmail")}>{text("support_email")}</Row>
        <Row label={L("supportMobile")}>{text("support_mobile")}</Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("accounting")}</h2>
        <Row label={L("accountingUrl")}>{text("accounting_api_url")}</Row>
        <Row label={L("accountingEnabled")} hint={L("accHint")}>
          {bool("accounting_enabled")}
        </Row>
        {!s.accounting_env_allowed && (
          <div style={{ marginTop: 10, padding: "10px 14px",
                        borderRadius: 8, fontSize: ".85rem",
                        background: "var(--copper-soft)",
                        color: "var(--copper)" }}>
            {L("accBlocked")}
          </div>
        )}
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

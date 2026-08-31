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
  support: { ar: "الدعم", en: "Support" },
  supportEmail: { ar: "بريد الدعم", en: "Support email" },
  supportMobile: { ar: "جوال الدعم", en: "Support mobile" },
  accounting: { ar: "الربط بالمحاسبي", en: "Accounting link" },
  accountingUrl: { ar: "رابط محاسبة معتمد", en: "Accounting API URL" },
  accountingEnabled: { ar: "مزامنة الفواتير", en: "Sync invoices" },
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

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("support")}</h2>
        <Row label={L("supportEmail")}>{text("support_email")}</Row>
        <Row label={L("supportMobile")}>{text("support_mobile")}</Row>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("accounting")}</h2>
        <Row label={L("accountingUrl")}>{text("accounting_api_url")}</Row>
        <Row label={L("accountingEnabled")}>{bool("accounting_enabled")}</Row>
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

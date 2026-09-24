"use client";
/**
 * قواعد احتساب الرواتب (ق-218).
 *
 * ⚠️ **والإضافيُّ وأساسُ اليوم قراراتٌ ماليّة**: **تُغيَّر مرّةً
 * وتبقى** — فموضعها شاشةٌ تُراجَع لا حقلٌ يُمرّ عليه.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import SettingRow from "@/components/SettingRow";
import { IcAlert, IcCheck } from "@/components/Icons";

/** ق-218: أسس الإضافيّ — ⚠️ **كما يعرفها الخادم** لا كما نظنّ */
const OT_BASES: [string, string][] = [
  ["full_plus_half_basic", "otFullPlusHalf"],
  ["basic_x1_5", "otBasicX15"],
  ["full_x1_5", "otFullX15"],
  ["full_plus_basic", "otFullPlusBasic"],
  ["full_x2", "otFullX2"],
];

const T: Dict = {
  title: { ar: "قواعد احتساب الرواتب", en: "Payroll rules" },
  sub: { ar: "الإضافيّ وأساس اليوم وتاريخ الاقتطاع",
         en: "Overtime, day basis and cutoff" },
  otBasis: { ar: "أساس العمل الإضافي", en: "Overtime basis" },
  otBasisHint: { ar: "الأساس المعتمد لكل ساعة إضافية",
                 en: "The rate used per overtime hour" },
  otFullPlusHalf: {
    ar: "أجر ساعة الأجر الكامل + 50% من ساعة الأساسي",
    en: "Full hour + 50% of basic",
  },
  otBasicX15: { ar: "أجر ساعة الأساسي × 1.5", en: "Basic × 1.5" },
  otFullX15: { ar: "أجر ساعة الأجر الكامل × 1.5", en: "Full × 1.5" },
  otFullPlusBasic: {
    ar: "أجر ساعة الأجر الكامل + ساعة الأساسي",
    en: "Full hour + basic hour",
  },
  otFullX2: { ar: "أجر ساعة الأجر الكامل × 2", en: "Full × 2" },
  otChoice: { ar: "السماح باختيار معامل الإضافي",
              en: "Allow rate choice" },
  otChoiceHint: {
    ar: "يُظهر للموظف خيار ×2 في طلبه — والمعتمد يقبل أو يرفض",
    en: "Shows a ×2 option to the employee",
  },
  otX2: { ar: "أساس معامل ×2", en: "×2 basis" },
  otX2Hint: { ar: "ما يُضاعف حين يُختار المعامل",
              en: "What gets doubled" },
  daysPerMonth: { ar: "أيام الشهر المعتمدة", en: "Days per month" },
  daysHint: {
    ar: "⚠️ أجر اليوم = الراتب ÷ هذا العدد — وتغييره يمسّ كل احتساب",
    en: "Daily wage = salary ÷ this",
  },
  startMonth: { ar: "أول شهر مسير", en: "First payroll month" },
  startMonthHint: {
    ar: "لا يُنشأ مسير قبل هذا الشهر — فالشهور السابقة صُرفت من نظامكم السابق. واترك الحقلين فارغين إن كان النظام هو الأول.",
    en: "No payroll run before this month — earlier months were paid by your previous system. Leave empty if this is your first system.",
  },
  cutoff: { ar: "يوم اقتطاع المسير", en: "Payroll cutoff day" },
  cutoffHint: {
    ar: "ما بعده يدخل الشهر التالي — و31 يعني نهاية الشهر",
    en: "After it, entries go to next month",
  },
  variance: { ar: "حدّ تنبيه الفروقات (%)", en: "Variance alert (%)" },
  varianceHint: {
    ar: "⚠️ فرقٌ يتجاوزه بين مسيرين يُنبَّه عليه — فالخطأ يُكتشف قبل الصرف",
    en: "Runs differing more than this raise a flag",
  },
  enabled: { ar: "مفعّل", en: "Enabled" },
  disabled: { ar: "معطّل", en: "Disabled" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظ", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  denied: { ar: "لا تملك صلاحية هذه الإعدادات", en: "Not allowed" },
  back: { ar: "← الإعدادات", en: "← Settings" },
};

type S = {
  overtime_basis: string;
  allow_overtime_rate_choice: boolean;
  overtime_basis_x2: string;
  payroll_days_per_month: number;
  payroll_start_year: number;
  payroll_start_month: number;
  payroll_cutoff_day: number;
  variance_threshold_percent: number;
};

export default function PayrollRulesPage() {
  const { L } = useT(T);
  const [data, setData] = useState<S | null>(null);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [denied, setDenied] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiGet<S>("/payroll/settings/")
      .then((d) => { setData(d); setBusy(false); })
      .catch((e: ApiError) => { setDenied(e.isForbidden); setBusy(false); });
  }, []);

  const set = (k: keyof S, v: unknown) =>
    setData((s) => (s ? { ...s, [k]: v } : s));

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setMsg("");
    setErr("");
    try {
      await apiPut("/payroll/settings/", data);
      setMsg(L("saved"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );
  if (denied) return (
    <div className="card" style={{ padding: 30, textAlign: "center" }}>
      {L("denied")}
    </div>
  );

  return (
    <div className="stack">
      <a className="btn btn-sm btn-ghost" href="/settings"
         style={{ alignSelf: "flex-start" }}>{L("back")}</a>

      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".92rem",
                                        marginTop: 3 }}>{L("sub")}</div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
        </div>
      )}

      {data && (
        <div className="card" style={{ padding: 22 }}>
          <SettingRow label={L("otBasis")} hint={L("otBasisHint")}>
            <select className="select" value={data.overtime_basis}
                    onChange={(e) => set("overtime_basis",
                                         e.target.value)}>
              {/* ⚠️ **والخيارات خمسة** — كما يعرفها الخادم */}
              {OT_BASES.map(([v, k]) => (
                <option key={v} value={v}>{L(k)}</option>
              ))}
            </select>
          </SettingRow>

          <SettingRow label={L("otChoice")} hint={L("otChoiceHint")}>
            <select className="select"
                    value={data.allow_overtime_rate_choice ? "1" : "0"}
                    onChange={(e) => set("allow_overtime_rate_choice",
                                         e.target.value === "1")}>
              <option value="1">{L("enabled")}</option>
              <option value="0">{L("disabled")}</option>
            </select>
          </SettingRow>

          {/* ⚠️ **ولا معنى للمعامل بلا السماح به** */}
          {data.allow_overtime_rate_choice && (
            <SettingRow label={L("otX2")} hint={L("otX2Hint")}>
              <select className="select" value={data.overtime_basis_x2}
                      onChange={(e) => set("overtime_basis_x2",
                                           e.target.value)}>
                {OT_BASES.map(([v, k]) => (
                  <option key={v} value={v}>{L(k)}</option>
                ))}
              </select>
            </SettingRow>
          )}

          <SettingRow label={L("daysPerMonth")} hint={L("daysHint")}>
            <input className="input num" type="number" min={1} max={31}
                   style={{ maxWidth: 130 }}
                   value={String(data.payroll_days_per_month ?? 30)}
                   onChange={(e) => set("payroll_days_per_month",
                                        Number(e.target.value))} />
          </SettingRow>

          {/* ⚠️⚠️ ق-٢٥٢: **أول شهرٍ يُصرف من النظام.** العميل المنتقل من
              نظامٍ آخر صرف شهوره السابقة هناك — وبلا هذا الحدّ **يُصرف الشهر
              مرتين**. وما قبله تاريخٌ للعلم: الحضور محسوبٌ ومعروض، والمسير
              وحده ممنوع. ويُضبط عند التأسيس بشهره، ويُعدَّل هنا. */}
          <SettingRow label={L("startMonth")} hint={L("startMonthHint")}>
            <div style={{ display: "flex", gap: 8 }}>
              <select className="input" style={{ maxWidth: 130 }}
                      value={String(data.payroll_start_month ?? 0)}
                      onChange={(e) => set("payroll_start_month",
                                           Number(e.target.value))}>
                <option value="0">—</option>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
                ))}
              </select>
              <input className="input num" type="number" min={0} max={2100}
                     style={{ maxWidth: 110 }} placeholder="—"
                     value={String(data.payroll_start_year ?? 0)}
                     onChange={(e) => set("payroll_start_year",
                                          Number(e.target.value))} />
            </div>
          </SettingRow>

          <SettingRow label={L("cutoff")} hint={L("cutoffHint")}>
            <input className="input num" type="number" min={1} max={31}
                   style={{ maxWidth: 130 }}
                   value={String(data.payroll_cutoff_day ?? 31)}
                   onChange={(e) => set("payroll_cutoff_day",
                                        Number(e.target.value))} />
          </SettingRow>

          <SettingRow label={L("variance")} hint={L("varianceHint")}>
            <input className="input num" type="number" min={0}
                   style={{ maxWidth: 130 }}
                   value={String(data.variance_threshold_percent ?? 10)}
                   onChange={(e) => set("variance_threshold_percent",
                                        Number(e.target.value))} />
          </SettingRow>

          <button className="btn btn-primary" style={{ marginTop: 18 }}
                  disabled={saving} onClick={save}>
            {saving ? L("saving") : L("save")}
          </button>
        </div>
      )}
    </div>
  );
}

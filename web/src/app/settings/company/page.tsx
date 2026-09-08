"use client";
/**
 * بيانات المنشأة — السجل التجاري والأرقام النظامية وبريد التواصل.
 *
 * بريد التواصل يصله ردّ الموظفين على رسائل النظام (ق-99): فالنظام
 * يرسل من noreply-hr@muatmd.sa، ولكل شركة بريدها الذي يعود إليه
 * الردّ — لا يصل ردّ موظف شركةٍ شركةً أخرى.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "بيانات المنشأة", en: "Company details" },
  subtitle: {
    ar: "السجل التجاري والأرقام النظامية وبريد التواصل",
    en: "Registration, statutory numbers and contact email",
  },
  secIdentity: { ar: "الهوية النظامية", en: "Legal identity" },
  secNumbers: { ar: "الأرقام النظامية", en: "Statutory numbers" },
  secContact: { ar: "التواصل والسنة المالية", en: "Contact and fiscal year" },
  legalAr: { ar: "الاسم النظامي", en: "Legal name" },
  legalEn: { ar: "الاسم بالإنجليزية", en: "Legal name (English)" },
  code: { ar: "رمز الشركة", en: "Company code" },
  cr: { ar: "السجل التجاري", en: "CR number" },
  crExp: { ar: "انتهاء السجل", en: "CR expiry" },
  unified: { ar: "الرقم الموحّد", en: "Unified number" },
  vat: { ar: "الرقم الضريبي", en: "VAT number" },
  gosi: { ar: "رقم منشأة التأمينات", en: "GOSI establishment no." },
  mol: { ar: "رقم منشأة قوى", en: "MOL establishment no." },
  activity: { ar: "رمز النشاط", en: "Activity code" },
  size: { ar: "حجم المنشأة", en: "Entity size" },
  fiscal: { ar: "بداية السنة المالية", en: "Fiscal year starts" },
  email: { ar: "بريد التواصل", en: "Contact email" },
  emailHint: {
    ar: "يصله ردّ الموظفين على رسائل النظام — واتركه فارغًا فلا يُتاح الردّ",
    en: "Receives employee replies to system emails — leave blank to disable replies",
  },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت البيانات", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  readOnly: { ar: "للعرض فقط — لا تملك صلاحية التعديل", en: "View only" },
  months: { ar: "شهر", en: "Month" },
};

type Company = {
  id: number;
  code: string;
  legal_name_ar: string;
  legal_name_en: string;
  cr_number: string;
  cr_expiry_date: string | null;
  unified_national_number: string;
  vat_number: string;
  gosi_establishment_no: string;
  mol_establishment_no: string;
  activity_code: string;
  entity_size: string;
  fiscal_year_start_month: number;
  contact_email: string;
};

const MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const MONTHS_EN = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

export default function CompanySettingsPage() {
  const { L, lang } = useT(T);
  const [data, setData] = useState<Company | null>(null);
  const [perms, setPerms] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const canEdit = perms.includes("company.edit");
  const canView = perms.includes("company.view") || canEdit;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      const c = await apiGet<Company>("/company/settings/");
      setData(c);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = (k: keyof Company, v: string | number) =>
    setData((d) => (d ? { ...d, [k]: v } as Company : d));

  const save = async () => {
    if (!data) return;
    setSaving(true); setErr(""); setMsg("");
    try {
      const out = await apiPut<Company>("/company/settings/", {
        legal_name_ar: data.legal_name_ar,
        legal_name_en: data.legal_name_en,
        cr_number: data.cr_number,
        cr_expiry_date: data.cr_expiry_date || "",
        unified_national_number: data.unified_national_number,
        vat_number: data.vat_number,
        gosi_establishment_no: data.gosi_establishment_no,
        mol_establishment_no: data.mol_establishment_no,
        activity_code: data.activity_code,
        entity_size: data.entity_size,
        fiscal_year_start_month: data.fiscal_year_start_month,
        contact_email: data.contact_email,
      });
      setData(out);
      setMsg(L("saved"));
      setTimeout(() => setMsg(""), 3000);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="card">{L("loading")}</div>;
  if (!canView) return <div className="card">{L("noAccess")}</div>;
  if (!data) return <div className="card">{err || L("noAccess")}</div>;

  // دالّة لا مكوّنًا: تعريف مكوّن داخل مكوّن يُنشئ نوعًا جديدًا كل
  // تصيير، فيُفكَّك الحقل ويُعاد بناؤه ويفقد التركيز بعد كل حرف.
  const F = (label: string, k: keyof Company,
             type = "text", hint?: string, w = 240) => (
    <div className="field" key={k} style={{ minWidth: w, flex: "1 1 " + w + "px" }}>
      <label className="label">{label}</label>
      <input className="input" type={type}
             value={(data[k] as string) ?? ""}
             disabled={!canEdit}
             onChange={(e) => set(k, e.target.value)} />
      {hint && <span className="muted"
                     style={{ fontSize: ".82rem" }}>{hint}</span>}
    </div>
  );

  const months = lang === "en" ? MONTHS_EN : MONTHS_AR;

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <p className="muted" style={{ margin: "4px 0 0" }}>{L("subtitle")}</p>
      </div>

      {!canEdit && (
        <div className="card">
          <IcAlert /> {L("readOnly")}
        </div>
      )}
      {err && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <IcAlert /> {err}
        </div>
      )}
      {msg && (
        <div className="card" style={{ borderColor: "var(--ok)" }}>
          <IcCheck /> {msg}
        </div>
      )}

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px" }}>{L("secIdentity")}</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: 14, alignItems: "flex-start" }}>
        {F(L("legalAr"), "legal_name_ar")}
        {F(L("legalEn"), "legal_name_en")}
        <div className="field" style={{ minWidth: 240, flex: "1 1 240px" }}>
          <label className="label">{L("code")}</label>
          <input className="input" value={data.code} disabled />
        </div>
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px" }}>{L("secNumbers")}</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: 14, alignItems: "flex-start" }}>
        {F(L("cr"), "cr_number")}
        {F(L("crExp"), "cr_expiry_date", "date")}
        {F(L("unified"), "unified_national_number")}
        {F(L("vat"), "vat_number")}
        {F(L("gosi"), "gosi_establishment_no")}
        {F(L("mol"), "mol_establishment_no")}
        {F(L("activity"), "activity_code")}
        {F(L("size"), "entity_size")}
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: "0 0 14px" }}>{L("secContact")}</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: 14, alignItems: "flex-start" }}>
        {F(L("email"), "contact_email", "email", L("emailHint"), 320)}
        <div className="field" style={{ minWidth: 240, flex: "1 1 240px" }}>
          <label className="label">{L("fiscal")}</label>
          <select className="select"
                  value={data.fiscal_year_start_month}
                  disabled={!canEdit}
                  onChange={(e) => set("fiscal_year_start_month",
                                        Number(e.target.value))}>
            {months.map((m, i) => (
              <option key={i} value={i + 1}>{m}</option>
            ))}
          </select>
        </div>
        </div>
      </div>

      {canEdit && (
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? L("saving") : L("save")}
        </button>
      )}
    </div>
  );
}

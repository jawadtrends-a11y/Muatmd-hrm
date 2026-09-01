"use client";

/**
 * ملف الموظف الكامل — أحد عشر تبويبًا (ق-63).
 *
 * كل تبويب قسم مستقل يُعدَّل وحده — فتغيير حقل لا يرسل الملف
 * كاملًا، ولا يفتح باب الخطأ في بيانات لم تُمسّ.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiGet, apiPost, apiPut, apiDelete, API_BASE, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import {
  IcAlert, IcCheck, IcClock, IcDoc, IcLeave, IcOrg, IcPayroll,
  IcPlus, IcUser, IcUsers, IcWallet, IcX,
} from "@/components/Icons";

const T: Dict = {
  back: { ar: "رجوع", en: "Back" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  notFound: { ar: "الموظف غير موجود", en: "Not found" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظ", en: "Saved" },
  edit: { ar: "تعديل", en: "Edit" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  add: { ar: "إضافة", en: "Add" },
  remove: { ar: "إزالة", en: "Remove" },
  empty: { ar: "لا سجلات", en: "No records" },

  // التبويبات
  personal: { ar: "البيانات الأساسية", en: "Personal" },
  job: { ar: "بيانات الوظيفة", en: "Job" },
  contract: { ar: "العقد", en: "Contract" },
  salary: { ar: "الراتب", en: "Salary" },
  gosi: { ar: "التأمينات", en: "GOSI" },
  bank: { ar: "البنك", en: "Bank" },
  dependents: { ar: "التابعون", en: "Dependents" },
  contact: { ar: "الاتصال", en: "Contact" },
  documents: { ar: "الوثائق", en: "Documents" },
  files: { ar: "الملفات", en: "Files" },
  audit: { ar: "السجل الوظيفي", en: "Activity" },

  // الحقول الشخصية
  firstName: { ar: "الاسم الأول", en: "First name" },
  fatherName: { ar: "اسم الأب", en: "Father" },
  grandName: { ar: "اسم الجد", en: "Grandfather" },
  familyName: { ar: "اسم العائلة", en: "Family" },
  fullNameEn: { ar: "الاسم بالإنجليزية", en: "Full name (EN)" },
  gender: { ar: "الجنس", en: "Gender" },
  male: { ar: "ذكر", en: "Male" },
  female: { ar: "أنثى", en: "Female" },
  birthDate: { ar: "تاريخ الميلاد", en: "Birth date" },
  maritalStatus: { ar: "الحالة الاجتماعية", en: "Marital status" },
  single: { ar: "أعزب", en: "Single" },
  married: { ar: "متزوج", en: "Married" },
  divorced: { ar: "مطلق", en: "Divorced" },
  widowed: { ar: "أرمل", en: "Widowed" },
  nationality: { ar: "الجنسية", en: "Nationality" },
  idType: { ar: "نوع الهوية", en: "ID type" },
  idNumber: { ar: "رقم الهوية", en: "ID number" },
  idExpiry: { ar: "انتهاء الهوية", en: "ID expiry" },
  passportNumber: { ar: "رقم الجواز", en: "Passport" },
  passportExpiry: { ar: "انتهاء الجواز", en: "Passport expiry" },
  borderNumber: { ar: "رقم الحدود", en: "Border number" },

  // الوظيفة
  jobTitle: { ar: "المسمى الوظيفي", en: "Job title" },
  department: { ar: "القسم", en: "Department" },
  branch: { ar: "الفرع", en: "Branch" },
  site: { ar: "موقع العمل", en: "Work site" },
  manager: { ar: "المدير المباشر", en: "Manager" },
  grade: { ar: "المرتبة الوظيفية", en: "Grade" },
  step: { ar: "الدرجة الوظيفية", en: "Step" },
  optional: { ar: "اختياري", en: "Optional" },

  // العقد
  contractType: { ar: "نوع العقد", en: "Contract type" },
  contractStart: { ar: "بداية العقد", en: "Start" },
  contractEnd: { ar: "نهاية العقد", en: "End" },
  joinDate: { ar: "تاريخ المباشرة", en: "Join date" },
  serviceStart: { ar: "بداية الخدمة المحتسبة", en: "Service start" },
  probationDays: { ar: "أيام التجربة", en: "Probation days" },
  probationEnd: { ar: "انتهاء التجربة", en: "Probation ends" },
  inProbation: { ar: "تحت التجربة", en: "In probation" },
  serviceLength: { ar: "مدة الخدمة", en: "Service" },
  years: { ar: "سنة", en: "y" },
  months: { ar: "شهرًا", en: "m" },

  // الراتب
  component: { ar: "المكوّن", en: "Component" },
  amount: { ar: "المبلغ", en: "Amount" },
  gross: { ar: "الإجمالي", en: "Gross" },
  inGosi: { ar: "بأجر التأمينات", en: "In GOSI" },
  inEosb: { ar: "بأجر المكافأة", en: "In EOSB" },
  history: { ar: "السجل التاريخي", en: "History" },
  effectiveFrom: { ar: "ساري من", en: "From" },

  // التأمينات
  gosiRegistered: { ar: "مسجّل بالتأمينات", en: "GOSI registered" },
  molRegistered: { ar: "مسجّل بقوى", en: "MOL registered" },
  wps: { ar: "حماية الأجور", en: "WPS" },
  declaredWage: { ar: "الأجر المسجَّل", en: "Declared wage" },
  establishmentNo: { ar: "رقم المنشأة", en: "Establishment No." },
  borneByCompany: { ar: "الشركة تتحمّل حصة الموظف", en: "Company bears" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },

  // البنك
  iban: { ar: "الآيبان", en: "IBAN" },
  bankName: { ar: "البنك", en: "Bank" },
  paymentMethod: { ar: "طريقة الصرف", en: "Payment method" },

  // التابعون
  relation: { ar: "صلة القرابة", en: "Relation" },
  dependentName: { ar: "الاسم", en: "Name" },
  addDependent: { ar: "إضافة تابع", en: "Add dependent" },
  spouse: { ar: "زوج/زوجة", en: "Spouse" },
  son: { ar: "ابن", en: "Son" },
  daughter: { ar: "ابنة", en: "Daughter" },
  father: { ar: "أب", en: "Father" },
  mother: { ar: "أم", en: "Mother" },
  other: { ar: "أخرى", en: "Other" },

  // الاتصال
  mobile: { ar: "الجوال", en: "Mobile" },
  email: { ar: "البريد", en: "Email" },
  emergency: { ar: "أرقام الطوارئ", en: "Emergency contacts" },
  addContact: { ar: "إضافة رقم طوارئ", en: "Add contact" },
  primary: { ar: "الأساسي", en: "Primary" },

  // الوثائق
  docType: { ar: "نوع الوثيقة", en: "Type" },
  docNumber: { ar: "الرقم", en: "Number" },
  issueDate: { ar: "الإصدار", en: "Issued" },
  expiryDate: { ar: "الانتهاء", en: "Expires" },
  daysLeft: { ar: "المتبقي", en: "Days left" },
  expired: { ar: "منتهية", en: "Expired" },
  days: { ar: "يوم", en: "days" },

  // الملفات
  fileName: { ar: "الملف", en: "File" },
  fileKind: { ar: "النوع", en: "Kind" },
  fileSize: { ar: "الحجم", en: "Size" },
  view: { ar: "عرض", en: "View" },
  ownHint: {
    ar: "تعديلاتك تُقدَّم كطلب يعتمده موظف الموارد البشرية",
    en: "Your edits are submitted as a request for HR approval",
  },
  requestSubmitted: {
    ar: "قُدّم طلب التعديل",
    en: "Edit request submitted",
  },
  pendingApproval: {
    ar: "بانتظار اعتماد الموارد البشرية",
    en: "Awaiting HR approval",
  },
  trackIt: { ar: "تابعه من «طلباتي»", en: "Track in My Requests" },
  notEditable: {
    ar: "لا يُعدَّل بطلب — راجع الموارد البشرية",
    en: "Not editable by request",
  },
};

const TABS = [
  "personal", "job", "contract", "salary", "gosi", "bank",
  "dependents", "contact", "documents", "files", "audit",
] as const;
type Tab = (typeof TABS)[number];

type Profile = Record<string, never> & {
  employment_id: number;
  employee_no: string;
  is_own?: boolean;
  can_edit?: boolean;
  status_label: string;
  avatar_url: string | null;
  personal: Record<string, string>;
  job: Record<string, string | number | null>;
  contract: Record<string, string | number | boolean | null>;
  salary: {
    gross: string;
    lines: { component: string; amount: string;
             in_gosi: boolean; in_eosb: boolean }[];
    history: { effective_from: string; effective_to: string | null;
               gross: string }[];
  };
  gosi: Record<string, string | boolean>;
  bank: Record<string, string>;
  dependents: {
    id: number; full_name_ar: string; relation: string;
    relation_label: string; id_number: string;
    id_expiry_date: string | null; birth_date: string | null;
  }[];
  emergency_contacts: {
    id: number; full_name_ar: string; relation: string;
    mobile: string; phone: string; is_primary: boolean;
  }[];
  documents: {
    id: number; type_label: string; document_number: string;
    issue_date: string | null; expiry_date: string | null;
    days_left: number | null;
  }[];
  files: {
    id: number; kind_label: string; name: string;
    size: string; url: string;
  }[];
};

function money(v: string | number) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : String(v);
}


/* ══ صف عرض — خارج المكوّن الرئيسي ══ */

function Row({
  label, value, numeric,
}: {
  label: string;
  value: React.ReactNode;
  numeric?: boolean;
}) {
  return (
    <div className="spread" style={{
      padding: "9px 0", borderBottom: "1px solid var(--line)",
    }}>
      <span className="muted" style={{ fontSize: ".86rem" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>
        {numeric && value ? <span className="num">{value}</span> : (value || "—")}
      </span>
    </div>
  );
}

/* ══ حقل تعديل ══ */

type FieldDef = {
  key: string;
  label: string;
  kind?: "text" | "number" | "date" | "select" | "bool";
  options?: { value: string; label: string }[];
  hint?: string;
  readOnly?: boolean;
};

function EditableSection({
  title, icon: Icon, fields, values, L, onSave, busy, readOnly,
}: {
  readOnly?: boolean;
  title: string;
  icon: React.ComponentType<{ size?: number }>;
  fields: FieldDef[];
  values: Record<string, unknown>;
  L: (k: string, f?: string) => string;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  function start() {
    const init: Record<string, string> = {};
    for (const f of fields) {
      const v = values[f.key];
      init[f.key] = v == null ? "" : String(v);
    }
    setDraft(init);
    setEditing(true);
  }

  async function commit() {
    const changed: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.readOnly) continue;
      const before = values[f.key] == null ? "" : String(values[f.key]);
      const after = draft[f.key] ?? "";
      if (before === after) continue;
      changed[f.key] = f.kind === "bool" ? after === "1" : after;
    }
    if (Object.keys(changed).length === 0) { setEditing(false); return; }

    await onSave(changed);
    setEditing(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="spread" style={{ marginBottom: 12 }}>
        <div className="row">
          <Icon size={19} />
          <h3 style={{ fontSize: "1rem" }}>{title}</h3>
          {saved && (
            <span className="badge badge-ok">
              <IcCheck size={13} /> {L("saved")}
            </span>
          )}
        </div>
        {readOnly ? null : !editing ? (
          <button className="btn btn-sm btn-ghost" onClick={start}>
            {L("edit")}
          </button>
        ) : (
          <div className="row" style={{ gap: 6 }}>
            <button className="btn btn-sm btn-primary" disabled={busy}
              onClick={commit}>
              {busy ? L("saving") : L("save")}
            </button>
            <button className="btn btn-sm btn-ghost"
              onClick={() => setEditing(false)}>
              {L("cancel")}
            </button>
          </div>
        )}
      </div>

      {!editing ? (
        /**
         * شبكة حقول لا صفوف جدول.
         *
         * القيمة داخل إطار الحقل تحت عنوانها مباشرةً — فالعين
         * تربطهما بلا قطع الشاشة، والشكل يطابق وضع التعديل
         * فلا يتغيّر التخطيط عند الضغط على «تعديل».
         */
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
          gap: 14,
        }}>
          {fields.map((f) => {
            const v = values[f.key];
            let display: React.ReactNode = v == null || v === "" ? "—" : String(v);

            if (f.kind === "bool") {
              display = (
                <span className={v ? "badge badge-ok" : "badge"}>
                  {v ? L("yes") : L("no")}
                </span>
              );
            } else if (f.kind === "select" && f.options) {
              display = f.options.find((o) => o.value === String(v))?.label
                || display;
            } else if (f.kind === "number" || f.kind === "date") {
              display = <span className="num">{display}</span>;
            }

            return (
              <div key={f.key}>
                <div className="muted" style={{
                  fontSize: ".8rem", marginBottom: 5,
                }}>
                  {f.label}
                </div>
                <div style={{
                  padding: "9px 12px", background: "var(--paper-2)",
                  borderRadius: "var(--radius-sm)", fontWeight: 500,
                  minHeight: 38, display: "flex", alignItems: "center",
                }}>
                  {display}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
          gap: 14,
        }}>
          {fields.map((f) => (
            <div key={f.key} className="field">
              <label className="label">{f.label}</label>

              {f.readOnly ? (
                <div style={{
                  padding: "9px 12px", background: "var(--paper-2)",
                  borderRadius: "var(--radius-sm)", color: "var(--ink-3)",
                }}>
                  {String(values[f.key] ?? "—")}
                </div>
              ) : f.kind === "date" ? (
                <DateField value={draft[f.key] ?? ""}
                  onChange={(v) => setDraft({ ...draft, [f.key]: v })} />
              ) : f.kind === "bool" ? (
                <select className="select" value={draft[f.key] || "0"}
                  onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}>
                  <option value="1">{L("yes")}</option>
                  <option value="0">{L("no")}</option>
                </select>
              ) : f.kind === "select" ? (
                <select className="select" value={draft[f.key] ?? ""}
                  onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}>
                  <option value="">—</option>
                  {(f.options ?? []).map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  type={f.kind === "number" ? "number" : "text"}
                  dir={f.kind === "number" ? "ltr" : undefined}
                  value={draft[f.key] ?? ""}
                  onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                />
              )}

              {f.hint && <div className="hint">{f.hint}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ══ التابعون ══ */

function DependentsTab({
  empId, rows, L, onChanged,
}: {
  empId: number;
  rows: Profile["dependents"];
  L: (k: string, f?: string) => string;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [relation, setRelation] = useState("spouse");
  const [idNumber, setIdNumber] = useState("");
  const [birth, setBirth] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const RELATIONS = [
    ["spouse", L("spouse")], ["son", L("son")], ["daughter", L("daughter")],
    ["father", L("father")], ["mother", L("mother")], ["other", L("other")],
  ];

  async function add() {
    setBusy(true);
    setError("");
    try {
      await apiPost(`/employees/${empId}/dependents/`, {
        full_name_ar: name.trim(), relation,
        id_number: idNumber.trim(), birth_date: birth || null,
      });
      setName(""); setIdNumber(""); setBirth("");
      setAdding(false);
      onChanged();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await apiDelete(`/employees/${empId}/dependents/?id=${id}`).catch(() => {});
    onChanged();
  }

  return (
    <div className="stack">
      <div className="spread">
        <div className="row">
          <IcUsers size={19} />
          <h3 style={{ fontSize: "1rem" }}>{L("dependents")}</h3>
        </div>
        {!adding && (
          <button className="btn btn-sm btn-primary" onClick={() => setAdding(true)}>
            <IcPlus size={15} />
            {L("addDependent")}
          </button>
        )}
      </div>

      {adding && (
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("dependentName")}</label>
              <input className="input" value={name} autoFocus
                onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field" style={{ maxWidth: 170 }}>
              <label className="label">{L("relation")}</label>
              <select className="select" value={relation}
                onChange={(e) => setRelation(e.target.value)}>
                {RELATIONS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ maxWidth: 180 }}>
              <label className="label">{L("idNumber")}</label>
              <input className="input" dir="ltr" inputMode="numeric"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value.replace(/\D/g, ""))} />
            </div>
            <div className="field" style={{ maxWidth: 180 }}>
              <label className="label">{L("birthDate")}</label>
              <DateField value={birth} onChange={setBirth} />
            </div>

            <button className="btn btn-primary" disabled={busy || !name.trim()}
              onClick={add}>
              {busy ? L("saving") : L("add")}
            </button>
            <button className="btn btn-ghost" onClick={() => setAdding(false)}>
              {L("cancel")}
            </button>
          </div>
          {error && (
            <div style={{
              marginTop: 10, color: "var(--danger)", fontSize: ".88rem",
            }}>
              {error}
            </div>
          )}
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <colgroup>
              <col style={{ width: "240px" }} />
              <col style={{ width: "140px" }} />
              <col style={{ width: "160px" }} />
              <col style={{ width: "140px" }} />
              <col style={{ width: "100px" }} />
            </colgroup>
            <thead>
              <tr>
                <th>{L("dependentName")}</th>
                <th>{L("relation")}</th>
                <th style={{ textAlign: "end" }}>{L("idNumber")}</th>
                <th style={{ textAlign: "end" }}>{L("birthDate")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td>{d.full_name_ar}</td>
                  <td><span className="badge">{d.relation_label}</span></td>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{d.id_number || "—"}</span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{d.birth_date || "—"}</span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    <button className="btn btn-sm btn-ghost"
                      style={{ color: "var(--danger)" }}
                      onClick={() => remove(d.id)}>
                      {L("remove")}
                    </button>
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

/* ══ الاتصال وأرقام الطوارئ ══ */

function ContactTab({
  empId, personal, contacts, L, onChanged,
}: {
  empId: number;
  personal: Record<string, string>;
  contacts: Profile["emergency_contacts"];
  L: (k: string, f?: string) => string;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [relation, setRelation] = useState("");
  const [mobile, setMobile] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    setBusy(true);
    try {
      await apiPost(`/employees/${empId}/contacts/`, {
        full_name_ar: name.trim(), relation: relation.trim(),
        mobile: mobile.trim(),
      });
      setName(""); setRelation(""); setMobile("");
      setAdding(false);
      onChanged();
    } catch { /* تجاهل */ }
    finally { setBusy(false); }
  }

  async function remove(id: number) {
    await apiDelete(`/employees/${empId}/contacts/?id=${id}`).catch(() => {});
    onChanged();
  }

  return (
    <div className="stack">
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>{L("contact")}</h3>
        <Row label={L("mobile")}
          value={<span className="num">{personal.mobile || "—"}</span>} />
        <Row label={L("email")} value={personal.email} />
      </div>

      <div className="spread">
        <h3 style={{ fontSize: "1rem" }}>{L("emergency")}</h3>
        {!adding && (
          <button className="btn btn-sm btn-primary" onClick={() => setAdding(true)}>
            <IcPlus size={15} />
            {L("addContact")}
          </button>
        )}
      </div>

      {adding && (
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("dependentName")}</label>
              <input className="input" value={name} autoFocus
                onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field" style={{ maxWidth: 170 }}>
              <label className="label">{L("relation")}</label>
              <input className="input" value={relation}
                onChange={(e) => setRelation(e.target.value)} />
            </div>
            <div className="field" style={{ maxWidth: 180 }}>
              <label className="label">{L("mobile")}</label>
              <input className="input" dir="ltr" inputMode="tel" value={mobile}
                onChange={(e) => setMobile(e.target.value)} />
            </div>
            <button className="btn btn-primary"
              disabled={busy || !name.trim() || !mobile.trim()} onClick={add}>
              {busy ? L("saving") : L("add")}
            </button>
            <button className="btn btn-ghost" onClick={() => setAdding(false)}>
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {contacts.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id}>
                  <td>{c.full_name_ar}</td>
                  <td className="muted">{c.relation}</td>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{c.mobile}</span>
                  </td>
                  <td style={{ width: 100, textAlign: "end" }}>
                    {c.is_primary && (
                      <span className="badge badge-teal">{L("primary")}</span>
                    )}
                  </td>
                  <td style={{ width: 90, textAlign: "end" }}>
                    <button className="btn btn-sm btn-ghost"
                      style={{ color: "var(--danger)" }}
                      onClick={() => remove(c.id)}>
                      {L("remove")}
                    </button>
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

export default function EmployeeProfileView({
  employmentId, showBack,
}: {
  employmentId: number;
  showBack?: boolean;
}) {
  const router = useRouter();
  const { L } = useT(T);
  const empId = employmentId;

  const [data, setData] = useState<Profile | null>(null);
  const [tab, setTab] = useState<Tab>("personal");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [requested, setRequested] = useState("");

  const load = useCallback(() => {
    apiGet<Profile>(`/employees/${empId}/profile/`)
      .then((d) => { setData(d); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });
  }, [empId]);

  useEffect(load, [load]);

  /**
   * الحفظ يفرّق بالدور (ق-65):
   *
   *   صاحب الملف   → يُنشأ طلب تعديل يعتمده موظف الموارد
   *   مدير الموارد → يُعدَّل مباشرةً
   *
   * والواجهة واحدة — فالموظف لا يتعلّم شاشتين لنفس الغرض.
   */
  async function save(section: string, changed: Record<string, unknown>) {
    setSaving(true);
    setError("");
    setRequested("");

    try {
      if (data?.is_own) {
        const res = await apiPost<{ request_no: string }>("/requests/", {
          request_type: "profile_update",
          payload: { changes: changed },
          note: `تعديل ${section}`,
        });
        setRequested(res.request_no);
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        await apiPut(`/employees/${empId}/update/`, { section, data: changed });
        load();
      }
    } catch (e) {
      setError((e as ApiError).message);
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

  if (!data) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--danger)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{error || L("notFound")}</div>
      </div>
    );
  }

  const ICONS: Record<Tab, React.ComponentType<{ size?: number }>> = {
    personal: IcUser, job: IcOrg, contract: IcDoc, salary: IcPayroll,
    gosi: IcCheck, bank: IcWallet, dependents: IcUsers, contact: IcUser,
    documents: IcDoc, files: IcDoc, audit: IcClock,
  };

  return (
    <div className="stack">
      {/* الترويسة */}
      <div>
        {showBack && (
          <button className="btn btn-sm btn-ghost"
            onClick={() => router.push("/employees")}>
            ← {L("back")}
          </button>
        )}

        <div className="row" style={{ marginTop: 12, gap: 16 }}>
          <div style={{
            width: 68, height: 68, borderRadius: "50%",
            background: "var(--paper-2)", overflow: "hidden",
            display: "grid", placeItems: "center", flexShrink: 0,
            border: "2px solid var(--line)",
          }}>
            {data.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`${API_BASE}${data.avatar_url}`} alt=""
                style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              <span style={{ color: "var(--ink-3)" }}><IcUser size={30} /></span>
            )}
          </div>

          <div>
            <h1>{data.personal.full_name_ar}</h1>
            <div className="muted" style={{ fontSize: ".9rem" }}>
              <span className="num">{data.employee_no}</span>
              {data.job.job_title ? ` · ${data.job.job_title}` : ""}
              {data.job.department ? ` · ${data.job.department}` : ""}
            </div>
          </div>

          <div className="grow" />
          <span className="badge">{data.status_label}</span>
        </div>
      </div>

      {data.is_own && (
        <div style={{
          fontSize: ".87rem", padding: "9px 13px",
          background: "var(--teal-soft)", color: "var(--teal)",
          borderRadius: "var(--radius-sm)", fontWeight: 500,
        }}>
          {L("ownHint")}
        </div>
      )}

      {requested && (
        <div style={{
          background: "var(--ok-soft)", color: "var(--ok)",
          padding: "12px 15px", borderRadius: "var(--radius-sm)",
        }}>
          <div className="row" style={{ fontWeight: 600 }}>
            <IcCheck size={17} />
            {L("requestSubmitted")} — <span className="num">{requested}</span>
          </div>
          <div style={{ fontSize: ".87rem", marginTop: 4 }}>
            {L("pendingApproval")} · {L("trackIt")}
          </div>
        </div>
      )}

      {/* التبويبات */}
      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {TABS.map((t) => {
          const Icon = ICONS[t];
          const count =
            t === "dependents" ? data.dependents.length
            : t === "documents" ? data.documents.length
            : t === "files" ? data.files.length
            : null;

          return (
            <button key={t}
              className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setTab(t)}>
              <Icon size={15} />
              {L(t)}
              {count != null && count > 0 && (
                <span className="num" style={{ opacity: .7 }}>({count})</span>
              )}
            </button>
          );
        })}
      </div>

      {error && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
        }}>
          {error}
        </div>
      )}

      {/* ══ المحتوى ══ */}

      {tab === "personal" && (
        <EditableSection
          title={L("personal")} icon={IcUser} L={L} busy={saving}
          readOnly={false}
          values={data.personal}
          onSave={(d) => save("personal", d)}
          fields={[
            { key: "first_name_ar", label: L("firstName") },
            { key: "father_name_ar", label: L("fatherName") },
            { key: "grandfather_name_ar", label: L("grandName") },
            { key: "family_name_ar", label: L("familyName") },
            { key: "full_name_en", label: L("fullNameEn") },
            { key: "gender", label: L("gender"), kind: "select",
              options: [{ value: "male", label: L("male") },
                        { value: "female", label: L("female") }] },
            { key: "birth_date", label: L("birthDate"), kind: "date" },
            { key: "marital_status", label: L("maritalStatus"), kind: "select",
              options: [{ value: "single", label: L("single") },
                        { value: "married", label: L("married") },
                        { value: "divorced", label: L("divorced") },
                        { value: "widowed", label: L("widowed") }] },
            { key: "nationality_code", label: L("nationality") },
            { key: "id_number", label: L("idNumber"), readOnly: true },
            { key: "id_expiry_date", label: L("idExpiry"), kind: "date" },
            { key: "passport_number", label: L("passportNumber") },
            { key: "passport_expiry_date", label: L("passportExpiry"),
              kind: "date" },
            { key: "border_number", label: L("borderNumber") },
          ]}
        />
      )}

      {tab === "job" && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ marginBottom: 12 }}>
            <IcOrg size={19} />
            <h3 style={{ fontSize: "1rem" }}>{L("job")}</h3>
          </div>
          <Row label={L("jobTitle")} value={data.job.job_title} />
          <Row label={L("department")} value={data.job.department} />
          <Row label={L("branch")} value={data.job.branch} />
          <Row label={L("site")} value={data.job.site} />
          <Row label={L("manager")} value={data.job.manager} />
          <Row label={`${L("grade")} (${L("optional")})`}
            value={data.job.grade} />
          <Row label={`${L("step")} (${L("optional")})`}
            value={data.job.step} />
        </div>
      )}

      {tab === "contract" && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ marginBottom: 12 }}>
            <IcDoc size={19} />
            <h3 style={{ fontSize: "1rem" }}>{L("contract")}</h3>
          </div>
          <Row label={L("contractType")} value={data.contract.contract_type} />
          <Row label={L("joinDate")} value={data.contract.join_date} numeric />
          <Row label={L("serviceStart")}
            value={data.contract.service_start_date} numeric />
          <Row label={L("contractStart")}
            value={data.contract.contract_start_date} numeric />
          <Row label={L("contractEnd")}
            value={data.contract.contract_end_date} numeric />
          <Row label={L("probationDays")}
            value={data.contract.probation_days} numeric />
          <Row label={L("probationEnd")} value={
            data.contract.in_probation ? (
              <span className="badge badge-warn">
                <span className="num">{String(data.contract.probation_end_date)}</span>
              </span>
            ) : String(data.contract.probation_end_date ?? "—")
          } />
          <Row label={L("serviceLength")} value={
            <>
              <span className="num">{String(data.contract.service_years)}</span>
              {" "}{L("years")}{" "}
              <span className="num">{String(data.contract.service_months)}</span>
              {" "}{L("months")}
            </>
          } />
        </div>
      )}

      {tab === "salary" && (
        <div className="stack">
          <div className="card" style={{ padding: 20 }}>
            <div className="spread" style={{ marginBottom: 14 }}>
              <div className="row">
                <IcPayroll size={19} />
                <h3 style={{ fontSize: "1rem" }}>{L("salary")}</h3>
              </div>
              <div style={{
                fontSize: "1.5rem", fontWeight: 600, color: "var(--teal)",
              }}>
                <span className="num">{money(data.salary.gross)}</span>
              </div>
            </div>

            <table className="table">
              <thead>
                <tr>
                  <th>{L("component")}</th>
                  <th style={{ textAlign: "end" }}>{L("amount")}</th>
                  <th style={{ width: 120 }}>{L("inGosi")}</th>
                  <th style={{ width: 130 }}>{L("inEosb")}</th>
                </tr>
              </thead>
              <tbody>
                {data.salary.lines.map((l, i) => (
                  <tr key={i}>
                    <td>{l.component}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{money(l.amount)}</span>
                    </td>
                    <td>{l.in_gosi
                      ? <span className="badge badge-ok">{L("yes")}</span> : "—"}</td>
                    <td>{l.in_eosb
                      ? <span className="badge badge-ok">{L("yes")}</span> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.salary.history.length > 1 && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>
                {L("history")}
              </h3>
              {data.salary.history.map((h, i) => (
                <Row key={i}
                  label={`${L("effectiveFrom")} ${h.effective_from}`}
                  value={money(h.gross)} numeric />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "gosi" && (
        <EditableSection
          title={L("gosi")} icon={IcCheck} L={L} busy={saving}
          readOnly={false}
          values={data.gosi}
          onSave={(d) => save("gosi", d)}
          fields={[
            { key: "is_registered", label: L("gosiRegistered"), kind: "bool" },
            { key: "establishment_no", label: L("establishmentNo") },
            { key: "declared_wage", label: L("declaredWage"), kind: "number" },
            { key: "borne_by_company", label: L("borneByCompany"),
              kind: "bool" },
            { key: "is_mol_registered", label: L("molRegistered"),
              kind: "bool" },
            { key: "include_in_wps", label: L("wps"), kind: "bool" },
          ]}
        />
      )}

      {tab === "bank" && (
        <EditableSection
          title={L("bank")} icon={IcWallet} L={L} busy={saving}
          readOnly={false}
          values={data.bank}
          onSave={(d) => save("bank", d)}
          fields={[
            { key: "iban", label: L("iban") },
            { key: "bank_name", label: L("bankName"), readOnly: true },
            { key: "payment_method", label: L("paymentMethod") },
          ]}
        />
      )}

      {tab === "dependents" && (
        <DependentsTab empId={empId} rows={data.dependents} L={L}
          onChanged={load} />
      )}

      {tab === "contact" && (
        <ContactTab empId={empId} personal={data.personal}
          contacts={data.emergency_contacts} L={L} onChanged={load} />
      )}

      {tab === "documents" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {data.documents.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
              {L("empty")}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("docType")}</th>
                  <th style={{ textAlign: "end" }}>{L("docNumber")}</th>
                  <th style={{ textAlign: "end" }}>{L("issueDate")}</th>
                  <th style={{ textAlign: "end" }}>{L("expiryDate")}</th>
                  <th style={{ textAlign: "end" }}>{L("daysLeft")}</th>
                </tr>
              </thead>
              <tbody>
                {data.documents.map((d) => (
                  <tr key={d.id}>
                    <td>{d.type_label}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.document_number || "—"}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.issue_date || "—"}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.expiry_date || "—"}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.days_left == null ? "—"
                        : d.days_left < 0 ? (
                          <span className="badge badge-danger">{L("expired")}</span>
                        ) : (
                          <span className={d.days_left <= 30
                            ? "badge badge-warn" : "badge"}>
                            <span className="num">{d.days_left}</span> {L("days")}
                          </span>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "files" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {data.files.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
              {L("empty")}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("fileName")}</th>
                  <th style={{ width: 160 }}>{L("fileKind")}</th>
                  <th style={{ width: 110, textAlign: "end" }}>{L("fileSize")}</th>
                  <th style={{ width: 100 }} />
                </tr>
              </thead>
              <tbody>
                {data.files.map((f) => (
                  <tr key={f.id}>
                    <td className="truncate">{f.name}</td>
                    <td><span className="badge">{f.kind_label}</span></td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{f.size}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <a className="btn btn-sm btn-ghost"
                        href={`${API_BASE}${f.url}`} target="_blank"
                        rel="noreferrer">
                        {L("view")}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "audit" && <AuditTab empId={empId} L={L} />}
    </div>
  );
}

/* ══ السجل الوظيفي ══ */

function AuditTab({
  empId, L,
}: {
  empId: number;
  L: (k: string, f?: string) => string;
}) {
  const [entries, setEntries] = useState<{
    id: number; action_label: string; actor: string; at: string;
    summary: string;
    changes: { field_label: string; from: unknown; to: unknown }[];
  }[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    apiGet<{ entries: typeof entries }>(`/audit/employment/${empId}/`)
      .then((d) => { setEntries(d.entries || []); setBusy(false); })
      .catch(() => { setEntries([]); setBusy(false); });
  }, [empId]);

  if (busy) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 10 }}>
      {entries.map((e) => (
        <div key={e.id} className="card" style={{ padding: 14 }}>
          <div className="spread" style={{ marginBottom: 6 }}>
            <span className="badge">{e.action_label}</span>
            <span className="muted" style={{ fontSize: ".82rem" }}>
              {e.actor} · <span className="num">{(e.at || "").slice(0, 16)}</span>
            </span>
          </div>
          {e.summary && <div style={{ fontSize: ".9rem" }}>{e.summary}</div>}
          {e.changes.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {e.changes.map((c, i) => (
                <div key={i} className="muted" style={{ fontSize: ".85rem" }}>
                  {c.field_label}:{" "}
                  <span style={{ textDecoration: "line-through" }}>
                    {String(c.from ?? "—")}
                  </span>
                  {" ← "}
                  <span style={{ color: "var(--ink)" }}>
                    {String(c.to ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

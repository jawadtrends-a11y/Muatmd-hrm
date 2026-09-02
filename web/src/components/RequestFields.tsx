"use client";

/**
 * حقول الطلبات الديناميكية — مشتركة بين «خدماتي» و«إسناد طلب».
 *
 * النموذج يُبنى من حقول النوع القادمة من الخادم (ق-9: الإعداد لا
 * الكود)، فإضافة نوع طلب جديد لا تحتاج تعديل أي شاشة.
 *
 * وكان داخل شاشة «خدماتي» وحدها — فنُقل حين احتاجته شاشة الإسناد،
 * لئلا يصير نموذجان يتباعدان مع كل تعديل.
 */
import { useRef, useState } from "react";

import { apiUpload, ApiError } from "@/lib/api";
import DateField from "@/components/DateField";

/**
 * أسماء الحقول — داخل المكوّن لا في كل شاشة.
 *
 * فالمكوّن هو من يعرف حقوله، وترك الترجمة لكل شاشة يعني أن شاشة
 * جديدة تعرض «attachment_url» خامًا حتى ينتبه أحد.
 */
const FIELD_NAMES: Record<string, { ar: string; en: string }> = {
  leave_type_code: { ar: "نوع الإجازة", en: "Leave type" },
  start_date: { ar: "تاريخ البداية", en: "Start date" },
  end_date: { ar: "تاريخ النهاية", en: "End date" },
  work_date: { ar: "تاريخ اليوم", en: "Date" },
  days: { ar: "عدد الأيام", en: "Days" },
  hours: { ar: "عدد الساعات", en: "Hours" },
  reason: { ar: "السبب", en: "Reason" },
  note: { ar: "ملاحظة", en: "Note" },
  attachment_url: { ar: "المرفق", en: "Attachment" },
  first_in: { ar: "وقت الحضور الصحيح", en: "Correct check-in" },
  last_out: { ar: "وقت الانصراف الصحيح", en: "Correct check-out" },
  from_time: { ar: "من الساعة", en: "From" },
  to_time: { ar: "إلى الساعة", en: "To" },
  fix_target: { ar: "أي بصمة تصحّح؟", en: "Which punch?" },
  amount: { ar: "المبلغ", en: "Amount" },
  installments: { ar: "عدد الأقساط", en: "Installments" },
  asset_name: { ar: "اسم العهدة", en: "Asset name" },
  asset_category: { ar: "التصنيف", en: "Category" },
  serial_number: { ar: "الرقم التسلسلي", en: "Serial" },
  value: { ar: "القيمة", en: "Value" },
  destination: { ar: "الوجهة", en: "Destination" },
  purpose: { ar: "الغرض", en: "Purpose" },
  estimated_cost: { ar: "التكلفة التقديرية", en: "Estimated cost" },
  travel_date: { ar: "تاريخ السفر", en: "Travel date" },
  family_members: { ar: "عدد أفراد العائلة", en: "Family members" },
  certificate_type: { ar: "نوع الخطاب", en: "Certificate type" },
  addressed_to: { ar: "موجّه إلى", en: "Addressed to" },
  include_salary: { ar: "يتضمن الراتب", en: "Include salary" },
  last_working_day: { ar: "آخر يوم عمل", en: "Last working day" },
  termination_reason: { ar: "سبب الإنهاء", en: "Termination reason" },
  request_date: { ar: "تاريخ الطلب", en: "Request date" },
};

/** اسم الحقل بلغة الواجهة — والمجهول يظهر برمزه لا يُخفى */
function fieldName(name: string): string {
  const t = FIELD_NAMES[name];
  if (!t) return name;
  const lang = typeof document !== "undefined"
    ? document.documentElement.lang || "ar"
    : "ar";
  return lang === "en" ? t.en : t.ar;
}

export function fieldKind(name: string): string {
  if (name.endsWith("_date") || name === "work_date") return "date";
  // first_in و last_out أوقات أيضًا — لا تنتهي بـ_time
  if (name.endsWith("_time") || name === "first_in"
      || name === "last_out") return "time";
  if (["days", "installments", "hours", "amount", "value",
       "estimated_cost", "family_members"].includes(name)) return "number";
  if (name === "include_salary") return "bool";
  if (name === "attachment_url") return "attachment";
  if (name === "leave_type_code") return "leave_type";
  if (name === "fix_target") return "fix_target";
  if (name === "termination_reason") return "termination_reason";
  if (name === "asset_category") return "asset_category";
  if (name === "certificate_type") return "certificate_type";
  if (["reason", "purpose", "note"].includes(name)) return "textarea";
  return "text";
}

const ASSET_CATEGORIES = [
  ["electronics", "أجهزة إلكترونية"], ["vehicle", "مركبة"],
  ["tools", "أدوات"], ["furniture", "أثاث"], ["other", "أخرى"],
];

const FIX_TARGETS = [
  ["in", "الحضور"], ["out", "الانصراف"], ["both", "كلاهما"],
];

const CERTIFICATE_TYPES = [
  ["employment", "شهادة تعريف بالعمل"],
  ["salary", "شهادة راتب"],
  ["experience", "شهادة خبرة"],
  ["bank", "خطاب لبنك"],
  ["embassy", "خطاب لسفارة"],
];


/* ══ حقل ديناميكي — خارج المكوّن الرئيسي ══ */

/* ══ حقل رفع مرفق (ق-70) ══ */

function AttachmentField({
  value, onChange, L,
}: {
  value: string;
  onChange: (v: string) => void;
  L: (k: string, f?: string) => string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function pick(file: File) {
    setBusy(true);
    setError("");
    try {
      const res = await apiUpload<{ url: string; name: string }>(
        "/files/", file);
      onChange(res.url);
      setName(res.name);
    } catch (e) {
      setError((e as ApiError).message || L("uploadFailed", "تعذّر الرفع"));
    } finally {
      setBusy(false);
    }
  }

  if (value) {
    return (
      <div className="row" style={{ gap: 8, alignItems: "center" }}>
        <a href={value} target="_blank" rel="noreferrer"
          style={{ color: "var(--teal)", fontWeight: 500 }}>
          {name || L("attached", "المرفق")}
        </a>
        <button className="btn btn-sm btn-ghost"
          onClick={() => { onChange(""); setName(""); }}>
          {L("remove", "إزالة")}
        </button>
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 4 }}>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.webp"
        style={{ display: "none" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) pick(f);
        }}
      />
      <button className="btn btn-sm" disabled={busy}
        onClick={() => inputRef.current?.click()}>
        {busy ? L("uploading", "جارٍ الرفع…") : L("pickFile", "اختر ملفًا")}
      </button>
      {error && (
        <div style={{ color: "var(--danger)", fontSize: ".8rem" }}>{error}</div>
      )}
    </div>
  );
}


export default function DynField({
  name, required, value, onChange, leaveTypes, terminationReasons, L,
}: {
  name: string;
  required: boolean;
  value: string;
  onChange: (v: string) => void;
  leaveTypes: { code: string; name_ar: string }[];
  terminationReasons: { code: string; name_ar: string }[];
  L: (k: string, f?: string) => string;
}) {
  const kind = fieldKind(name);

  const label = (
    <label className="label">
      {fieldName(name)}
      {required && (
        <span style={{ color: "var(--danger)", marginInlineStart: 3 }}>*</span>
      )}
    </label>
  );

  const wide = kind === "textarea";

  return (
    <div className="field" style={{
      minWidth: wide ? 300 : 180,
      maxWidth: wide ? 460 : 230,
      flex: wide ? 2 : 1,
    }}>
      {label}

      {kind === "textarea" ? (
        <textarea className="textarea" value={value} rows={2}
          onChange={(e) => onChange(e.target.value)} />
      ) : kind === "bool" ? (
        <select className="select" value={value || "0"}
          onChange={(e) => onChange(e.target.value)}>
          <option value="0">{L("no")}</option>
          <option value="1">{L("yes")}</option>
        </select>
      ) : kind === "leave_type" ? (
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {leaveTypes.map((t) => (
            <option key={t.code} value={t.code}>{t.name_ar}</option>
          ))}
        </select>
      ) : kind === "asset_category" ? (
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          {ASSET_CATEGORIES.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      ) : kind === "fix_target" ? (
        <div className="row" style={{ gap: 4 }}>
          {FIX_TARGETS.map(([v, l]) => (
            <button key={v} type="button"
              className={`btn btn-sm ${value === v ? "btn-primary" : ""}`}
              onClick={() => onChange(v)}>
              {l}
            </button>
          ))}
        </div>
      ) : kind === "termination_reason" ? (
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {terminationReasons.map((r) => (
            <option key={r.code} value={r.code}>{r.name_ar}</option>
          ))}
        </select>
      ) : kind === "certificate_type" ? (
        <select className="select" value={value}
          onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {CERTIFICATE_TYPES.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      ) : kind === "attachment" ? (
        <AttachmentField value={value} onChange={onChange} L={L} />
      ) : kind === "date" ? (
        <DateField value={value} onChange={onChange} />
      ) : (
        <input
          className="input"
          type={kind === "time" ? "time" : kind === "number" ? "number" : "text"}
          dir={kind === "number" || kind === "time" ? "ltr" : undefined}
          step={kind === "time" ? 60 : undefined}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}

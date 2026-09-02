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
import DateField from "@/components/DateField";

export function fieldKind(name: string): string {
  if (name.endsWith("_date") || name === "work_date") return "date";
  // first_in و last_out أوقات أيضًا — لا تنتهي بـ_time
  if (name.endsWith("_time") || name === "first_in"
      || name === "last_out") return "time";
  if (["days", "installments", "hours", "amount", "value",
       "estimated_cost", "family_members"].includes(name)) return "number";
  if (name === "include_salary") return "bool";
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
      {L(name, name)}
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

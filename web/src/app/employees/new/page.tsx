"use client";

/**
 * إضافة موظف — قلب النظام.
 *
 * ق-5: الهوية والجوال منع صارم، والاسم تحذير يُتجاوز بـforce.
 * ق-15: أعلام التسجيل تبدأ مطفأة — التوظيف مستقل عن التسجيل.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import NationalityField from "@/components/NationalityField";
import { IcAlert, IcCheck, IcUser } from "@/components/Icons";

const T: Dict = {
  title: { ar: "موظف جديد", en: "New employee" },
  back: { ar: "رجوع", en: "Back" },
  // الأقسام
  personal: { ar: "البيانات الشخصية", en: "Personal" },
  employment: { ar: "بيانات التوظيف", en: "Employment" },
  salary: { ar: "الراتب", en: "Salary" },
  // الشخصية
  firstName: { ar: "الاسم الأول", en: "First name" },
  fatherName: { ar: "اسم الأب", en: "Father name" },
  grandName: { ar: "اسم الجد", en: "Grandfather name" },
  familyName: { ar: "اسم العائلة", en: "Family name" },
  fullNameEn: { ar: "الاسم بالإنجليزية", en: "Full name (English)" },
  gender: { ar: "الجنس", en: "Gender" },
  male: { ar: "ذكر", en: "Male" },
  female: { ar: "أنثى", en: "Female" },
  nationality: { ar: "الجنسية", en: "Nationality" },
  idType: { ar: "نوع الهوية", en: "ID type" },
  nationalId: { ar: "هوية وطنية", en: "National ID" },
  iqama: { ar: "إقامة", en: "Iqama" },
  border: { ar: "رقم حدود", en: "Border number" },
  idNumber: { ar: "رقم الهوية", en: "ID number" },
  mobile: { ar: "الجوال", en: "Mobile" },
  email: { ar: "البريد", en: "Email" },
  // التوظيف
  employeeNo: { ar: "الرقم الوظيفي", en: "Employee No." },
  joinDate: { ar: "تاريخ المباشرة", en: "Join date" },
  serviceStart: { ar: "بداية الخدمة المحتسبة", en: "Service start" },
  serviceHint: {
    ar: "اتركه فارغًا إن كان نفس تاريخ المباشرة — يُستخدم عند نقل خدمة سابقة",
    en: "Leave empty if same as join date",
  },
  probation: { ar: "أيام التجربة", en: "Probation days" },
  probationHint: {
    ar: "النظام يسمح بـ90 يومًا، وتُمدَّد لـ180 باتفاق مكتوب",
    en: "90 days by law, extendable to 180",
  },
  iban: { ar: "الآيبان", en: "IBAN" },
  ibanHint: {
    ar: "24 خانة تبدأ بـSA — يُتحقق منه فورًا",
    en: "24 characters starting with SA",
  },
  // الراتب
  component: { ar: "المكوّن", en: "Component" },
  amount: { ar: "المبلغ", en: "Amount" },
  addLine: { ar: "إضافة بند", en: "Add line" },
  totalSalary: { ar: "إجمالي الراتب", en: "Total salary" },
  salaryHint: {
    ar: "الأساسي إلزامي — والبدلات تحدد أجر مكافأة نهاية الخدمة بأعلامها",
    en: "Basic is required",
  },
  // عام
  save: { ar: "حفظ الموظف", en: "Save employee" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  required: { ar: "أكمل الحقول المطلوبة", en: "Complete required fields" },
  saved: { ar: "أُضيف الموظف", en: "Employee added" },
  ibanBad: {
    ar: "الآيبان يجب أن يكون SA متبوعًا بـ22 رقمًا",
    en: "IBAN must be SA followed by 22 digits",
  },
  warnings: { ar: "تنبيهات", en: "Warnings" },
  duplicate: { ar: "شخص مكرر", en: "Duplicate person" },
  forceAnyway: { ar: "متابعة رغم التنبيه", en: "Continue anyway" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
};


type Component = { id: number; code: string; name_ar: string;
                   is_recurring: boolean };
type Line = { code: string; amount: string };


/* ══ حقل — خارج المكوّن الرئيسي ══ */

function F({
  label, hint, required, children, wide,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="field" style={{
      minWidth: wide ? 300 : 190, maxWidth: wide ? 420 : 240, flex: 1,
    }}>
      <label className="label">
        {label}
        {required && (
          <span style={{ color: "var(--danger)", marginInlineStart: 3 }}>*</span>
        )}
      </label>
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export default function NewEmployeePage() {
  const router = useRouter();
  const { L } = useT(T);

  const [components, setComponents] = useState<Component[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [needsForce, setNeedsForce] = useState(false);

  // الشخصية
  const [firstName, setFirstName] = useState("");
  const [fatherName, setFatherName] = useState("");
  const [grandName, setGrandName] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [fullNameEn, setFullNameEn] = useState("");
  const [gender, setGender] = useState("male");
  const [nationality, setNationality] = useState("SA");
  const [idType, setIdType] = useState("national_id");
  const [idNumber, setIdNumber] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");

  // التوظيف
  const [employeeNo, setEmployeeNo] = useState("");
  const [joinDate, setJoinDate] = useState("");
  const [serviceStart, setServiceStart] = useState("");
  const [probation, setProbation] = useState("90");
  const [iban, setIban] = useState("");

  // الراتب
  const [lines, setLines] = useState<Line[]>([{ code: "BASIC", amount: "" }]);

  useEffect(() => {
    apiGet<Component[]>("/payroll/components/")
      .then((d) => {
        setComponents(d.filter((c) => c.is_recurring !== false));
        setBusy(false);
      })
      .catch(() => setBusy(false));
  }, []);

  // نوع الهوية يتبع الجنسية تلقائيًا
  useEffect(() => {
    setIdType(nationality === "SA" ? "national_id" : "iqama");
  }, [nationality]);

  const total = lines.reduce(
    (s, l) => s + (Number(l.amount) || 0), 0);

  // تحقق فوري من الصيغة — 24 خانة تبدأ بـSA
  const ibanBad = iban.trim().length > 0 &&
    !/^SA\d{22}$/.test(iban.trim());

  // اسم البنك للعرض (ق-57): معروف → اسمه، وإلا «بنوك أخرى».
  // عرض لا حكم — مسؤولية صحة الآيبان على الشركة.
  const [bankLabel, setBankLabel] = useState("");

  useEffect(() => {
    const v = iban.trim().toUpperCase();
    if (v.length < 6 || !v.startsWith("SA")) {
      setBankLabel("");
      return;
    }
    let alive = true;
    apiGet<{ label: string }>(`/payroll/bank-lookup/?iban=${v}`)
      .then((r) => { if (alive) setBankLabel(r.label || ""); })
      .catch(() => { if (alive) setBankLabel(""); });
    return () => { alive = false; };
  }, [iban]);

  const missing =
    !firstName.trim() || !familyName.trim() || !idNumber.trim() ||
    !employeeNo.trim() || !joinDate ||
    !lines.some((l) => l.code === "BASIC" && Number(l.amount) > 0) ||
    ibanBad;

  async function save(force = false) {
    setSaving(true);
    setError("");
    setWarnings([]);
    try {
      const res = await apiPost<{ employee_no: string; employment_id: number;
                                  warnings: string[] }>("/employees/", {
        first_name_ar: firstName.trim(),
        father_name_ar: fatherName.trim(),
        grandfather_name_ar: grandName.trim(),
        family_name_ar: familyName.trim(),
        full_name_en: fullNameEn.trim(),
        gender,
        nationality_code: nationality,
        id_type: idType,
        id_number: idNumber.trim(),
        mobile: mobile.trim(),
        email: email.trim(),
        employee_no: employeeNo.trim(),
        join_date: joinDate,
        service_start_date: serviceStart || null,
        probation_days: Number(probation) || 90,
        iban: iban.trim(),
        salary_lines: lines
          .filter((l) => l.code && Number(l.amount) > 0)
          .map((l) => ({ code: l.code, amount: l.amount })),
        force,
      });

      if (res.warnings?.length) {
        setWarnings(res.warnings);
        setTimeout(() => router.push(`/employees/${res.employment_id}`), 2500);
      } else {
        router.push(`/employees/${res.employment_id}`);
      }
    } catch (e) {
      const err = e as ApiError;
      if (err.code === "duplicate_person") {
        const blocking = (err.detail as { blocking?: boolean })?.blocking;
        setNeedsForce(!blocking);
        setError(err.message);
      } else {
        setError(err.message);
      }
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

  return (
    <div className="stack">
      <div>
        <button className="btn btn-sm btn-ghost"
          onClick={() => router.push("/employees")}>
          ← {L("back")}
        </button>
        <h1 style={{ marginTop: 8 }}>{L("title")}</h1>
      </div>

      {/* ══ البيانات الشخصية ══ */}
      <div className="card" style={{ padding: 20 }}>
        <div className="row" style={{ marginBottom: 14 }}>
          <IcUser size={19} />
          <h2 style={{ fontSize: "1rem" }}>{L("personal")}</h2>
        </div>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
          <F label={L("firstName")} required>
            <input className="input" value={firstName} autoFocus
              onChange={(e) => setFirstName(e.target.value)} />
          </F>
          <F label={L("fatherName")}>
            <input className="input" value={fatherName}
              onChange={(e) => setFatherName(e.target.value)} />
          </F>
          <F label={L("grandName")}>
            <input className="input" value={grandName}
              onChange={(e) => setGrandName(e.target.value)} />
          </F>
          <F label={L("familyName")} required>
            <input className="input" value={familyName}
              onChange={(e) => setFamilyName(e.target.value)} />
          </F>
        </div>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
          <F label={L("fullNameEn")} wide>
            <input className="input" dir="ltr" value={fullNameEn}
              onChange={(e) => setFullNameEn(e.target.value)} />
          </F>
          <F label={L("gender")}>
            <select className="select" value={gender}
              onChange={(e) => setGender(e.target.value)}>
              <option value="male">{L("male")}</option>
              <option value="female">{L("female")}</option>
            </select>
          </F>
          <F label={L("nationality")}>
            <NationalityField value={nationality} onChange={setNationality} />
          </F>
        </div>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
          <F label={L("idType")}>
            <select className="select" value={idType}
              onChange={(e) => setIdType(e.target.value)}>
              <option value="national_id">{L("nationalId")}</option>
              <option value="iqama">{L("iqama")}</option>
              <option value="border_number">{L("border")}</option>
            </select>
          </F>
          <F label={L("idNumber")} required>
            <input className="input" dir="ltr" inputMode="numeric"
              maxLength={10} value={idNumber}
              onChange={(e) => setIdNumber(
                e.target.value.replace(/\D/g, ""))} />
          </F>
          <F label={L("mobile")}>
            <input className="input" dir="ltr" inputMode="tel"
              placeholder="05XXXXXXXX" value={mobile}
              onChange={(e) => setMobile(e.target.value)} />
          </F>
          <F label={L("email")}>
            <input className="input" dir="ltr" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </F>
        </div>
      </div>

      {/* ══ بيانات التوظيف ══ */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 14 }}>
          {L("employment")}
        </h2>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
          <F label={L("employeeNo")} required>
            <input className="input" dir="ltr" value={employeeNo}
              onChange={(e) => setEmployeeNo(e.target.value)} />
          </F>
          <F label={L("joinDate")} required>
            <DateField value={joinDate} onChange={setJoinDate} />
          </F>
          <F label={L("serviceStart")} hint={L("serviceHint")}>
            <DateField value={serviceStart} onChange={setServiceStart} />
          </F>
          <F label={L("probation")} hint={L("probationHint")}>
            <input className="input" type="number" dir="ltr" value={probation}
              onChange={(e) => setProbation(e.target.value)} />
          </F>
        </div>

        <div className="row" style={{ alignItems: "flex-start" }}>
          <F label={L("iban")}
            hint={ibanBad ? undefined : L("ibanHint")} wide>
            <input
              className="input" dir="ltr" maxLength={24} placeholder="SA…"
              style={ibanBad ? { borderColor: "var(--danger)" } : undefined}
              value={iban}
              onChange={(e) => setIban(
                e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} />
            {ibanBad && (
              <div className="error-text">
                {L("ibanBad")} ({iban.trim().length}/24)
              </div>
            )}
            {!ibanBad && bankLabel && (
              <div style={{
                marginTop: 4, fontSize: ".88rem", fontWeight: 500,
                color: "var(--teal)",
              }}>
                {bankLabel}
              </div>
            )}
          </F>
        </div>
      </div>

      {/* ══ الراتب ══ */}
      <div className="card" style={{ padding: 20 }}>
        <div className="spread" style={{ marginBottom: 4 }}>
          <h2 style={{ fontSize: "1rem" }}>{L("salary")}</h2>
          <div style={{ fontSize: "1.15rem", fontWeight: 600 }}>
            {L("totalSalary")}:{" "}
            <span className="num" style={{ color: "var(--teal)" }}>
              {total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
        </div>
        <div className="muted" style={{ fontSize: ".82rem", marginBottom: 12 }}>
          {L("salaryHint")}
        </div>

        {lines.map((line, i) => (
          <div key={i} className="row" style={{ marginBottom: 8 }}>
            <select className="select" style={{ maxWidth: 240 }}
              value={line.code}
              onChange={(e) => {
                const next = [...lines];
                next[i] = { ...next[i], code: e.target.value };
                setLines(next);
              }}>
              <option value="">—</option>
              {components.map((c) => (
                <option key={c.id} value={c.code}>{c.name_ar}</option>
              ))}
            </select>

            <input className="input" type="number" dir="ltr"
              style={{ maxWidth: 180 }} value={line.amount}
              onChange={(e) => {
                const next = [...lines];
                next[i] = { ...next[i], amount: e.target.value };
                setLines(next);
              }} />

            {lines.length > 1 && (
              <button className="btn btn-sm btn-ghost"
                style={{ color: "var(--danger)" }}
                onClick={() => setLines(lines.filter((_, j) => j !== i))}>
                ×
              </button>
            )}
          </div>
        ))}

        <button className="btn btn-sm"
          onClick={() => setLines([...lines, { code: "", amount: "" }])}>
          + {L("addLine")}
        </button>
      </div>

      {/* ══ الرسائل ══ */}
      {error && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "12px 15px", borderRadius: "var(--radius-sm)",
        }}>
          <div className="row">
            <IcAlert size={18} />
            <span className="grow">{error}</span>
            {needsForce && (
              <button className="btn btn-sm" onClick={() => save(true)}>
                {L("forceAnyway")}
              </button>
            )}
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "12px 15px", borderRadius: "var(--radius-sm)",
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {L("saved")} — {L("warnings")}
          </div>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontSize: ".88rem" }}>• {w}</div>
          ))}
        </div>
      )}

      <div className="row">
        <button className="btn btn-primary" style={{ height: 42, minWidth: 160 }}
          disabled={saving || missing} onClick={() => save(false)}>
          <IcCheck size={17} />
          {saving ? L("saving") : L("save")}
        </button>
        <button className="btn btn-ghost"
          onClick={() => router.push("/employees")}>
          {L("cancel")}
        </button>
        {missing && (
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("required")}
          </span>
        )}
      </div>
    </div>
  );
}

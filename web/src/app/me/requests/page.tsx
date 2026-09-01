"use client";

/**
 * خدماتي — تقديم الطلبات (ق-58).
 *
 * النماذج تُبنى تلقائيًا من /me/request-types/ — فإضافة نوع
 * في الخادم تظهر هنا بلا تعديل واجهة.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import {
  IcAlert, IcCheck, IcClock, IcDoc, IcHome, IcLeave, IcWallet,
} from "@/components/Icons";

const T: Dict = {
  title: { ar: "خدماتي", en: "My services" },
  subtitle: {
    ar: "اختر الخدمة التي تريد طلبها",
    en: "Choose a service to request",
  },
  back: { ar: "رجوع للخدمات", en: "Back" },
  submit: { ar: "تقديم الطلب", en: "Submit" },
  submitting: { ar: "جارٍ التقديم…", en: "Submitting…" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  required: { ar: "أكمل الحقول المطلوبة", en: "Complete required fields" },
  submitted: { ar: "قُدّم الطلب", en: "Request submitted" },
  trackIt: { ar: "تابعه من «طلباتي»", en: "Track it in My Requests" },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك — راجع مدير الموارد البشرية",
    en: "No employee profile linked",
  },
  note: { ar: "ملاحظة", en: "Note" },
  warnings: { ar: "تنبيهات", en: "Warnings" },

  // أسماء الحقول
  leave_type_code: { ar: "نوع الإجازة", en: "Leave type" },
  start_date: { ar: "تاريخ البداية", en: "Start date" },
  days: { ar: "عدد الأيام", en: "Days" },
  work_date: { ar: "تاريخ اليوم", en: "Date" },
  reason: { ar: "السبب", en: "Reason" },
  first_in: { ar: "وقت الحضور", en: "Check-in" },
  last_out: { ar: "وقت الانصراف", en: "Check-out" },
  from_time: { ar: "من الساعة", en: "From" },
  to_time: { ar: "إلى الساعة", en: "To" },
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
  hours: { ar: "عدد الساعات", en: "Hours" },
  end_date: { ar: "تاريخ النهاية", en: "End date" },
  fix_target: { ar: "أي بصمة تصحّح؟", en: "Which punch?" },
  fixIn: { ar: "الحضور", en: "Check-in" },
  fixOut: { ar: "الانصراف", en: "Check-out" },
  fixBoth: { ar: "كلاهما", en: "Both" },
  termination_reason: { ar: "سبب الإنهاء", en: "Termination reason" },
  request_date: { ar: "تاريخ الطلب", en: "Request date" },
  // المعاينة
  preview: { ar: "المعاينة", en: "Preview" },
  chargedDays: { ar: "الأيام المخصومة", en: "Days charged" },
  calendarDays: { ar: "أيام تقويمية", en: "Calendar days" },
  excludedDays: { ar: "أيام لا تُخصم", en: "Not charged" },
  balanceBefore: { ar: "رصيدك الآن", en: "Balance now" },
  balanceAfter: { ar: "رصيدك بعدها", en: "After" },
  returnDate: { ar: "تعود في", en: "Return on" },
  tripDays: { ar: "أيام الرحلة", en: "Trip days" },
  otDuration: { ar: "المدة المحتسبة", en: "Duration" },
  noticeDays: { ar: "مدة الإشعار", en: "Notice period" },
  duplicateFound: { ar: "طلب مكرر", en: "Duplicate" },
  currentRecord: { ar: "السجل الحالي", en: "Current record" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

type ReqType = {
  code: string;
  name_ar: string;
  icon: string;
  hint_ar: string;
  required_fields: string[];
  optional_fields: string[];
};

const ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  leave: IcLeave, clock: IcClock, home: IcHome,
  wallet: IcWallet, doc: IcDoc, alert: IcAlert,
};

// نوع الحقل يُستنتج من اسمه
function fieldKind(name: string): string {
  if (name.endsWith("_date") || name === "work_date") return "date";
  if (name.endsWith("_time")) return "time";
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

function DynField({
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
      ) : (
        <input
          className="input"
          type={kind === "date" ? "date" : kind === "time" ? "time"
                : kind === "number" ? "number" : "text"}
          dir={kind === "number" ? "ltr" : undefined}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}

/* ══ الشاشة ══ */

export default function MyRequestsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { L } = useT(T);

  const [types, setTypes] = useState<ReqType[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<{ code: string; name_ar: string }[]>([]);
  const [selected, setSelected] = useState<ReqType | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [reasons, setReasons] = useState<{ code: string; name_ar: string }[]>([]);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<{ no: string; warnings: string[] } | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    Promise.all([
      apiGet<{ types: ReqType[] }>("/me/request-types/")
        .catch(() => { setDenied(true); return { types: [] }; }),
      apiGet<{ code: string; name_ar: string }[]>("/leaves/types/")
        .catch(() => []),
      // ق-60: الموظف يرى ما يبادر به هو فقط
      apiGet<{ reasons: { code: string; name_ar: string }[] }>(
        "/payroll/termination-reasons/?initiator=employee")
        .then((d) => d.reasons || [])
        .catch(() => []),
    ]).then(([t, lt, rs]) => {
      setTypes(t.types || []);
      setLeaveTypes(lt);
      setReasons(rs);
      setBusy(false);

      // فتح نوع محدد من الرابط (?type=leave)
      const want = params.get("type");
      if (want) {
        const found = (t.types || []).find((x) => x.code === want);
        if (found) pick(found);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = useCallback((t: ReqType) => {
    setSelected(t);
    setValues({});
    setNote("");
    setError("");
    setDone(null);
  }, []);

  const missing = selected
    ? selected.required_fields.filter((f) => !values[f]?.trim())
    : [];

  /**
   * ق-59: المعاينة الحيّة — النظام يحتسب ويعرض قبل التقديم.
   *
   * الموظف يرى الأيام المخصومة ورصيده بعدها، أو مدة الإضافي
   * بالدقيقة، أو تحذير التكرار — قبل أن يضغط «تقديم».
   */
  useEffect(() => {
    if (!selected) { setPreview(null); return; }

    const PREVIEWABLE = ["leave", "overtime", "business_trip",
                         "attendance_fix", "resignation"];
    if (!PREVIEWABLE.includes(selected.code)) { setPreview(null); return; }

    // الحقول اللازمة للمعاينة
    const needed: Record<string, string[]> = {
      leave: ["leave_type_code", "start_date", "end_date"],
      overtime: ["from_time", "to_time"],
      business_trip: ["start_date", "end_date"],
      attendance_fix: ["work_date"],
      resignation: [],
    };
    const req = needed[selected.code] || [];
    if (req.some((f) => !values[f])) { setPreview(null); return; }

    let alive = true;
    setPreviewing(true);
    const payload: Record<string, unknown> = {};
    for (const f of [...selected.required_fields,
                     ...selected.optional_fields]) {
      if (values[f]) payload[f] = values[f];
    }

    apiPost<Record<string, unknown>>("/requests/preview/", {
      request_type: selected.code, payload,
    })
      .then((d) => { if (alive) { setPreview(d); setPreviewing(false); } })
      .catch(() => { if (alive) { setPreview(null); setPreviewing(false); } });

    return () => { alive = false; };
  }, [selected, values]);

  async function submit() {
    if (!selected || missing.length > 0) return;
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      for (const f of [...selected.required_fields,
                       ...selected.optional_fields]) {
        const v = values[f];
        if (v === undefined || v === "") continue;
        payload[f] = fieldKind(f) === "bool" ? v === "1" : v;
      }

      const res = await apiPost<{ request_no: string; warnings: string[] }>(
        "/requests/", {
          request_type: selected.code,
          payload,
          note: note.trim(),
        });

      setDone({ no: res.request_no, warnings: res.warnings || [] });
      setSelected(null);
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

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--copper)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noProfile")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        {selected && (
          <button className="btn btn-sm btn-ghost"
            onClick={() => setSelected(null)}>
            ← {L("back")}
          </button>
        )}
        <h1 style={{ marginTop: selected ? 8 : 0 }}>
          {selected ? selected.name_ar : L("title")}
        </h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {selected ? selected.hint_ar : L("subtitle")}
        </div>
      </div>

      {done && (
        <div style={{
          background: "var(--ok-soft)", color: "var(--ok)",
          padding: "14px 16px", borderRadius: "var(--radius-sm)",
        }}>
          <div className="row" style={{ fontWeight: 600, marginBottom: 4 }}>
            <IcCheck size={18} />
            {L("submitted")} — <span className="num">{done.no}</span>
          </div>
          <div style={{ fontSize: ".88rem" }}>{L("trackIt")}</div>
          {done.warnings.length > 0 && (
            <div style={{ marginTop: 8, color: "var(--copper)" }}>
              {done.warnings.map((w, i) => (
                <div key={i} style={{ fontSize: ".87rem" }}>• {w}</div>
              ))}
            </div>
          )}
          <button className="btn btn-sm" style={{ marginTop: 10 }}
            onClick={() => router.push("/me/track")}>
            {L("trackIt")}
          </button>
        </div>
      )}

      {!selected ? (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))",
          gap: 14,
        }}>
          {types.map((t) => {
            const Icon = ICONS[t.icon] || IcDoc;
            return (
              <button key={t.code} className="card"
                onClick={() => pick(t)}
                style={{
                  padding: 18, textAlign: "start", cursor: "pointer",
                  border: "1px solid var(--line)", background: "var(--paper)",
                  font: "inherit", color: "inherit",
                }}>
                <div style={{ color: "var(--teal)", marginBottom: 8 }}>
                  <Icon size={24} />
                </div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {t.name_ar}
                </div>
                <div className="muted" style={{ fontSize: ".82rem" }}>
                  {t.hint_ar}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
            {selected.required_fields.map((f) => (
              <DynField key={f} name={f} required value={values[f] ?? ""}
                onChange={(v) => setValues({ ...values, [f]: v })}
                leaveTypes={leaveTypes} terminationReasons={reasons} L={L} />
            ))}
            {selected.optional_fields.filter((f) => {
              if (f === "note" || f === "attachment_url") return false;
              // ق-59: حقل الوقت يظهر حسب البصمة المختارة
              if (selected.code === "attendance_fix") {
                const target = values.fix_target || "";
                if (f === "first_in" && target === "out") return false;
                if (f === "last_out" && target === "in") return false;
                if (!target) return false;
              }
              return true;
            }).map((f) => (
              <DynField key={f} name={f} required={false}
                value={values[f] ?? ""}
                onChange={(v) => setValues({ ...values, [f]: v })}
                leaveTypes={leaveTypes} terminationReasons={reasons} L={L} />
            ))}
          </div>

          <div className="field" style={{ maxWidth: 520, marginTop: 8 }}>
            <label className="label">{L("note")}</label>
            <textarea className="textarea" rows={2} value={note}
              onChange={(e) => setNote(e.target.value)} />
          </div>

          {/* ══ المعاينة الحيّة (ق-59) ══ */}
          {preview && !previewing && (
            <div style={{
              marginTop: 16, padding: "14px 16px",
              background: preview.duplicate
                ? "var(--danger-soft)" : "var(--teal-soft)",
              borderRadius: "var(--radius-sm)",
            }}>
              {/* تكرار البصمة */}
              {preview.duplicate ? (
                <div style={{ color: "var(--danger)", fontWeight: 500 }}>
                  <IcAlert size={17} /> {L("duplicateFound")}:{" "}
                  <span className="num">{String(preview.duplicate_no)}</span>
                </div>
              ) : (
                <>
                  {/* الإجازة */}
                  {preview.charged_days != null && (
                    <div className="row" style={{
                      flexWrap: "wrap", gap: 20, alignItems: "flex-start",
                    }}>
                      <div>
                        <div className="muted" style={{ fontSize: ".8rem" }}>
                          {L("chargedDays")}
                        </div>
                        <div style={{
                          fontSize: "1.5rem", fontWeight: 600,
                          color: "var(--teal)",
                        }}>
                          <span className="num">
                            {String(preview.charged_days)}
                          </span>
                        </div>
                      </div>

                      <div>
                        <div className="muted" style={{ fontSize: ".8rem" }}>
                          {L("calendarDays")}
                        </div>
                        <div style={{ fontSize: "1.1rem", fontWeight: 500 }}>
                          <span className="num">
                            {String(preview.calendar_days)}
                          </span>
                        </div>
                      </div>

                      {Number(preview.excluded_days) > 0 && (
                        <div>
                          <div className="muted" style={{ fontSize: ".8rem" }}>
                            {L("excludedDays")}
                          </div>
                          <div style={{ fontSize: "1.1rem", fontWeight: 500 }}>
                            <span className="num">
                              {String(preview.excluded_days)}
                            </span>
                          </div>
                        </div>
                      )}

                      {preview.available_before != null && (
                        <div>
                          <div className="muted" style={{ fontSize: ".8rem" }}>
                            {L("balanceAfter")}
                          </div>
                          <div style={{
                            fontSize: "1.1rem", fontWeight: 600,
                            color: Number(preview.available_after) < 0
                              ? "var(--danger)" : "var(--ink)",
                          }}>
                            {/* السهم داخل span معزول — RTL يقلب
                                الاتجاه لو تُرك في تدفق النص */}
                            <span className="num">
                              {String(preview.available_before)}
                              {" ← "}
                              {String(preview.available_after)}
                            </span>
                          </div>
                        </div>
                      )}

                      {preview.return_date != null && (
                        <div>
                          <div className="muted" style={{ fontSize: ".8rem" }}>
                            {L("returnDate")}
                          </div>
                          <div style={{ fontSize: "1.1rem", fontWeight: 500 }}>
                            <span className="num">
                              {String(preview.return_date)}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* الإضافي */}
                  {preview.label != null && (
                    <div>
                      <div className="muted" style={{ fontSize: ".8rem" }}>
                        {L("otDuration")}
                      </div>
                      <div style={{
                        fontSize: "1.4rem", fontWeight: 600,
                        color: "var(--teal)",
                      }}>
                        {String(preview.label)}
                      </div>
                    </div>
                  )}

                  {/* رحلة العمل */}
                  {preview.days != null && preview.charged_days == null && (
                    <div>
                      <div className="muted" style={{ fontSize: ".8rem" }}>
                        {L("tripDays")}
                      </div>
                      <div style={{
                        fontSize: "1.4rem", fontWeight: 600,
                        color: "var(--teal)",
                      }}>
                        <span className="num">{String(preview.days)}</span>
                      </div>
                      {preview.note != null && (
                        <div className="muted" style={{
                          fontSize: ".84rem", marginTop: 4,
                        }}>
                          {String(preview.note)}
                        </div>
                      )}
                    </div>
                  )}

                  {/* إنهاء العقد */}
                  {preview.notice_days != null && (
                    <div>
                      <div className="row">
                        <span className="muted" style={{ fontSize: ".85rem" }}>
                          {L("noticeDays")}:
                        </span>
                        <strong>
                          <span className="num">
                            {String(preview.notice_days)}
                          </span>{" "}
                          يومًا
                        </strong>
                      </div>
                      <div className="muted" style={{
                        fontSize: ".84rem", marginTop: 4,
                      }}>
                        {String(preview.note || "")}
                      </div>
                    </div>
                  )}

                  {/* السجل الحالي للبصمة */}
                  {preview.current != null && (
                    <div className="muted" style={{ fontSize: ".87rem" }}>
                      {L("currentRecord")}:{" "}
                      {String((preview.current as Record<string, unknown>).status)}
                      {" · "}
                      <span className="num">
                        {String((preview.current as Record<string, unknown>)
                          .first_in) || "—"}
                      </span>
                      {" → "}
                      <span className="num">
                        {String((preview.current as Record<string, unknown>)
                          .last_out) || "—"}
                      </span>
                    </div>
                  )}
                </>
              )}

              {/* تحذيرات المعاينة */}
              {Array.isArray(preview.warnings) &&
                (preview.warnings as string[]).length > 0 && (
                <div style={{ marginTop: 10, color: "var(--copper)" }}>
                  {(preview.warnings as string[]).map((w, i) => (
                    <div key={i} style={{ fontSize: ".87rem" }}>• {w}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && (
            <div style={{
              marginTop: 12, background: "var(--danger-soft)",
              color: "var(--danger)", padding: "10px 13px",
              borderRadius: "var(--radius-sm)", fontSize: ".9rem",
            }}>
              {error}
            </div>
          )}

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary" style={{ minWidth: 150 }}
              disabled={saving || missing.length > 0} onClick={submit}>
              <IcCheck size={17} />
              {saving ? L("submitting") : L("submit")}
            </button>
            <button className="btn btn-ghost" onClick={() => setSelected(null)}>
              {L("cancel")}
            </button>
            {missing.length > 0 && (
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {L("required")}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

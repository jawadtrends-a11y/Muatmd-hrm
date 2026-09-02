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
import DateField from "@/components/DateField";
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
  first_in: { ar: "وقت الحضور الصحيح", en: "Correct check-in" },
  last_out: { ar: "وقت الانصراف الصحيح", en: "Correct check-out" },
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
import DynField, { fieldKind } from "@/components/RequestFields";

/**
 * هل للمعاينة محتوى يستحق العرض؟
 *
 * بلا هذا الفحص يظهر شريط فارغ حين ترجع المعاينة بلا بيانات —
 * كتصحيح بصمة ليوم لا سجل حضور له ولا طلب سابق عليه.
 */
function hasPreviewContent(p: Record<string, unknown>): boolean {
  if (p.duplicate) return true;
  if (p.charged_days != null) return true;
  if (p.label != null) return true;
  if (p.days != null) return true;
  if (p.notice_days != null) return true;
  if (p.current != null) return true;
  return Array.isArray(p.warnings) && (p.warnings as string[]).length > 0;
}

/* ══ الشاشة ══ */

export default function MyRequestsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { L } = useT(T);

  const [types, setTypes] = useState<ReqType[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<
    { code: string; name_ar: string; requires_attachment?: boolean }[]
  >([]);
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

  /**
   * النوع المختار يُحفظ في الرابط (?type=…) لا في الحالة وحدها.
   *
   * فتحديث الصفحة يبقيك في النموذج، والرابط قابل للمشاركة،
   * وزر الرجوع في المتصفح يعمل كما يتوقع المستخدم.
   */
  const pick = useCallback((t: ReqType) => {
    setSelected(t);
    setValues({});
    setNote("");
    setError("");
    setDone(null);
    router.replace(`/me/requests?type=${t.code}`, { scroll: false });
  }, [router]);

  const clearSelection = useCallback(() => {
    setSelected(null);
    setError("");
    router.replace("/me/requests", { scroll: false });
  }, [router]);

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

      // attachment_url حقل مستقل في Request لا داخل payload —
      // وإرساله داخله يعني أن الخادم لا يراه، فيرفض الطلب طالبًا
      // مرفقًا وهو مرفوع أمام المستخدم
      const attachment = String(payload.attachment_url ?? "");
      delete payload.attachment_url;

      const res = await apiPost<{ request_no: string; warnings: string[] }>(
        "/requests/", {
          request_type: selected.code,
          payload,
          note: note.trim(),
          attachment_url: attachment,
        });

      setDone({ no: res.request_no, warnings: res.warnings || [] });
      setSelected(null);
      router.replace("/me/requests", { scroll: false });
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
            onClick={clearSelection}>
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
            {/* ق-70: المرفق في الإجازات — إلزامي حين يطلبه نوعها
                (المرضية والوضع والخاصة)، اختياري في غيرها.
                والعلم من الخادم لا شرط مكتوب هنا. */}
            {selected.code === "leave" && (
              <DynField name="attachment_url"
                required={!!leaveTypes.find(
                  (t) => t.code === values.leave_type_code,
                )?.requires_attachment}
                value={values.attachment_url ?? ""}
                onChange={(v) => setValues({ ...values, attachment_url: v })}
                leaveTypes={leaveTypes} terminationReasons={reasons} L={L} />
            )}
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
          {preview && !previewing && hasPreviewContent(preview) && (
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
            <button className="btn btn-ghost" onClick={clearSelection}>
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

"use client";

/**
 * إسناد طلب لموظف (ق-68).
 *
 * الموظف ينسى تقديم طلبه فيُخصم منه، أو لا يُحسن استخدام النظام —
 * فيسنده مشرفه نيابةً عنه. والنطاق يحصر الإسناد في الفريق.
 *
 * والنموذج يُبنى من حقول النوع القادمة من الخادم، فإضافة نوع
 * جديد لا تحتاج تعديل هذه الشاشة (ق-9: الإعداد لا الكود).
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcCheck, IcDoc } from "@/components/Icons";
import DynField from "@/components/RequestFields";

const T: Dict = {
  title: { ar: "إسناد طلب", en: "Assign request" },
  hint: {
    ar: "تقدّم الطلب نيابةً عن أحد موظفيك — ويسير في سلسلة اعتماده المعتادة",
    en: "Submit on behalf of a team member — it follows the usual approval chain",
  },
  employee: { ar: "الموظف", en: "Employee" },
  pickEmployee: { ar: "اختر الموظف", en: "Select employee" },
  type: { ar: "نوع الطلب", en: "Request type" },
  pickType: { ar: "اختر النوع", en: "Select type" },
  submit: { ar: "إسناد الطلب", en: "Assign" },
  sending: { ar: "جارٍ الإرسال…", en: "Sending…" },
  done: { ar: "أُسند الطلب", en: "Request assigned" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noEmployees: { ar: "لا مرؤوسين", en: "No team members" },
  optional: { ar: "اختياري", en: "optional" },
};

type Emp = { id: number; employee_no: string; name_ar: string };
type ReqType = {
  code: string;
  name_ar: string;
  hint_ar?: string;
  required_fields: string[];
  optional_fields: string[];
};

export default function AssignRequestPage() {
  const { L, lang } = useT(T);

  const [emps, setEmps] = useState<Emp[]>([]);
  const [empId, setEmpId] = useState<number | null>(null);
  const [types, setTypes] = useState<ReqType[]>([]);
  const [typeCode, setTypeCode] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [leaveTypes, setLeaveTypes] = useState<
    { code: string; name_ar: string; requires_attachment?: boolean }[]
  >([]);
  const [busy, setBusy] = useState(true);
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  // المرؤوسون
  useEffect(() => {
    apiGet<Emp[]>("/employees/")
      .then((r) => { setEmps(r); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });
    apiGet<{ code: string; name_ar: string;
             requires_attachment?: boolean }[]>("/leaves/types/")
      .then(setLeaveTypes)
      .catch(() => setLeaveTypes([]));
  }, []);

  // أنواع الطلبات للموظف المختار — تختلف بالجنسية والمدة والعقد
  const loadTypes = useCallback(async (id: number) => {
    setTypes([]);
    setTypeCode("");
    setValues({});
    try {
      const r = await apiGet<{ types: ReqType[] }>(
        `/me/request-types/${qs({ employment_id: id })}`);
      setTypes(r.types || []);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }, []);

  const active = types.find((t) => t.code === typeCode);
  // ق-70: المرفق إلزامي حين يطلبه نوع الإجازة المختار — المرضية
  // والخاصة (وفاة، ولادة). والعلم من الخادم لا شرط مكتوب هنا،
  // فالشركة تعدّله لأي نوع بلا تعديل كود.
  const pickedLeave = leaveTypes.find(
    (t) => t.code === values.leave_type_code);
  const attachmentRequired = active?.code === "leave"
    && !!pickedLeave?.requires_attachment;

  const fields = active
    ? [...active.required_fields.map((f) => ({ name: f, required: true })),
       ...(active.code === "leave"
         ? [{ name: "attachment_url", required: attachmentRequired }]
         : []),
       ...active.optional_fields
         .filter((f) => f !== "note" && f !== "attachment_url")
         .filter((f) => {
           // وقت البصمة يظهر حسب ما يُصحَّح
           if (active.code !== "attendance_fix") return true;
           const target = values.fix_target || "";
           if (!target) return false;
           if (f === "first_in" && target === "out") return false;
           if (f === "last_out" && target === "in") return false;
           return true;
         })
         .map((f) => ({ name: f, required: false }))]
    : [];

  const ready = active
    && active.required_fields.every((f) => (values[f] || "").trim() !== "")
    && (!attachmentRequired || (values.attachment_url || "") !== "");

  async function send() {
    if (!empId || !active) return;
    setSending(true);
    setToast("");
    try {
      // attachment_url حقل مستقل في Request لا داخل payload
      const { attachment_url: att, ...payload } = values;
      await apiPost("/requests/", {
        employment_id: empId,
        request_type: active.code,
        payload,
        attachment_url: att || "",
      });
      setToast(L("done"));
      setValues({});
      setTypeCode("");
    } catch (e) {
      setToast((e as ApiError).message);
    } finally {
      setSending(false);
      setTimeout(() => setToast(""), 4000);
    }
  }

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("hint")}
          </div>
        </div>
        {toast && <span className="badge badge-teal">{toast}</span>}
      </div>

      {busy ? (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
          {L("loading")}
        </div>
      ) : error ? (
        <div className="card" style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
          {error}
        </div>
      ) : emps.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
          <IcDoc size={22} />
          <div style={{ marginTop: 8 }}>{L("noEmployees")}</div>
        </div>
      ) : (
        <div className="card" style={{ padding: 22, maxWidth: 620 }}>
          <div className="stack" style={{ gap: 14 }}>
            <div className="field">
              <label className="label">{L("employee")}</label>
              <select className="select" value={empId ?? ""}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  setEmpId(id || null);
                  if (id) loadTypes(id);
                }}>
                <option value="">{L("pickEmployee")}</option>
                {emps.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.employee_no} — {e.name_ar}
                  </option>
                ))}
              </select>
            </div>

            {types.length > 0 && (
              <div className="field">
                <label className="label">{L("type")}</label>
                <select className="select" value={typeCode}
                  onChange={(e) => { setTypeCode(e.target.value); setValues({}); }}>
                  <option value="">{L("pickType")}</option>
                  {types.map((t) => (
                    <option key={t.code} value={t.code}>{t.name_ar}</option>
                  ))}
                </select>
              </div>
            )}

            {active?.hint_ar && (
              <div className="muted" style={{
                fontSize: ".86rem", padding: "9px 11px",
                background: "var(--paper-2)", borderRadius: "var(--radius-sm)",
              }}>
                {active.hint_ar}
              </div>
            )}

            {/* الحقول تُرسم بالمكوّن المشترك — فترث التقويم العربي
                وقوائم أنواع الإجازات وأزرار «ما يُصحَّح» */}
            <div className="row" style={{
              flexWrap: "wrap", alignItems: "flex-start",
            }}>
              {fields.map(({ name, required }) => (
                <DynField key={name} name={name} required={required}
                  value={values[name] ?? ""}
                  onChange={(v) => setValues((old) => ({ ...old, [name]: v }))}
                  leaveTypes={leaveTypes} terminationReasons={[]} L={L} />
              ))}
            </div>

            {active && (
              <div className="row" style={{ marginTop: 4 }}>
                <button className="btn btn-primary" disabled={!ready || sending}
                  onClick={send}>
                  <IcCheck size={17} />
                  {sending ? L("sending") : L("submit")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";
/**
 * إصدار خطاب لموظف (ق-193).
 *
 * ⚠️⚠️ **والمساران كانا مبنيَّين بلا شاشة** — كشفهما الجرد:
 * الإصدار والمعاينة.
 *
 * ⚠️ **والمعاينة قبل الإصدار**: فمن يُصدر **يرى نتيجته لا نصًّا
 * بمتغيّرات** — والخطاب **يُجمَّد نصُّه** عند الإصدار برقمٍ
 * متسلسل.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import EmployeePicker, { type PickedEmployee }
  from "@/components/EmployeePicker";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "إصدار خطاب", en: "Issue a letter" },
  sub: {
    ar: "اختر القالب والموظف — وعاين قبل الإصدار",
    en: "Pick a template and preview before issuing",
  },
  template: { ar: "القالب", en: "Template" },
  pickTemplate: { ar: "اختر القالب", en: "Select template" },
  employee: { ar: "الموظف", en: "Employee" },
  addressee: { ar: "موجّه إلى", en: "Addressee" },
  addresseeHint: {
    ar: "اتركه فارغًا ليُستعمل ما في القالب",
    en: "Empty uses the template default",
  },
  includeSalary: { ar: "إظهار الراتب", en: "Include salary" },
  salaryHint: {
    ar: "⚠️ متغيّرٌ حسّاس — لا يظهر إلا بطلب صاحبه",
    en: "Sensitive — only on request",
  },
  preview: { ar: "معاينة", en: "Preview" },
  issue: { ar: "إصدار الخطاب", en: "Issue" },
  issued: { ar: "صدر الخطاب برقم", en: "Issued as" },
  validUntil: { ar: "صالح حتى", en: "Valid until" },
  view: { ar: "عرض", en: "View" },
  needed: { ar: "اختر القالب والموظف", en: "Pick both first" },
  noTemplates: {
    ar: "لا قوالب — أضفها من الإعدادات ← قوالب الخطابات",
    en: "No templates yet",
  },
  previewTitle: { ar: "المعاينة", en: "Preview" },
  frozen: {
    ar: "⚠️ نصّ الخطاب يُجمَّد عند الإصدار — وتعديل القالب لاحقًا لا يغيّره",
    en: "The text is frozen when issued",
  },
};

type Tpl = {
  id: number; code: string; name_ar: string;
  includes_salary: boolean; is_active: boolean;
};
type Preview = { heading_ar: string; body_ar: string };
type Issued = {
  id: number; letter_no: string; issued_on: string;
  valid_until: string | null;
};

export default function IssueLetterPage() {
  const { L } = useT(T);
  const [tpls, setTpls] = useState<Tpl[]>([]);
  const [tplId, setTplId] = useState("");
  const [emp, setEmp] = useState<PickedEmployee | null>(null);
  const [addressee, setAddressee] = useState("");
  const [withSalary, setWithSalary] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const [shown, setShown] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiGet<{ templates: Tpl[] }>("/letters/templates/")
      .then((d) => setTpls((d.templates || []).filter((t) => t.is_active)))
      .catch(() => setTpls([]));
  }, []);

  // ⚠️ **وتغيّر المدخلات يمسح المعاينة والنتيجة**: فمعاينةٌ قديمة
  // **يُصدَر عليها خطابٌ خاطئ**.
  useEffect(() => {
    setPreview(null);
    setIssued(null);
    setShown(null);
  }, [tplId, emp, addressee, withSalary]);

  const tpl = tpls.find((t) => String(t.id) === tplId) || null;

  const body = () => ({
    employment_id: emp?.id,
    addressee: addressee.trim(),
    include_salary: withSalary,
  });

  const showIssued = async (id: number) => {
    try {
      const d = await apiGet<Preview>(`/letters/${id}/`);
      setShown(d);
      setPreview(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };

  const doPreview = async () => {
    if (!tplId || !emp) { setErr(L("needed")); return; }
    setBusy(true);
    setErr("");
    try {
      setPreview(await apiPost<Preview>(
        `/letters/templates/${tplId}/preview/`, body()));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const doIssue = async () => {
    if (!tplId || !emp) { setErr(L("needed")); return; }
    setBusy(true);
    setErr("");
    try {
      setIssued(await apiPost<Issued>("/letters/issue/", {
        template_id: Number(tplId), ...body(),
      }));
      setPreview(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem",
                                        marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
        </div>
      )}

      {issued && (
        <div className="card" style={{ borderColor: "var(--ok)",
                                       padding: 16 }}>
          <div className="spread">
            <div>
              <IcCheck size={17} /> {L("issued")}{" "}
              <span className="num">{issued.letter_no}</span>
              {issued.valid_until && (
                <div className="muted num" style={{ fontSize: ".8rem",
                                                    marginTop: 3 }}>
                  {L("validUntil")} {issued.valid_until}
                </div>
              )}
            </div>
            {/* ⚠️ **والنصّ يُقرأ من المسار** — فلا مسارَ PDF
                للخطاب بعد */}
            <button className="btn btn-sm"
                    onClick={() => showIssued(issued.id)}>
              {L("view")}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 20 }}>
        {tpls.length === 0 ? (
          <div className="muted" style={{ fontSize: ".88rem",
                                          lineHeight: 1.9 }}>
            <IcDoc size={18} /> {L("noTemplates")}
          </div>
        ) : (
          <>
            <div style={{ display: "grid", gap: 14,
                          gridTemplateColumns:
                            "repeat(auto-fit, minmax(220px, 1fr))" }}>
              <label className="field">
                <span className="label">{L("template")}</span>
                <select className="select" value={tplId}
                        onChange={(e) => setTplId(e.target.value)}>
                  <option value="">{L("pickTemplate")}</option>
                  {tpls.map((t) => (
                    <option key={t.id} value={t.id}>{t.name_ar}</option>
                  ))}
                </select>
              </label>

              <div className="field">
                <label className="label">{L("employee")}</label>
                <EmployeePicker value={emp} onChange={setEmp} />
              </div>

              <label className="field">
                <span className="label">{L("addressee")}</span>
                <input className="input" value={addressee}
                       onChange={(e) => setAddressee(e.target.value)} />
                <span className="muted" style={{ fontSize: ".76rem" }}>
                  {L("addresseeHint")}
                </span>
              </label>
            </div>

            {/* ⚠️ **والراتب لا يظهر إلا إن سمح القالب وطلبه
                صاحبه** (ق-65) */}
            {tpl?.includes_salary && (
              <label className="row" style={{ gap: 8, marginTop: 14,
                                              cursor: "pointer",
                                              alignItems: "flex-start" }}>
                <input type="checkbox" checked={withSalary}
                       style={{ marginTop: 3 }}
                       onChange={(e) => setWithSalary(e.target.checked)} />
                <span>
                  {L("includeSalary")}
                  <div className="muted" style={{ fontSize: ".78rem" }}>
                    {L("salaryHint")}
                  </div>
                </span>
              </label>
            )}

            <div className="row" style={{ gap: 8, marginTop: 18 }}>
              <button className="btn" disabled={busy || !tplId || !emp}
                      onClick={doPreview}>
                {busy ? "…" : L("preview")}
              </button>
              <button className="btn btn-primary"
                      disabled={busy || !tplId || !emp}
                      onClick={doIssue}>
                <IcDoc size={16} /> {L("issue")}
              </button>
            </div>
          </>
        )}
      </div>

      {(preview || shown) && (
        <>
          {preview && (
          <div style={{ background: "var(--copper-soft)",
                        color: "var(--copper)", padding: "10px 13px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".83rem", lineHeight: 1.9 }}>
            {L("frozen")}
          </div>
          )}

          <div className="card" style={{ padding: 28 }}>
            <h3 style={{ margin: "0 0 18px", textAlign: "center" }}>
              {(preview || shown)!.heading_ar}
            </h3>
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 2.2,
                          fontSize: ".95rem" }}>
              {(preview || shown)!.body_ar}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

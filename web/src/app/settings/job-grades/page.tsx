"use client";

/**
 * السلّم الوظيفي — المراتب ودرجاتها (ق-63).
 *
 * اختياري: تملؤه الشركة إن كانت تستخدم سلّمًا، وتتركه فارغًا إن
 * لم تكن. فالنظام لا يفرض بنية لا تحتاجها.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcOrg, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  nameEn: { ar: "الاسم بالإنجليزية", en: "Name (English)" },
  title: { ar: "السلّم الوظيفي", en: "Job scale" },
  subtitle: {
    ar: "المراتب ودرجاتها ونطاق رواتبها — اختياري",
    en: "Grades, steps and salary ranges — optional",
  },
  add: { ar: "مرتبة جديدة", en: "New grade" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "الاسم", en: "Name" },
  level: { ar: "المستوى", en: "Level" },
  minSalary: { ar: "أدنى راتب", en: "Min salary" },
  maxSalary: { ar: "أعلى راتب", en: "Max salary" },
  steps: { ar: "الدرجات", en: "Steps" },
  stepNo: { ar: "رقم الدرجة", en: "Step no." },
  salary: { ar: "الراتب", en: "Salary" },
  addStep: { ar: "أضف درجة", en: "Add step" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  show: { ar: "عرض الدرجات", en: "Show steps" },
  hide: { ar: "إخفاء", en: "Hide" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: {
    ar: "لا مراتب — أضف مرتبة إن كانت شركتك تستخدم سلّمًا وظيفيًا",
    en: "No grades — add one if your company uses a job scale",
  },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  active: { ar: "نشطة", en: "Active" },
  inactive: { ar: "معطّلة", en: "Inactive" },
  confirmDel: {
    ar: "حذف المرتبة؟ إن كانت مستخدمة في عقود فستُعطَّل بدل حذفها.",
    en: "Delete? If used in contracts it is deactivated instead.",
  },
  confirmDelStep: {
    ar: "حذف هذه الدرجة؟",
    en: "Delete this step?",
  },
  noSteps: { ar: "لا درجات في هذه المرتبة", en: "No steps yet" },
};

type Step = {
  id: number;
  code: string;
  name_ar: string;
  name_en?: string;
  step_number: number;
  salary: string | null;
};

type Grade = {
  id: number;
  code: string;
  name_ar: string;
  name_en?: string;
  level: number;
  min_salary: string | null;
  max_salary: string | null;
  is_active: boolean;
  steps: Step[];
};

export default function JobGradesPage() {
  const { L, lang } = useT(T);
  const [rows, setRows] = useState<Grade[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [open, setOpen] = useState<number | null>(null);
  const [stepDraft, setStepDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);
  const [askStep, setAskStep] = useState<{
    grade: number; step: number;
  } | null>(null);

  const load = useCallback(() => {
    apiGet<Grade[]>("/job-grades/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("employees.edit")))
      .catch(() => setCanEdit(false));
  }, []);

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (adding) await apiPost("/job-grades/", draft);
      else await apiPut(`/job-grades/${editing}/`, draft);
      setAdding(false);
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    try {
      const r = await apiDelete<{ deactivated?: boolean; detail?: string }>(
        `/job-grades/${id}/`);
      if (r?.deactivated && r.detail) {
        setMsg(r.detail);
        setTimeout(() => setMsg(""), 6000);
      }
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  async function addStep(gradeId: number) {
    setErr("");
    try {
      await apiPost(`/job-grades/${gradeId}/steps/`, stepDraft);
      setStepDraft({});
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  async function removeStep(gradeId: number, stepId: number) {
    try {
      await apiDelete(`/job-grades/${gradeId}/steps/?step_id=${stepId}`);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    }
  }

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <ConfirmDialog
        open={askDel !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDel")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const id = askDel;
          setAskDel(null);
          if (id !== null) remove(id);
        }}
      />
      <ConfirmDialog
        open={askStep !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDelStep")}
        onCancel={() => setAskStep(null)}
        onConfirm={() => {
          const a = askStep;
          setAskStep(null);
          if (a) removeStep(a.grade, a.step);
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && !adding && editing === null && (
          <button className="btn btn-primary" onClick={() => {
            setDraft({ code: "", name_ar: "", level: 0 });
            setAdding(true);
          }}>
            <IcPlus size={17} />
            {L("add")}
          </button>
        )}
      </div>

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}
      {msg && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {msg}
        </div>
      )}

      {(adding || editing !== null) && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("code")}
                disabled={!adding}
                onChange={(e) => set("code", e.target.value.toUpperCase())} />
            </div>
            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("nameEn")}</label>
              <input className="input" value={f("name_en")}
                onChange={(e) => set("name_en", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("level")}</label>
              <input className="input num" value={f("level")}
                onChange={(e) => set("level", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("minSalary")}</label>
              <input className="input num" value={f("min_salary")}
                onChange={(e) => set("min_salary", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("maxSalary")}</label>
              <input className="input num" value={f("max_salary")}
                onChange={(e) => set("max_salary", e.target.value)} />
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" disabled={saving}
              onClick={save}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => {
                setAdding(false); setEditing(null); setErr("");
              }}>
              <IcX size={16} />
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : rows.length === 0 ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          <IcOrg size={22} />
          <div style={{ marginTop: 8 }}>{L("empty")}</div>
        </div>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {rows.map((g) => (
            <div key={g.id} className="card"
              style={{ opacity: g.is_active ? 1 : .6 }}>
              <div className="spread" style={{ padding: "14px 18px" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    <span className="num">{g.code}</span>
                    {" — "}{(lang === "en" ? g.name_en : g.name_ar) || g.name_ar}
                  </div>
                  <div className="muted" style={{
                    fontSize: ".8rem", marginTop: 3,
                  }}>
                    {L("level")} {g.level}
                    {g.min_salary && (
                      <> · <span className="num">
                        {g.min_salary} — {g.max_salary || "…"}
                      </span></>
                    )}
                    {" · "}{g.steps.length} {L("steps")}
                  </div>
                </div>

                <div className="row" style={{ gap: 8 }}>
                  <button className="btn btn-sm btn-ghost"
                    onClick={() =>
                      setOpen(open === g.id ? null : g.id)}>
                    {open === g.id ? L("hide") : L("show")}
                  </button>
                  <span className={g.is_active
                    ? "badge badge-ok" : "badge"}>
                    {g.is_active ? L("active") : L("inactive")}
                  </span>
                  {canEdit && (
                    <>
                      <button className="btn btn-sm btn-ghost"
                        onClick={() => {
                          setDraft({ ...g });
                          setEditing(g.id);
                          setAdding(false);
                        }}>
                        {L("edit")}
                      </button>
                      <button className="btn btn-sm btn-ghost"
                        style={{ color: "var(--danger)" }}
                        onClick={() => setAskDel(g.id)}>
                        {L("del")}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {open === g.id && (
                <div style={{
                  borderTop: "1px solid var(--line)",
                  padding: "12px 18px",
                }}>
                  {g.steps.length === 0 ? (
                    <div className="muted" style={{ fontSize: ".85rem" }}>
                      {L("noSteps")}
                    </div>
                  ) : (
                    g.steps.map((s) => (
                      <div key={s.id} className="spread" style={{
                        padding: "7px 0",
                        borderBottom: "1px solid var(--line)",
                      }}>
                        <div style={{ fontSize: ".88rem" }}>
                          <span className="num">{s.step_number}</span>
                          {" · "}{(lang === "en" ? s.name_en : s.name_ar) || s.name_ar}
                        </div>
                        <div className="row" style={{ gap: 8 }}>
                          {s.salary && (
                            <span className="num">{s.salary}</span>
                          )}
                          {canEdit && (
                            <button className="btn btn-sm btn-ghost"
                              style={{ color: "var(--danger)" }}
                              onClick={() => setAskStep({
                                grade: g.id, step: s.id,
                              })}>
                              {L("del")}
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}

                  {canEdit && (
                    <div className="row" style={{
                      gap: 8, paddingTop: 12, flexWrap: "wrap",
                    }}>
                      <input className="input" placeholder={L("code")}
                        style={{ maxWidth: 110 }}
                        value={String(stepDraft.code ?? "")}
                        onChange={(e) => setStepDraft((d) => ({
                          ...d, code: e.target.value.toUpperCase(),
                        }))} />
                      <input className="input" placeholder={L("name")}
                        style={{ maxWidth: 180 }}
                        value={String(stepDraft.name_ar ?? "")}
                        onChange={(e) => setStepDraft((d) => ({
                          ...d, name_ar: e.target.value,
                        }))} />
                      <input className="input num"
                        placeholder={L("stepNo")}
                        style={{ maxWidth: 110 }}
                        value={String(stepDraft.step_number ?? "")}
                        onChange={(e) => setStepDraft((d) => ({
                          ...d, step_number: e.target.value,
                        }))} />
                      <input className="input num"
                        placeholder={L("salary")}
                        style={{ maxWidth: 130 }}
                        value={String(stepDraft.salary ?? "")}
                        onChange={(e) => setStepDraft((d) => ({
                          ...d, salary: e.target.value,
                        }))} />
                      <button className="btn btn-sm btn-primary"
                        onClick={() => addStep(g.id)}>
                        {L("addStep")}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

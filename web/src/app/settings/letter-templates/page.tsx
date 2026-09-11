"use client";
/**
 * قوالب الخطابات (ق-128).
 *
 * **الشركة تكتب قوالبها** — بمتغيّرات تُدرَج بضغطة، ومعاينةٍ
 * ببيانات موظفٍ حقيقيّ قبل الاعتماد.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "قوالب الخطابات", en: "Letter templates" },
  sub: {
    ar: "اكتب قوالبك بمتغيّراتها — وتُملأ ببيانات الموظف عند الإصدار",
    en: "Write templates with variables — filled at issue time",
  },
  add: { ar: "قالب جديد", en: "New template" },
  name: { ar: "اسم القالب", en: "Name" },
  code: { ar: "الرمز", en: "Code" },
  issued: { ar: "صدر منه", en: "Issued" },
  validity: { ar: "الصلاحية", en: "Validity" },
  days: { ar: "يومًا", en: "days" },
  salary: { ar: "يتضمّن الراتب", en: "Includes salary" },
  active: { ar: "مفعّل", en: "Active" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: {
    ar: "قوالب الخطابات غير متاحة في باقتكم",
    en: "Letter templates not in your plan",
  },
  empty: { ar: "لم تكتب قالبًا بعد", en: "No templates yet" },
  heading: { ar: "عنوان الخطاب", en: "Heading" },
  addressee: { ar: "موجّه إلى", en: "Addressed to" },
  addresseeHint: {
    ar: "اتركه فارغًا ليكتبه الطالب — أو «من يهمّه الأمر»",
    en: "Leave empty for the requester to fill",
  },
  body: { ar: "نصّ الخطاب", en: "Body" },
  vars: { ar: "المتغيّرات", en: "Variables" },
  varsHint: {
    ar: "اضغط المتغيّر لإدراجه في موضع المؤشّر",
    en: "Click to insert at cursor",
  },
  salaryVar: { ar: "يحتاج إذن الراتب", en: "Needs salary consent" },
  salaryHint: {
    ar: "لا يُطبع الراتب إلا إن أذن القالب وطلبه صاحبه معًا",
    en: "Printed only if both the template and the employee allow",
  },
  newTitle: { ar: "قالب جديد", en: "New template" },
  savedOk: { ar: "حُفظ القالب", en: "Template saved" },
};

type Tpl = {
  id: number; code: string; name_ar: string; heading_ar: string;
  addressee_ar: string; body_ar: string; includes_salary: boolean;
  valid_days: number; is_active: boolean; issued_count: number;
};
type Variable = { key: string; label_ar: string; salary: boolean };

export default function LetterTemplatesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Tpl[]>([]);
  const [vars, setVars] = useState<Variable[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Tpl | null>(null);
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ templates: Tpl[]; variables: Variable[] }>(
        "/letters/templates/");
      setRows(d.templates);
      setVars(d.variables);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (t: Tpl) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ deactivated?: boolean; detail?: string }>(
        `/letters/templates/${t.id}/`);
      if (out?.deactivated) setMsg(out.detail || "");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  if (denied) return (
    <div className="card" style={{ padding: 36, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      <IcAlert size={22} />
      <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
    </div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        <button className="btn btn-primary btn-sm"
                onClick={() => setAdding(true)}>{L("add")}</button>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{L("name")}</th>
                <th style={{ width: 110 }}>{L("validity")}</th>
                <th style={{ width: 100 }}>{L("issued")}</th>
                <th style={{ width: 160 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} style={{ opacity: t.is_active ? 1 : 0.55 }}>
                  <td>
                    <div style={{ fontWeight: 500 }}>
                      {t.name_ar}
                      {t.includes_salary && (
                        <span className="badge badge-warn"
                              style={{ marginInlineStart: 6,
                                       fontSize: ".7rem" }}>
                          {L("salary")}
                        </span>
                      )}
                    </div>
                    <div className="muted num" style={{ fontSize: ".76rem" }}>
                      {t.code}
                    </div>
                  </td>
                  <td>
                    <span className="num">{t.valid_days}</span> {L("days")}
                  </td>
                  <td><span className="num">{t.issued_count}</span></td>
                  <td>
                    <div className="row" style={{ gap: 5 }}>
                      <button className="btn btn-sm"
                              onClick={() => { setEditing(t); setErr(""); }}>
                        {L("edit")}
                      </button>
                      <button className="btn btn-sm btn-danger"
                              disabled={acting} onClick={() => remove(t)}>
                        {L("del")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {(editing || adding) && (
        <TplDialog tpl={editing} vars={vars} L={L}
                   onClose={() => { setEditing(null); setAdding(false); }}
                   onSaved={async () => {
                     setEditing(null); setAdding(false);
                     setMsg(L("savedOk"));
                     setTimeout(() => setMsg(""), 3000);
                     await load();
                   }} />
      )}
    </div>
  );
}


/* ══ نافذة القالب ══ */

function TplDialog({ tpl, vars, L, onClose, onSaved }: {
  tpl: Tpl | null;
  vars: Variable[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: tpl?.code || "",
    name_ar: tpl?.name_ar || "",
    heading_ar: tpl?.heading_ar || "",
    addressee_ar: tpl?.addressee_ar || "",
    body_ar: tpl?.body_ar || "",
    includes_salary: tpl?.includes_salary ?? false,
    valid_days: String(tpl?.valid_days ?? 30),
    is_active: tpl?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  const insert = (key: string) => {
    const el = bodyRef.current;
    const token = `{{${key}}}`;
    if (!el) { setF({ ...f, body_ar: f.body_ar + token }); return; }
    const start = el.selectionStart ?? f.body_ar.length;
    const end = el.selectionEnd ?? start;
    const next = f.body_ar.slice(0, start) + token + f.body_ar.slice(end);
    setF({ ...f, body_ar: next });
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = { ...f, valid_days: Number(f.valid_days) || 30 };
      if (tpl) await apiPut(`/letters/templates/${tpl.id}/`, body);
      else await apiPost("/letters/templates/", body);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 680,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{tpl ? tpl.name_ar : L("newTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="row" style={{ gap: 12, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {!tpl && (
            <label className="field" style={{ minWidth: 150 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={f.code}
                     onChange={(e) => setF({ ...f,
                       code: e.target.value.trim().toUpperCase() })} />
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 180 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
          <label className="field" style={{ width: 130 }}>
            <span className="label">{L("validity")}</span>
            <input className="input num" type="number" min={0}
                   value={f.valid_days}
                   onChange={(e) => setF({ ...f,
                     valid_days: e.target.value })} />
          </label>
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("heading")}</span>
          <input className="input" value={f.heading_ar}
                 onChange={(e) => setF({ ...f,
                   heading_ar: e.target.value })} />
        </label>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("addressee")}</span>
          <input className="input" value={f.addressee_ar}
                 onChange={(e) => setF({ ...f,
                   addressee_ar: e.target.value })} />
          <span className="muted" style={{ fontSize: ".78rem" }}>
            {L("addresseeHint")}
          </span>
        </label>

        <div style={{ marginTop: 16 }}>
          <div className="spread">
            <span className="label">{L("vars")}</span>
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("varsHint")}
            </span>
          </div>
          <div className="row" style={{ gap: 5, flexWrap: "wrap",
                                        marginTop: 6 }}>
            {vars.map((v) => (
              <button key={v.key} type="button"
                      className="btn btn-sm btn-ghost"
                      title={v.salary ? L("salaryVar") : v.label_ar}
                      style={v.salary
                        ? { borderColor: "var(--copper)",
                            color: "var(--copper)" } : undefined}
                      onClick={() => insert(v.key)}>
                {v.label_ar}
              </button>
            ))}
          </div>
        </div>

        <label className="field" style={{ marginTop: 14 }}>
          <span className="label">{L("body")}</span>
          <textarea className="input" rows={9} ref={bodyRef}
                    value={f.body_ar}
                    onChange={(e) => setF({ ...f,
                      body_ar: e.target.value })} />
        </label>

        <label className="row" style={{ gap: 8, marginTop: 12,
                                        cursor: "pointer",
                                        alignItems: "flex-start" }}>
          <input type="checkbox" checked={f.includes_salary}
                 style={{ marginTop: 3 }}
                 onChange={(e) => setF({ ...f,
                   includes_salary: e.target.checked })} />
          <span>
            {L("salary")}
            <div className="muted" style={{ fontSize: ".78rem" }}>
              {L("salaryHint")}
            </div>
          </span>
        </label>

        <label className="row" style={{ gap: 8, marginTop: 8,
                                        cursor: "pointer" }}>
          <input type="checkbox" checked={f.is_active}
                 onChange={(e) => setF({ ...f,
                   is_active: e.target.checked })} />
          <span>{L("active")}</span>
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim() || !f.body_ar.trim()
                            || (!tpl && !f.code)}
                  onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

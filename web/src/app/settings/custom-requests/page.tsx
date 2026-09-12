"use client";
/**
 * أنواع الطلبات المخصّصة (ق-142).
 *
 * **الشركة تُنشئ نوع طلبٍ بحقوله** — فلا تنتظر منّا نوعًا لكل
 * حاجة.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الطلبات المخصّصة", en: "Custom requests" },
  sub: {
    ar: "أنشئ نوع طلبٍ بحقوله — ولا تنتظر منّا نوعًا لكل حاجة",
    en: "Create request types with their own fields",
  },
  add: { ar: "نوع جديد", en: "New type" },
  name: { ar: "اسم الطلب", en: "Name" },
  code: { ar: "الرمز", en: "Code" },
  fields: { ar: "الحقول", en: "Fields" },
  manageFields: { ar: "الحقول", en: "Fields" },
  hint: { ar: "التوضيح", en: "Hint" },
  needsAttach: { ar: "يلزمه مرفق", en: "Needs attachment" },
  dailyUnique: { ar: "مرّة في اليوم", en: "Once per day" },
  dailyHint: {
    ar: "يمنع طلبين في يومٍ واحد — ويحتاج حقل تاريخ بمفتاح work_date",
    en: "Blocks two per day — needs a work_date field",
  },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  close: { ar: "إغلاق", en: "Close" },
  empty: { ar: "لا أنواع مخصّصة بعد", en: "No custom types yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "الطلبات المخصّصة غير متاحة في باقتكم",
              en: "Not in your plan" },
  newTitle: { ar: "نوع طلب جديد", en: "New request type" },
  fieldKey: { ar: "المفتاح", en: "Key" },
  keyHint: {
    ar: "بالإنجليزية الصغيرة — يُقرأ برمجيًّا لا يُعرض",
    en: "Lowercase English — read by code, not shown",
  },
  label: { ar: "التسمية", en: "Label" },
  kind: { ar: "نوع الحقل", en: "Field kind" },
  required: { ar: "إلزاميّ", en: "Required" },
  options: { ar: "الخيارات", en: "Options" },
  optionsHint: {
    ar: "مفصولةٌ بفواصل — للاختيار من قائمة",
    en: "Comma-separated — for select fields",
  },
  addField: { ar: "إضافة حقل", en: "Add field" },
  noFields: { ar: "لا حقول — أضف واحدًا", en: "No fields yet" },
  savedOk: { ar: "حُفظ", en: "Saved" },
};

type Field = {
  id: number; key: string; label_ar: string; kind: string;
  kind_label: string; is_required: boolean; options: string[];
};
type CType = {
  id: number; code: string; name_ar: string; hint_ar: string;
  requires_attachment: boolean; daily_unique: boolean;
  is_active: boolean; field_count: number; fields: Field[];
};
type Kind = { value: string; label: string };

export default function CustomRequestsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<CType[]>([]);
  const [kinds, setKinds] = useState<Kind[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<CType | null>(null);
  const [fieldsOf, setFieldsOf] = useState<CType | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ types: CType[]; kinds: Kind[] }>(
        "/custom-request-types/");
      setRows(d.types);
      setKinds(d.kinds);
      setFieldsOf((cur) =>
        cur ? d.types.find((t) => t.id === cur.id) || null : null);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (t: CType) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ deactivated?: boolean;
                                    detail?: string }>(
        `/custom-request-types/${t.id}/`);
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
                <th style={{ width: 100 }}>{L("fields")}</th>
                <th style={{ width: 160 }} />
                <th style={{ width: 160 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} style={{ opacity: t.is_active ? 1 : .55 }}>
                  <td>
                    <div style={{ fontWeight: 500 }}>
                      {t.name_ar}
                      {t.daily_unique && (
                        <span className="badge"
                              style={{ marginInlineStart: 6,
                                       fontSize: ".68rem" }}>
                          {L("dailyUnique")}
                        </span>
                      )}
                      {t.requires_attachment && (
                        <span className="badge badge-warn"
                              style={{ marginInlineStart: 4,
                                       fontSize: ".68rem" }}>
                          {L("needsAttach")}
                        </span>
                      )}
                    </div>
                    <div className="muted num"
                         style={{ fontSize: ".75rem" }}>{t.code}</div>
                  </td>
                  <td><span className="num">{t.field_count}</span></td>
                  <td>
                    <button className="btn btn-sm"
                            onClick={() => setFieldsOf(t)}>
                      {L("manageFields")}
                    </button>
                  </td>
                  <td>
                    <div className="row" style={{ gap: 5 }}>
                      <button className="btn btn-sm"
                              onClick={() => { setEditing(t);
                                               setErr(""); }}>
                        {L("edit")}
                      </button>
                      <button className="btn btn-sm btn-danger"
                              disabled={acting}
                              onClick={() => remove(t)}>{L("del")}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {(adding || editing) && (
        <TypeDialog t={editing} L={L}
                    onClose={() => { setAdding(false);
                                     setEditing(null); }}
                    onSaved={async () => {
                      setAdding(false); setEditing(null);
                      setMsg(L("savedOk"));
                      setTimeout(() => setMsg(""), 3000);
                      await load();
                    }} />
      )}

      {fieldsOf && (
        <FieldsDialog t={fieldsOf} kinds={kinds} L={L}
                      onClose={() => setFieldsOf(null)}
                      onChanged={load} />
      )}
    </div>
  );
}


function TypeDialog({ t, L, onClose, onSaved }: {
  t: CType | null;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: t?.code || "", name_ar: t?.name_ar || "",
    hint_ar: t?.hint_ar || "",
    requires_attachment: t?.requires_attachment ?? false,
    daily_unique: t?.daily_unique ?? false,
    is_active: t?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      if (t) await apiPut(`/custom-request-types/${t.id}/`, f);
      else await apiPost("/custom-request-types/", f);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{t ? t.name_ar : L("newTitle")}</h3>

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
          {!t && (
            <label className="field" style={{ width: 130 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={f.code}
                     onChange={(e) => setF({ ...f,
                       code: e.target.value.trim().toUpperCase() })} />
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 170 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("hint")}</span>
          <input className="input" value={f.hint_ar}
                 onChange={(e) => setF({ ...f,
                   hint_ar: e.target.value })} />
        </label>

        <label className="row" style={{ gap: 8, marginTop: 14,
                                        cursor: "pointer" }}>
          <input type="checkbox" checked={f.requires_attachment}
                 onChange={(e) => setF({ ...f,
                   requires_attachment: e.target.checked })} />
          <span>{L("needsAttach")}</span>
        </label>

        <label className="row" style={{ gap: 8, marginTop: 10,
                                        cursor: "pointer",
                                        alignItems: "flex-start" }}>
          <input type="checkbox" checked={f.daily_unique}
                 style={{ marginTop: 3 }}
                 onChange={(e) => setF({ ...f,
                   daily_unique: e.target.checked })} />
          <span>
            {L("dailyUnique")}
            <div className="muted" style={{ fontSize: ".78rem" }}>
              {L("dailyHint")}
            </div>
          </span>
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim() || (!t && !f.code)}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


function FieldsDialog({ t, kinds, L, onClose, onChanged }: {
  t: CType;
  kinds: Kind[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [f, setF] = useState({
    key: "", label_ar: "", kind: "text", is_required: true, options: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const add = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/custom-request-types/${t.id}/fields/`, f);
      setF({ key: "", label_ar: "", kind: "text",
             is_required: true, options: "" });
      await onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const drop = async (id: number) => {
    try {
      await apiDelete(`/custom-request-types/${t.id}/fields/`,
                      { field_id: id });
      await onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 620,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{t.name_ar} — {L("fields")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="card" style={{ padding: 14, marginTop: 16,
                                       background: "var(--paper-2)" }}>
          <div className="row" style={{ gap: 10, flexWrap: "wrap",
                                        alignItems: "flex-end" }}>
            <label className="field" style={{ width: 150 }}>
              <span className="label">{L("fieldKey")}</span>
              <input className="input" dir="ltr" value={f.key}
                     onChange={(e) => setF({ ...f,
                       key: e.target.value.trim().toLowerCase() })} />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 150 }}>
              <span className="label">{L("label")}</span>
              <input className="input" value={f.label_ar}
                     onChange={(e) => setF({ ...f,
                       label_ar: e.target.value })} />
            </label>
            <label className="field" style={{ width: 150 }}>
              <span className="label">{L("kind")}</span>
              <select className="select" value={f.kind}
                      onChange={(e) => setF({ ...f,
                        kind: e.target.value })}>
                {kinds.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </select>
            </label>
          </div>

          {f.kind === "select" && (
            <label className="field" style={{ marginTop: 10 }}>
              <span className="label">{L("options")}</span>
              <input className="input" value={f.options}
                     onChange={(e) => setF({ ...f,
                       options: e.target.value })} />
              <span className="muted" style={{ fontSize: ".78rem" }}>
                {L("optionsHint")}
              </span>
            </label>
          )}

          <div className="row" style={{ gap: 12, marginTop: 12,
                                        alignItems: "center" }}>
            <label className="row" style={{ gap: 7, cursor: "pointer" }}>
              <input type="checkbox" checked={f.is_required}
                     onChange={(e) => setF({ ...f,
                       is_required: e.target.checked })} />
              <span style={{ fontSize: ".86rem" }}>{L("required")}</span>
            </label>
            <button className="btn btn-sm btn-primary"
                    disabled={busy || !f.key || !f.label_ar}
                    onClick={add}>+ {L("addField")}</button>
            <span className="muted" style={{ fontSize: ".76rem" }}>
              {L("keyHint")}
            </span>
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          {t.fields.length === 0 ? (
            <div className="muted" style={{ padding: "18px 0",
                                            textAlign: "center" }}>
              {L("noFields")}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 150 }}>{L("fieldKey")}</th>
                  <th>{L("label")}</th>
                  <th style={{ width: 130 }}>{L("kind")}</th>
                  <th style={{ width: 70 }} />
                </tr>
              </thead>
              <tbody>
                {t.fields.map((fl) => (
                  <tr key={fl.id}>
                    <td>
                      <span className="num"
                            style={{ fontSize: ".8rem" }}>{fl.key}</span>
                    </td>
                    <td>
                      {fl.label_ar}
                      {fl.is_required && (
                        <span style={{ color: "var(--danger)" }}> *</span>
                      )}
                      {fl.options.length > 0 && (
                        <div className="muted"
                             style={{ fontSize: ".74rem" }}>
                          {fl.options.join(" · ")}
                        </div>
                      )}
                    </td>
                    <td className="muted">{fl.kind_label}</td>
                    <td>
                      <button className="btn btn-sm btn-ghost"
                              onClick={() => drop(fl.id)}>×</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <button className="btn" style={{ marginTop: 16 }}
                onClick={onClose}>{L("close")}</button>
      </div>
    </div>
  );
}

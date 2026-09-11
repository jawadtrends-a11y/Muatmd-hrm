"use client";
/**
 * وسوم الموظفين (ق-131).
 *
 * **تصنيفٌ حرّ تكتبه الشركة** — لا حقلٌ نضيفه لكل حاجة.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "وسوم الموظفين", en: "Employee tags" },
  sub: {
    ar: "صنّف موظفيك كما تشاء — «سائق»، «مناوب»، «يتقن الإنجليزية»",
    en: "Label employees however you like",
  },
  add: { ar: "وسم جديد", en: "New tag" },
  name: { ar: "الوسم", en: "Tag" },
  descr: { ar: "الوصف", en: "Description" },
  color: { ar: "اللون", en: "Color" },
  count: { ar: "الموظفون", en: "Employees" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا وسوم بعد", en: "No tags yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "الوسوم غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "وسم جديد", en: "New tag" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  none: { ar: "بلا لون", en: "None" },
};

type Tag = {
  id: number; name_ar: string; color: string;
  description: string; is_active: boolean; count: number;
};

const COLORS = [
  ["", "none"], ["teal", "teal"], ["copper", "copper"],
  ["ok", "ok"], ["danger", "danger"],
] as const;

export default function TagsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Tag[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await apiGet<Tag[]>("/tags/"));
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (t: Tag) => {
    setActing(true); setErr("");
    try {
      await apiDelete(`/tags/${t.id}/`);
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
                <th>{L("descr")}</th>
                <th style={{ width: 110 }}>{L("count")}</th>
                <th style={{ width: 100 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={`badge ${t.color ? `badge-${t.color}` : ""}`}>
                      {t.name_ar}
                    </span>
                  </td>
                  <td className="muted">{t.description || "—"}</td>
                  <td><span className="num">{t.count}</span></td>
                  <td>
                    <button className="btn btn-sm btn-danger"
                            disabled={acting} onClick={() => remove(t)}>
                      {L("del")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {adding && (
        <TagDialog L={L} onClose={() => setAdding(false)}
                   onSaved={async () => {
                     setAdding(false);
                     setMsg(L("savedOk"));
                     setTimeout(() => setMsg(""), 3000);
                     await load();
                   }} />
      )}
    </div>
  );
}


function TagDialog({ L, onClose, onSaved }: {
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({ name_ar: "", color: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/tags/", f);
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
      <div className="card" style={{ padding: 24, maxWidth: 400,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("newTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 16 }}>
          <label className="field">
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar} autoFocus
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
          <label className="field">
            <span className="label">{L("descr")}</span>
            <input className="input" value={f.description}
                   onChange={(e) => setF({ ...f,
                     description: e.target.value })} />
          </label>
          <label className="field">
            <span className="label">{L("color")}</span>
            <select className="select" value={f.color}
                    onChange={(e) => setF({ ...f,
                      color: e.target.value })}>
              {COLORS.map(([v, label]) => (
                <option key={v} value={v}>
                  {v ? label : L("none")}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim()} onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

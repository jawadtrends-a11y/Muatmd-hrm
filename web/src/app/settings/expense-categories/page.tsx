"use client";
/**
 * فئات المصروفات (ق-139).
 *
 * **والسقف في الفئة** — «وقود حتى ٣٠٠ للمطالبة و٨٠٠ للشهر».
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "فئات المصروفات", en: "Expense categories" },
  sub: {
    ar: "عرّف فئاتك وسقوفها — والفاتورة إلزامية دائمًا",
    en: "Define categories and caps — receipts always required",
  },
  add: { ar: "فئة جديدة", en: "New category" },
  name: { ar: "الفئة", en: "Category" },
  code: { ar: "الرمز", en: "Code" },
  perClaim: { ar: "سقف المطالبة", en: "Per claim" },
  perMonth: { ar: "سقف الشهر", en: "Per month" },
  noCap: { ar: "بلا حدّ", en: "No limit" },
  descr: { ar: "الوصف", en: "Description" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا فئات بعد", en: "No categories yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "المصروفات غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "فئة مصروف", en: "Expense category" },
  capHint: {
    ar: "اتركه فارغًا إن لم يكن ثمّة سقف — والاعتماد هو الضابط",
    en: "Leave empty for no cap — approval is the control",
  },
  active: { ar: "مفعّلة", en: "Active" },
  savedOk: { ar: "حُفظت", en: "Saved" },
};

type Category = {
  id: number; code: string; name_ar: string; description: string;
  max_per_claim: string | null; max_per_month: string | null;
  component_code: string; is_active: boolean;
};

export default function ExpenseCategoriesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Category[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Category | null>(null);
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await apiGet<Category[]>("/expense-categories/"));
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (c: Category) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ deactivated?: boolean;
                                    detail?: string }>(
        `/expense-categories/${c.id}/`);
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
                <th style={{ width: 130 }}>{L("perClaim")}</th>
                <th style={{ width: 130 }}>{L("perMonth")}</th>
                <th style={{ width: 160 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} style={{ opacity: c.is_active ? 1 : .55 }}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{c.name_ar}</div>
                    <div className="muted num"
                         style={{ fontSize: ".75rem" }}>{c.code}</div>
                  </td>
                  <td>
                    {c.max_per_claim
                      ? <span className="num">{c.max_per_claim}</span>
                      : <span className="muted">{L("noCap")}</span>}
                  </td>
                  <td>
                    {c.max_per_month
                      ? <span className="num">{c.max_per_month}</span>
                      : <span className="muted">{L("noCap")}</span>}
                  </td>
                  <td>
                    <div className="row" style={{ gap: 5 }}>
                      <button className="btn btn-sm"
                              onClick={() => { setEditing(c);
                                               setErr(""); }}>
                        {L("edit")}
                      </button>
                      <button className="btn btn-sm btn-danger"
                              disabled={acting}
                              onClick={() => remove(c)}>{L("del")}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {(editing || adding) && (
        <CatDialog c={editing} L={L}
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


function CatDialog({ c, L, onClose, onSaved }: {
  c: Category | null;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: c?.code || "",
    name_ar: c?.name_ar || "",
    description: c?.description || "",
    max_per_claim: c?.max_per_claim || "",
    max_per_month: c?.max_per_month || "",
    is_active: c?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      if (c) await apiPut(`/expense-categories/${c.id}/`, f);
      else await apiPost("/expense-categories/", f);
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
      <div className="card" style={{ padding: 24, maxWidth: 450,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{c ? c.name_ar : L("newTitle")}</h3>

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
          {!c && (
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

        <div className="row" style={{ gap: 12, marginTop: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("perClaim")}</span>
            <input className="input num" type="number" min={0}
                   step="0.01" value={f.max_per_claim}
                   placeholder={L("noCap")}
                   onChange={(e) => setF({ ...f,
                     max_per_claim: e.target.value })} />
          </label>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("perMonth")}</span>
            <input className="input num" type="number" min={0}
                   step="0.01" value={f.max_per_month}
                   placeholder={L("noCap")}
                   onChange={(e) => setF({ ...f,
                     max_per_month: e.target.value })} />
          </label>
        </div>
        <div className="muted" style={{ fontSize: ".78rem", marginTop: 4 }}>
          {L("capHint")}
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("descr")}</span>
          <input className="input" value={f.description}
                 onChange={(e) => setF({ ...f,
                   description: e.target.value })} />
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim() || (!c && !f.code)}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

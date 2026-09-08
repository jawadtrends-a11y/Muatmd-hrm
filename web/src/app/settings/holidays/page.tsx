"use client";
/**
 * العطل الرسمية — تديرها الشركة بالكامل (ق-103).
 *
 * في الإعدادات لا في الهيكل التنظيمي: الهيكل فروع وأقسام
 * ومسمّيات، والعطلة تقويمٌ يخصّ الحضور والإجازات والمسير.
 *
 * ولا تصنيفات لها: الشركة تكتب اسمها وتحدّد تاريخيها.
 */
import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcClock, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "العطل الرسمية", en: "Public holidays" },
  subtitle: {
    ar: "عطل الشركة — لا تُخصم من رصيد الإجازات ولا من الأجر",
    en: "Company holidays — not deducted from leave balance or pay",
  },
  add: { ar: "عطلة جديدة", en: "New holiday" },
  nameAr: { ar: "الاسم", en: "Name" },
  nameEn: { ar: "الاسم بالإنجليزية", en: "Name (English)" },
  from: { ar: "من تاريخ", en: "From" },
  to: { ar: "إلى تاريخ", en: "To" },
  days: { ar: "الأيام", en: "Days" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  confirmDel: {
    ar: "حذف هذه العطلة؟ سيُعاد احتساب أيام الحضور المتأثرة.",
    en: "Delete this holiday? Affected attendance days are recomputed.",
  },
  empty: { ar: "لا عطل — أضف الأولى", en: "No holidays — add the first" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك صلاحية إدارة العطل", en: "Not permitted" },
  required: { ar: "الاسم والتاريخان مطلوبة", en: "Name and dates are required" },
  badRange: { ar: "تاريخ النهاية قبل البداية", en: "End date is before start" },
  saved: { ar: "حُفظت", en: "Saved" },
};

type Holiday = {
  id: number;
  name_ar: string;
  name_en?: string;
  start_date: string;
  end_date: string;
  days: number;
};

const today = () => new Date().toISOString().slice(0, 10);

export default function HolidaysPage() {
  const { L, lang } = useT(T);
  const [rows, setRows] = useState<Holiday[]>([]);
  const [perms, setPerms] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [f, setF] = useState({
    name_ar: "", name_en: "",
    start_date: today(), end_date: today(),
  });

  const canView = perms.includes("org.view") || perms.includes("org.manage");
  const canManage = perms.includes("org.manage");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      setRows(await apiGet<Holiday[]>("/org/holidays/"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const reset = () => {
    setF({ name_ar: "", name_en: "", start_date: today(), end_date: today() });
    setAdding(false); setEditing(null); setErr("");
  };

  const startEdit = (h: Holiday) => {
    setF({ name_ar: h.name_ar, name_en: h.name_en || "",
           start_date: h.start_date, end_date: h.end_date });
    setEditing(h.id); setAdding(false); setErr("");
  };

  const save = async () => {
    if (!f.name_ar.trim() || !f.start_date || !f.end_date) {
      setErr(L("required")); return;
    }
    if (f.end_date < f.start_date) { setErr(L("badRange")); return; }
    setSaving(true); setErr("");
    try {
      if (editing) await apiPut(`/org/holidays/${editing}/`, f);
      else await apiPost("/org/holidays/", f);
      setMsg(L("saved"));
      setTimeout(() => setMsg(""), 3000);
      reset(); await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!delId) return;
    try {
      await apiDelete(`/org/holidays/${delId}/`);
      setDelId(null); await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
      setDelId(null);
    }
  };

  if (busy) return <div className="card" style={{ padding: 40,
    textAlign: "center", color: "var(--ink-3)" }}>{L("loading")}</div>;

  if (!canView) return (
    <div className="card" style={{ padding: 36, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      <IcAlert size={22} />
      <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
    </div>
  );

  const form = (
    <div className="card" style={{ padding: 20 }}>
      <div className="row" style={{ flexWrap: "wrap", gap: 12,
                                    alignItems: "flex-start" }}>
        <div className="field" style={{ minWidth: 220, flex: "1 1 220px" }}>
          <label className="label">{L("nameAr")}</label>
          <input className="input" value={f.name_ar} autoFocus
                 onChange={(e) => setF({ ...f, name_ar: e.target.value })} />
        </div>
        <div className="field" style={{ minWidth: 220, flex: "1 1 220px" }}>
          <label className="label">{L("nameEn")}</label>
          <input className="input" value={f.name_en} dir="ltr"
                 onChange={(e) => setF({ ...f, name_en: e.target.value })} />
        </div>
        <div className="field" style={{ minWidth: 160 }}>
          <label className="label">{L("from")}</label>
          <DateField value={f.start_date}
                     onChange={(v) => setF({ ...f, start_date: v })} />
        </div>
        <div className="field" style={{ minWidth: 160 }}>
          <label className="label">{L("to")}</label>
          <DateField value={f.end_date}
                     onChange={(v) => setF({ ...f, end_date: v })} />
        </div>
      </div>
      {err && (
        <div style={{ background: "var(--danger-soft)", color: "var(--danger)",
                      padding: "9px 12px", borderRadius: "var(--radius-sm)",
                      fontSize: ".88rem", marginTop: 12 }}>{err}</div>
      )}
      <div className="row" style={{ gap: 8, marginTop: 14 }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? L("saving") : L("save")}
        </button>
        <button className="btn" onClick={reset}>{L("cancel")}</button>
      </div>
    </div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canManage && !adding && editing === null && (
          <button className="btn btn-primary"
                  onClick={() => { reset(); setAdding(true); }}>
            <IcPlus size={16} /> {L("add")}
          </button>
        )}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && !adding && editing === null && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <IcAlert /> {err}
        </div>
      )}

      {(adding || editing !== null) && form}

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcClock size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("nameAr")}</th>
                  <th style={{ width: 140 }}>{L("from")}</th>
                  <th style={{ width: 140 }}>{L("to")}</th>
                  <th style={{ width: 90 }}>{L("days")}</th>
                  {canManage && <th style={{ width: 150 }} />}
                </tr>
              </thead>
              <tbody>
                {rows.map((h) => (
                  <tr key={h.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {(lang === "en" ? h.name_en : h.name_ar) || h.name_ar}
                      </div>
                      {lang !== "en" && h.name_en && (
                        <div className="muted" style={{ fontSize: ".76rem" }}
                             dir="ltr">{h.name_en}</div>
                      )}
                    </td>
                    <td><span className="num">{h.start_date}</span></td>
                    <td><span className="num">{h.end_date}</span></td>
                    <td><span className="num">{h.days}</span></td>
                    {canManage && (
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm"
                                  onClick={() => startEdit(h)}>
                            {L("edit")}
                          </button>
                          <button className="btn btn-sm btn-danger"
                                  onClick={() => setDelId(h.id)}>
                            <IcX size={13} /> {L("del")}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={delId !== null}
        message={L("confirmDel")}
        tone="danger"
        onConfirm={remove}
        onCancel={() => setDelId(null)}
      />
    </div>
  );
}

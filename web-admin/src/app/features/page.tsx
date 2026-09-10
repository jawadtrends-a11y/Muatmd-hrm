"use client";
/**
 * إدارة المزايا (ق-125).
 *
 * **التحكّم الكامل**: تُضاف الميزة وتُعدَّل وتُفعَّل بلا نشر.
 *
 * ⚠️ **إلا الحراسة** — فهي حقيقةٌ تقنية لا تفضيل مشغّل: ميزةٌ بلا
 * حارس في الكود لا تصير محروسة بضغطة زرّ، وادّعاؤها يبيع وهمًا.
 */
import { useCallback, useEffect, useState } from "react";
import { pGet, pPost, pPut, pDelete, type AdminError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "المزايا", en: "Features" },
  subtitle: {
    ar: "ما يُباع في الباقات — والمحروس منه ما له حارس في الكود",
    en: "What plans sell — guarded ones have code enforcing them",
  },
  add: { ar: "ميزة جديدة", en: "New feature" },
  sync: { ar: "تحديث الحراسة", en: "Sync guards" },
  syncing: { ar: "جارٍ…", en: "Working…" },
  search: { ar: "بحث…", en: "Search…" },
  allModules: { ar: "كل الوحدات", en: "All modules" },
  onlyGuarded: { ar: "المحروسة فقط", en: "Guarded only" },
  onlyUnguarded: { ar: "بلا حارس", en: "Unguarded" },
  key: { ar: "المفتاح", en: "Key" },
  name: { ar: "الاسم", en: "Name" },
  module: { ar: "الوحدة", en: "Module" },
  type: { ar: "النوع", en: "Type" },
  guard: { ar: "الحراسة", en: "Guard" },
  plans: { ar: "الباقات", en: "Plans" },
  state: { ar: "الحالة", en: "State" },
  guarded: { ar: "محروسة", en: "Guarded" },
  unguarded: { ar: "بلا حارس", en: "No guard" },
  active: { ar: "مفعّلة", en: "Active" },
  inactive: { ar: "معطّلة", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك عرض المزايا", en: "Not permitted" },
  total: { ar: "الإجمالي", en: "Total" },
  descr: { ar: "الوصف", en: "Description" },
  order: { ar: "الترتيب", en: "Order" },
  newTitle: { ar: "ميزة جديدة", en: "New feature" },
  newHint: {
    ar: "تُضاف بلا حارس — فلا تُباع حتى يُكتب لها كود يمنعها",
    en: "Added unguarded — not sold until code enforces it",
  },
  keyHint: {
    ar: "بالإنجليزية بلا مسافات — والكود يشير إليه",
    en: "English, no spaces — code references it",
  },
  guardHint: {
    ar: "موضع الفحص في الكود — يُحدَّث بالمزامنة لا يدويًّا",
    en: "Where it's enforced — updated by sync",
  },
  syncDone: { ar: "حُدّثت الحراسة: {n} ميزة", en: "{n} features synced" },
};

type Feature = {
  id: number; feature_key: string; module: string;
  name_ar: string; name_en: string; description_ar: string;
  value_type: string; sort_order: number;
  is_active: boolean; is_implemented: boolean; guarded_at: string;
  plans: string[];
};

export default function FeaturesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Feature[]>([]);
  const [modules, setModules] = useState<string[]>([]);
  const [stats, setStats] = useState({ total: 0, implemented: 0 });
  const [q, setQ] = useState("");
  const [mod, setMod] = useState("");
  const [only, setOnly] = useState<"" | "guarded" | "unguarded">("");
  const [busy, setBusy] = useState(true);
  const [acting, setActing] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<Feature | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await pGet<{ features: Feature[]; modules: string[];
                             total: number; implemented: number }>(
        "/platform/features/");
      setRows(d.features);
      setModules(d.modules);
      setStats({ total: d.total, implemented: d.implemented });
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setActing(true); setErr("");
    try {
      const out = await pPost<{ total: number }>(
        "/platform/features/sync/", {});
      setMsg(L("syncDone").replace("{n}", String(out.total)));
      setTimeout(() => setMsg(""), 5000);
      await load();
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setActing(false); }
  };

  const remove = async (f: Feature) => {
    setActing(true); setErr("");
    try {
      await pDelete(`/platform/features/${f.id}/`);
      await load();
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setActing(false); }
  };

  const visible = rows.filter((f) => {
    if (mod && f.module !== mod) return false;
    if (only === "guarded" && !f.is_implemented) return false;
    if (only === "unguarded" && f.is_implemented) return false;
    if (!q.trim()) return true;
    const t = q.toLowerCase();
    return f.feature_key.toLowerCase().includes(t)
      || f.name_ar.includes(q) || f.module.includes(t);
  });

  // الصلاحية تُفحص في الخادم — والإخفاء هنا تحسين عرضٍ لا حماية
  const mayWrite = true;

  if (busy) return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
      {L("loading")}
    </div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-sm" disabled={acting} onClick={sync}>
            {acting ? L("syncing") : L("sync")}
          </button>
          {mayWrite && (
            <button className="btn btn-primary btn-sm"
                    onClick={() => setAdding(true)}>
              {L("add")}
            </button>
          )}
        </div>
      </div>

      {msg && (
        <div style={{ background: "var(--ok-soft)", color: "var(--ok)",
                      padding: "10px 14px", borderRadius: "var(--radius-sm)" }}>
          <IcCheck size={15} /> {msg}
        </div>
      )}
      {err && (
        <div style={{ background: "var(--danger-soft)",
                      color: "var(--danger)", padding: "10px 14px",
                      borderRadius: "var(--radius-sm)" }}>
          <IcAlert size={15} /> {err}
        </div>
      )}

      <div className="card" style={{ padding: 14 }}>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <input className="input" style={{ maxWidth: 260 }}
                 placeholder={L("search")} value={q}
                 onChange={(e) => setQ(e.target.value)} />
          <select className="select" style={{ maxWidth: 200 }}
                  value={mod} onChange={(e) => setMod(e.target.value)}>
            <option value="">{L("allModules")}</option>
            {modules.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="select" style={{ maxWidth: 180 }}
                  value={only}
                  onChange={(e) => setOnly(e.target.value as typeof only)}>
            <option value="">—</option>
            <option value="guarded">{L("onlyGuarded")}</option>
            <option value="unguarded">{L("onlyUnguarded")}</option>
          </select>
          <div className="muted" style={{ fontSize: ".85rem",
                                          alignSelf: "center" }}>
            {L("guarded")} <span className="num">{stats.implemented}</span>
            {" / "}
            <span className="num">{stats.total}</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>{L("name")}</th>
                <th style={{ width: 170 }}>{L("key")}</th>
                <th style={{ width: 110 }}>{L("module")}</th>
                <th style={{ width: 90 }}>{L("state")}</th>
                <th style={{ width: 160 }}>{L("plans")}</th>
                {mayWrite && <th style={{ width: 140 }} />}
              </tr>
            </thead>
            <tbody>
              {visible.map((f) => (
                <tr key={f.id} style={{
                  opacity: f.is_active ? 1 : 0.55,
                }}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{f.name_ar}</div>
                    {f.guarded_at && (
                      <div className="muted" style={{ fontSize: ".74rem" }}>
                        {f.guarded_at}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="num" style={{ fontSize: ".8rem" }}>
                      {f.feature_key}
                    </span>
                  </td>
                  <td className="muted">{f.module}</td>
                  <td>
                    {f.is_implemented ? (
                      <span className="badge badge-ok">{L("guarded")}</span>
                    ) : (
                      <span className="badge badge-warn">
                        {L("unguarded")}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="row" style={{ gap: 3, flexWrap: "wrap" }}>
                      {f.plans.map((p) => (
                        <span key={p} className="badge"
                              style={{ fontSize: ".7rem" }}>{p}</span>
                      ))}
                    </div>
                  </td>
                  {mayWrite && (
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm"
                                onClick={() => { setEditing(f); setErr(""); }}>
                          {L("edit")}
                        </button>
                        {!f.is_implemented && f.plans.length === 0 && (
                          <button className="btn btn-sm btn-danger"
                                  disabled={acting}
                                  onClick={() => remove(f)}>
                            {L("del")}
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="muted" style={{ fontSize: ".85rem" }}>
        {L("total")}: <span className="num">{visible.length}</span>
      </div>

      {(editing || adding) && (
        <FeatureDialog
          feature={editing} modules={modules} L={L}
          onClose={() => { setEditing(null); setAdding(false); }}
          onSaved={async () => {
            setEditing(null); setAdding(false); await load();
          }} />
      )}
    </div>
  );
}


/* ══ نافذة الإضافة والتعديل ══ */

function FeatureDialog({ feature, modules, L, onClose, onSaved }: {
  feature: Feature | null;
  modules: string[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    feature_key: feature?.feature_key || "",
    name_ar: feature?.name_ar || "",
    name_en: feature?.name_en || "",
    description_ar: feature?.description_ar || "",
    module: feature?.module || (modules[0] || "other"),
    value_type: feature?.value_type || "bool",
    sort_order: String(feature?.sort_order ?? 999),
    is_active: feature?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = { ...f, sort_order: Number(f.sort_order) || 0 };
      if (feature) await pPut(`/platform/features/${feature.id}/`, body);
      else await pPost("/platform/features/", body);
      onSaved();
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 460,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>
          {feature ? feature.name_ar : L("newTitle")}
        </h3>
        {!feature && (
          <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
            {L("newHint")}
          </div>
        )}

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 16 }}>
          {!feature && (
            <label className="field">
              <span className="label">{L("key")}</span>
              <input className="input" dir="ltr" value={f.feature_key}
                     onChange={(e) => setF({ ...f,
                       feature_key: e.target.value.trim() })} />
              <span className="muted" style={{ fontSize: ".78rem" }}>
                {L("keyHint")}
              </span>
            </label>
          )}

          <label className="field">
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f, name_ar: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("name")} (EN)</span>
            <input className="input" dir="ltr" value={f.name_en}
                   onChange={(e) => setF({ ...f, name_en: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("descr")}</span>
            <textarea className="input" rows={2} value={f.description_ar}
                      onChange={(e) => setF({ ...f,
                        description_ar: e.target.value })} />
          </label>

          <div className="row" style={{ gap: 10 }}>
            <label className="field" style={{ flex: 1 }}>
              <span className="label">{L("module")}</span>
              <input className="input" dir="ltr" value={f.module}
                     list="mods"
                     onChange={(e) => setF({ ...f, module: e.target.value })} />
              <datalist id="mods">
                {modules.map((m) => <option key={m} value={m} />)}
              </datalist>
            </label>
            <label className="field" style={{ width: 120 }}>
              <span className="label">{L("type")}</span>
              <select className="select" value={f.value_type}
                      onChange={(e) => setF({ ...f,
                        value_type: e.target.value })}>
                <option value="bool">bool</option>
                <option value="int">int</option>
                <option value="text">text</option>
              </select>
            </label>
            <label className="field" style={{ width: 100 }}>
              <span className="label">{L("order")}</span>
              <input className="input num" type="number" value={f.sort_order}
                     onChange={(e) => setF({ ...f,
                       sort_order: e.target.value })} />
            </label>
          </div>

          <label className="row" style={{ gap: 8, cursor: "pointer" }}>
            <input type="checkbox" checked={f.is_active}
                   onChange={(e) => setF({ ...f,
                     is_active: e.target.checked })} />
            <span>{L("active")}</span>
          </label>

          {feature && (
            <div style={{ padding: "10px 14px", fontSize: ".82rem",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--paper-2)" }}>
              <div className="spread">
                <span className="muted">{L("guard")}</span>
                <span>
                  {feature.is_implemented ? L("guarded") : L("unguarded")}
                </span>
              </div>
              <div className="muted" style={{ fontSize: ".76rem",
                                              marginTop: 4 }}>
                {L("guardHint")}
              </div>
            </div>
          )}
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy || !f.name_ar}
                  onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

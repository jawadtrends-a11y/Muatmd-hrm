"use client";
/**
 * الباقات (ق-108) — الأسماء والأسعار والمزايا.
 *
 * القرار التجاريّ يتغيّر، فلا يُدفن في بذرة تحتاج نشرًا لتعديلها.
 */
import { useCallback, useEffect, useState } from "react";
import { pGet, pPost, pPut, pDelete } from "@/lib/api";

type Tier = {
  id?: number; from_employees: number; to_employees: number | null;
  monthly: string; yearly: string;
};
type Plan = {
  id: number; code: string; name_ar: string; name_en: string;
  tier_order: number; base_fee_monthly: string;
  min_billable_employees: number; max_employees: number | null;
  trial_days: number; is_public: boolean; is_active: boolean;
  tiers: Tier[]; features: Record<string, string>;
};
type Feat = {
  key: string; name_ar: string; module: string;
  value_type: string; is_core: boolean;
};

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [feats, setFeats] = useState<Feat[]>([]);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [edit, setEdit] = useState<Plan | null>(null);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await pGet<{ plans: Plan[]; features: Feat[] }>(
        "/platform/plans/");
      setPlans(d.plans);
      setFeats(d.features);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!edit) return;
    setSaving(true); setErr("");
    try {
      await pPut(`/platform/plans/${edit.id}/`, edit);
      setMsg("حُفظت الباقة");
      setTimeout(() => setMsg(""), 3000);
      setEdit(null);
      await load();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setSaving(false); }
  };

  const create = async () => {
    if (!newCode.trim() || !newName.trim()) return;
    try {
      await pPost("/platform/plans/", {
        code: newCode.trim(), name_ar: newName.trim(),
        tier_order: plans.length + 1,
      });
      setCreating(false); setNewCode(""); setNewName("");
      await load();
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };

  const remove = async (p: Plan) => {
    if (!confirm(`حذف «${p.name_ar}»؟`)) return;
    await pDelete(`/platform/plans/${p.id}/`).catch(
      (e) => setErr(String((e as Error).message)));
    await load();
  };

  const setTier = (i: number, patch: Partial<Tier>) => {
    if (!edit) return;
    const tiers = edit.tiers.map((t, j) => (j === i ? { ...t, ...patch } : t));
    setEdit({ ...edit, tiers });
  };

  const addTier = () => {
    if (!edit) return;
    const last = edit.tiers[edit.tiers.length - 1];
    setEdit({ ...edit, tiers: [...edit.tiers, {
      from_employees: last ? (last.to_employees || last.from_employees) + 1 : 1,
      to_employees: null, monthly: "0", yearly: "0",
    }] });
  };

  const toggleFeat = (k: string, type: string) => {
    if (!edit) return;
    const f = { ...edit.features };
    if (k in f) delete f[k];
    else f[k] = type === "bool" ? "true" : "0";
    setEdit({ ...edit, features: f });
  };

  if (busy) return <div className="card" style={{ padding: 18 }}>جارٍ التحميل…</div>;

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>الباقات</h1>
          <div className="muted" style={{ fontSize: ".85rem" }}>
            الأسعار لكل موظف — والحساب على عدد الموظفين النشطين
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
          باقة جديدة
        </button>
      </div>

      {msg && <div className="card" style={{ padding: 14, borderColor: "var(--ok)" }}>{msg}</div>}
      {err && <div className="card" style={{ padding: 14, borderColor: "var(--danger)" }}>{err}</div>}

      {creating && (
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <input className="input" placeholder="الرمز (بالإنجليزية)"
                   value={newCode} dir="ltr"
                   onChange={(e) => setNewCode(e.target.value)} />
            <input className="input" placeholder="الاسم بالعربية"
                   value={newName}
                   onChange={(e) => setNewName(e.target.value)} />
            <button className="btn btn-primary" onClick={create}>إنشاء</button>
            <button className="btn" onClick={() => setCreating(false)}>
              إلغاء
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gap: 14,
                    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
        {plans.map((p) => (
          <div key={p.id} className="card" style={{ padding: 18 }}>
            <div className="spread">
              <div>
                <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>
                  {p.name_ar}
                </div>
                <div className="muted" style={{ fontSize: ".85rem" }} dir="ltr">{p.code}</div>
              </div>
              <span className={p.is_active ? "badge badge-ok" : "badge"}>
                {p.is_active ? "مفعّلة" : "معطّلة"}
              </span>
            </div>

            <div style={{ marginTop: 12 }}>
              {p.tiers.map((t) => (
                <div key={t.id ?? t.from_employees} className="spread"
                     style={{ fontSize: ".85rem", padding: "3px 0" }}>
                  <span className="muted">
                    {t.from_employees}–{t.to_employees ?? "∞"} موظفًا
                  </span>
                  <span>
                    <b>{t.monthly}</b> شهريًّا · {t.yearly} سنويًّا
                  </span>
                </div>
              ))}
              {p.tiers.length === 0 && (
                <div className="muted" style={{ fontSize: ".85rem" }}>لا أسعار — أضفها</div>
              )}
            </div>

            <div className="muted" style={{ fontSize: ".85rem", marginTop: 10 }}>
              {Object.keys(p.features).length} ميزة ·
              تجربة {p.trial_days} يومًا ·
              حد أدنى {p.min_billable_employees}
            </div>

            <div className="row" style={{ gap: 6, marginTop: 12 }}>
              <button className="btn btn-sm" onClick={() => setEdit(p)}>تعديل</button>
              <button className="btn btn-sm btn-danger" onClick={() => remove(p)}>
                حذف
              </button>
            </div>
          </div>
        ))}
      </div>

      {edit && (
        <div onClick={() => setEdit(null)} style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 70,
        }}>
          <div className="card" style={{ padding: 22, maxWidth: 720, width: "100%",
                                       maxHeight: "85vh", overflowY: "auto" }}
               onClick={(e) => e.stopPropagation()}>
            <h3>تعديل: {edit.name_ar}</h3>

            <div className="row" style={{ gap: 10, flexWrap: "wrap",
                                          marginTop: 12 }}>
              <label className="field">
                <span className="muted" style={{ fontSize: ".85rem" }}>الاسم بالعربية</span>
                <input className="input" value={edit.name_ar}
                       onChange={(e) => setEdit({ ...edit, name_ar: e.target.value })} />
              </label>
              <label className="field">
                <span className="muted" style={{ fontSize: ".85rem" }}>الاسم بالإنجليزية</span>
                <input className="input" value={edit.name_en} dir="ltr"
                       onChange={(e) => setEdit({ ...edit, name_en: e.target.value })} />
              </label>
              <label className="field">
                <span className="muted" style={{ fontSize: ".85rem" }}>أيام التجربة</span>
                <input className="input" type="number" value={edit.trial_days}
                       onChange={(e) => setEdit({ ...edit, trial_days: +e.target.value })} />
              </label>
              <label className="field">
                <span className="muted" style={{ fontSize: ".85rem" }}>أدنى عدد محتسَب</span>
                <input className="input" type="number"
                       value={edit.min_billable_employees}
                       onChange={(e) => setEdit({ ...edit, min_billable_employees: +e.target.value })} />
              </label>
            </div>

            <h4 style={{ marginTop: 18 }}>الأسعار لكل موظف</h4>
            {edit.tiers.map((t, i) => (
              <div key={i} className="row" style={{ gap: 8, marginTop: 8,
                                                    flexWrap: "wrap" }}>
                <input className="input" style={{ width: 90 }} type="number"
                       value={t.from_employees}
                       onChange={(e) => setTier(i, { from_employees: +e.target.value })} />
                <span className="muted">إلى</span>
                <input className="input" style={{ width: 90 }} type="number"
                       placeholder="∞"
                       value={t.to_employees ?? ""}
                       onChange={(e) => setTier(i, {
                         to_employees: e.target.value ? +e.target.value : null })} />
                <input className="input" style={{ width: 110 }}
                       value={t.monthly} placeholder="شهريًّا"
                       onChange={(e) => setTier(i, { monthly: e.target.value })} />
                <input className="input" style={{ width: 110 }}
                       value={t.yearly} placeholder="سنويًّا"
                       onChange={(e) => setTier(i, { yearly: e.target.value })} />
                <button className="btn btn-sm btn-danger"
                        onClick={() => setEdit({ ...edit,
                          tiers: edit.tiers.filter((_, j) => j !== i) })}>
                  ×
                </button>
              </div>
            ))}
            <button className="btn btn-sm" style={{ marginTop: 8 }}
                    onClick={addTier}>+ شريحة</button>

            <h4 style={{ marginTop: 18 }}>المزايا</h4>
            <div style={{ display: "grid", gap: 4,
                          gridTemplateColumns: "repeat(2, 1fr)" }}>
              {feats.map((f) => (
                <label key={f.key} className="row" style={{ gap: 8,
                                                            fontSize: ".88rem" }}>
                  <input type="checkbox" checked={f.key in edit.features}
                         onChange={() => toggleFeat(f.key, f.value_type)} />
                  <span>{f.name_ar}</span>
                  {f.key in edit.features && f.value_type !== "bool" && (
                    <input className="input" style={{ width: 70 }}
                           value={edit.features[f.key]}
                           onChange={(e) => setEdit({ ...edit, features: {
                             ...edit.features, [f.key]: e.target.value } })} />
                  )}
                </label>
              ))}
            </div>

            <div className="row" style={{ gap: 8, marginTop: 18 }}>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? "جارٍ الحفظ…" : "حفظ"}
              </button>
              <button className="btn" onClick={() => setEdit(null)}>إلغاء</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

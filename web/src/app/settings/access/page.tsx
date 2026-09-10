"use client";
/**
 * الأدوار والصلاحيات (ق-127).
 *
 * **الأدوار الستّة تكفي أكثر المنشآت** — ومن احتاج غيرها يبنيه
 * بصلاحياته.
 *
 * ⚠️ والأساسيّ **يُعدَّل ولا يُحذف**: الكود يشير إليه برمزه.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الأدوار والصلاحيات", en: "Roles & permissions" },
  sub: {
    ar: "من يرى ماذا ومن يفعل ماذا — والدور يُبنى إن لم يكفِ الجاهز",
    en: "Who sees and does what — build a role if the defaults fall short",
  },
  add: { ar: "دور جديد", en: "New role" },
  role: { ar: "الدور", en: "Role" },
  scope: { ar: "النطاق", en: "Scope" },
  perms: { ar: "الصلاحيات", en: "Permissions" },
  users: { ar: "الموظفون", en: "Users" },
  system: { ar: "أساسي", en: "Built-in" },
  edit: { ar: "الصلاحيات", en: "Permissions" },
  rename: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك عرض الأدوار", en: "Not permitted" },
  newTitle: { ar: "دور جديد", en: "New role" },
  newHint: {
    ar: "لا تمنح صلاحيةً ليست لك — والنظام يرفضها",
    en: "You cannot grant what you don't have",
  },
  code: { ar: "الرمز", en: "Code" },
  codeHint: {
    ar: "بالإنجليزية بلا مسافات — ولا يتغيّر بعد الحفظ",
    en: "English, no spaces — fixed after saving",
  },
  name: { ar: "الاسم", en: "Name" },
  scopeOwn: { ar: "نفسه", en: "Own" },
  scopeTeam: { ar: "فريقه", en: "Team" },
  scopeDept: { ar: "إدارته", en: "Department" },
  scopeCompany: { ar: "الشركة", en: "Company" },
  scopeAccount: { ar: "الحساب", en: "Account" },
  pickPerms: { ar: "اختر صلاحياته", en: "Pick permissions" },
  selected: { ar: "مختارة", en: "selected" },
  protected: {
    ar: "محميّة — لا تُنزع من مالك الحساب",
    en: "Protected — never removed from the owner",
  },
  savedOk: { ar: "حُفظ", en: "Saved" },
};

type Role = {
  id: number; code: string; name_ar: string; default_scope: string;
  is_system: boolean; permission_count: number; assigned_users: number;
};
type Perm = { key: string; name_ar: string; is_protected: boolean };
type Module = { key: string; permissions: Perm[] };

const SCOPES = [
  ["own", "scopeOwn"], ["team", "scopeTeam"], ["department", "scopeDept"],
  ["company", "scopeCompany"], ["account", "scopeAccount"],
] as const;

export default function AccessPage() {
  const { L } = useT(T);
  const [roles, setRoles] = useState<Role[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [mine, setMine] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Role | null>(null);
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [r, p, w] = await Promise.all([
        apiGet<Role[]>("/access/roles/"),
        apiGet<{ modules: Module[] }>("/access/permissions/"),
        apiGet<{ permissions: string[] }>("/me/workspace/")
          .catch(() => ({ permissions: [] })),
      ]);
      setRoles(r);
      setModules(p.modules);
      setMine(w.permissions || []);
    } catch (e) {
      if ((e as ApiError).status === 403) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (r: Role) => {
    setActing(true); setErr("");
    try {
      await apiDelete(`/access/roles/${r.id}/manage/`);
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
        <table className="table">
          <thead>
            <tr>
              <th>{L("role")}</th>
              <th style={{ width: 120 }}>{L("scope")}</th>
              <th style={{ width: 100 }}>{L("perms")}</th>
              <th style={{ width: 100 }}>{L("users")}</th>
              <th style={{ width: 200 }} />
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id}>
                <td>
                  <div style={{ fontWeight: 500 }}>
                    {r.name_ar}
                    {r.is_system && (
                      <span className="badge"
                            style={{ marginInlineStart: 6,
                                     fontSize: ".7rem" }}>
                        {L("system")}
                      </span>
                    )}
                  </div>
                  <div className="muted num" style={{ fontSize: ".76rem" }}>
                    {r.code}
                  </div>
                </td>
                <td className="muted">
                  {L(SCOPES.find(([v]) => v === r.default_scope)?.[1]
                     || "scopeOwn")}
                </td>
                <td><span className="num">{r.permission_count}</span></td>
                <td><span className="num">{r.assigned_users}</span></td>
                <td>
                  <div className="row" style={{ gap: 5 }}>
                    <button className="btn btn-sm"
                            onClick={() => { setEditing(r); setErr(""); }}>
                      {L("edit")}
                    </button>
                    {!r.is_system && r.assigned_users === 0 && (
                      <button className="btn btn-sm btn-danger"
                              disabled={acting} onClick={() => remove(r)}>
                        {L("del")}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(editing || adding) && (
        <RoleDialog role={editing} modules={modules} mine={mine} L={L}
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


/* ══ نافذة الدور ══ */

function RoleDialog({ role, modules, mine, L, onClose, onSaved }: {
  role: Role | null;
  modules: Module[];
  mine: string[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState(role?.name_ar || "");
  const [scope, setScope] = useState(role?.default_scope || "own");
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!role) return;
    apiGet<{ permissions: string[] }>(`/access/roles/${role.id}/`)
      .then((d) => setPicked(d.permissions || []))
      .catch(() => setPicked([]));
  }, [role]);

  const toggle = (k: string) =>
    setPicked(picked.includes(k)
      ? picked.filter((x) => x !== k) : [...picked, k]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      if (role) {
        if (name !== role.name_ar || scope !== role.default_scope) {
          await apiPut(`/access/roles/${role.id}/manage/`,
                       { name_ar: name, default_scope: scope });
        }
        await apiPut(`/access/roles/${role.id}/permissions/`,
                     { permissions: picked });
      } else {
        await apiPost("/access/roles/create/", {
          code, name_ar: name, default_scope: scope, permissions: picked,
        });
      }
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
      <div className="card" style={{ padding: 24, maxWidth: 620,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>
          {role ? role.name_ar : L("newTitle")}
        </h3>
        {!role && (
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

        <div className="row" style={{ gap: 12, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {!role && (
            <label className="field" style={{ minWidth: 160 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={code}
                     onChange={(e) => setCode(
                       e.target.value.trim().toLowerCase())} />
              <span className="muted" style={{ fontSize: ".76rem" }}>
                {L("codeHint")}
              </span>
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 180 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={name}
                   onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field" style={{ minWidth: 150 }}>
            <span className="label">{L("scope")}</span>
            <select className="select" value={scope}
                    onChange={(e) => setScope(e.target.value)}>
              {SCOPES.map(([v, k]) => (
                <option key={v} value={v}>{L(k)}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="spread" style={{ marginTop: 18 }}>
          <span className="label">{L("pickPerms")}</span>
          <span className="muted" style={{ fontSize: ".8rem" }}>
            <span className="num">{picked.length}</span> {L("selected")}
          </span>
        </div>

        <div style={{ marginTop: 8, display: "grid", gap: 14 }}>
          {modules.map((m) => (
            <div key={m.key}>
              <div className="muted" style={{ fontSize: ".8rem",
                                              marginBottom: 5 }}>
                {m.key}
              </div>
              <div className="row" style={{ gap: 5, flexWrap: "wrap" }}>
                {m.permissions.map((p) => {
                  const on = picked.includes(p.key);
                  // ⚠️ ما لا يملكه لا يُعرض قابلًا للاختيار —
                  // والخادم يرفضه على كل حال
                  const owned = mine.includes(p.key);
                  return (
                    <button key={p.key} type="button"
                            disabled={!owned}
                            title={owned ? p.name_ar : L("newHint")}
                            className={`btn btn-sm ${on ? "btn-primary" : "btn-ghost"}`}
                            style={{ opacity: owned ? 1 : 0.4 }}
                            onClick={() => toggle(p.key)}>
                      {p.name_ar}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="row" style={{ gap: 8, marginTop: 20 }}>
          <button className="btn btn-primary"
                  disabled={busy || !name.trim() || (!role && !code)
                            || !picked.length}
                  onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

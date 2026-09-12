"use client";
/**
 * سلسلة موافقات المسير (ق-140).
 *
 * **بالدور لا بالشخص** — فمن غاب حلّ محلّه من يحمل دوره.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "سلسلة اعتماد المسير", en: "Payroll approval chain" },
  sub: {
    ar: "من يعتمد المسير وبأيّ ترتيب — بالدور لا بالشخص",
    en: "Who approves payroll and in what order — by role",
  },
  add: { ar: "خطوة جديدة", en: "New step" },
  order: { ar: "الترتيب", en: "Order" },
  role: { ar: "الدور المعتمِد", en: "Role" },
  stepTitle: { ar: "مسمّى الخطوة", en: "Step title" },
  sla: { ar: "المهلة (ساعة)", en: "SLA (hours)" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: {
    ar: "لا سلسلة — والمسير يُعتمد مباشرةً",
    en: "No chain — payroll is approved directly",
  },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "السلسلة غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "خطوة اعتماد", en: "Approval step" },
  hint: {
    ar: "⚠️ والمسير لا يُعتمد قبل اكتمال سلسلته",
    en: "Payroll cannot be approved until the chain completes",
  },
  roleHint: {
    ar: "بالدور لا بالشخص — فمن غاب حلّ محلّه",
    en: "By role — so absence doesn't block payroll",
  },
  savedOk: { ar: "حُفظت", en: "Saved" },
};

type Step = {
  id: number; step_order: number; role_id: number; role: string;
  title: string; sla_hours: number | null; is_active: boolean;
};
type Role = { id: number; name_ar: string };

export default function PayrollApprovalPage() {
  const { L } = useT(T);
  const [steps, setSteps] = useState<Step[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ steps: Step[]; roles: Role[] }>(
        "/payroll/approval-steps/");
      setSteps(d.steps);
      setRoles(d.roles);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (s: Step) => {
    setActing(true); setErr("");
    try {
      await apiDelete(`/payroll/approval-steps/${s.id}/`);
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

      {steps.length > 0 && (
        <div className="muted" style={{ fontSize: ".85rem" }}>
          {L("hint")}
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {steps.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>{L("order")}</th>
                <th>{L("role")}</th>
                <th style={{ width: 170 }}>{L("stepTitle")}</th>
                <th style={{ width: 110 }}>{L("sla")}</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {steps.map((s) => (
                <tr key={s.id}>
                  <td><span className="num">{s.step_order}</span></td>
                  <td style={{ fontWeight: 500 }}>{s.role}</td>
                  <td className="muted">{s.title || "—"}</td>
                  <td>
                    {s.sla_hours
                      ? <span className="num">{s.sla_hours}</span>
                      : <span className="muted">—</span>}
                  </td>
                  <td>
                    <button className="btn btn-sm btn-danger"
                            disabled={acting}
                            onClick={() => remove(s)}>{L("del")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {adding && (
        <StepDialog roles={roles} nextOrder={steps.length + 1} L={L}
                    onClose={() => setAdding(false)}
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


function StepDialog({ roles, nextOrder, L, onClose, onSaved }: {
  roles: Role[];
  nextOrder: number;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    role_id: "", title: "", sla_hours: "",
    step_order: String(nextOrder),
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/payroll/approval-steps/", {
        role_id: Number(f.role_id),
        title: f.title,
        step_order: Number(f.step_order),
        sla_hours: f.sla_hours ? Number(f.sla_hours) : undefined,
      });
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
      <div className="card" style={{ padding: 24, maxWidth: 420,
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
            <span className="label">{L("role")}</span>
            <select className="select" value={f.role_id}
                    onChange={(e) => setF({ ...f,
                      role_id: e.target.value })}>
              <option value="">—</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>{r.name_ar}</option>
              ))}
            </select>
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("roleHint")}
            </span>
          </label>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ width: 110 }}>
              <span className="label">{L("order")}</span>
              <input className="input num" type="number" min={1}
                     value={f.step_order}
                     onChange={(e) => setF({ ...f,
                       step_order: e.target.value })} />
            </label>
            <label className="field" style={{ width: 130 }}>
              <span className="label">{L("sla")}</span>
              <input className="input num" type="number" min={1}
                     value={f.sla_hours} placeholder="—"
                     onChange={(e) => setF({ ...f,
                       sla_hours: e.target.value })} />
            </label>
          </div>

          <label className="field">
            <span className="label">{L("stepTitle")}</span>
            <input className="input" value={f.title}
                   onChange={(e) => setF({ ...f, title: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.role_id} onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

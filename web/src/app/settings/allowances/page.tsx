"use client";
/**
 * كتالوج المخصّصات المصروفة (ق-134).
 *
 * **الشركة تُعرّفها وتُسندها للأفراد** — فلا يرى الموظف إلا ما
 * أُسند له.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "المخصّصات المصروفة", en: "Claimable allowances" },
  sub: {
    ar: "عرّف مخصّصاتك وأسندها لمن يستحقّها",
    en: "Define allowances and assign them",
  },
  add: { ar: "مخصّص جديد", en: "New allowance" },
  name: { ar: "المخصّص", en: "Allowance" },
  code: { ar: "الرمز", en: "Code" },
  mode: { ar: "نوع المبلغ", en: "Amount type" },
  amount: { ar: "المبلغ", en: "Amount" },
  cap: { ar: "السقف", en: "Cap" },
  eligible: { ar: "المستحقّون", en: "Eligible" },
  attach: { ar: "يلزمه مرفق", en: "Needs receipt" },
  component: { ar: "بند المسير", en: "Pay component" },
  descr: { ar: "الوصف", en: "Description" },
  assign: { ar: "الاستحقاق", en: "Eligibility" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  close: { ar: "إغلاق", en: "Close" },
  empty: { ar: "لا مخصّصات بعد", en: "No allowances yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "المخصّصات غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "مخصّص جديد", en: "New allowance" },
  employee: { ar: "الموظف", en: "Employee" },
  dept: { ar: "الإدارة", en: "Department" },
  customAmount: { ar: "مبلغ خاصّ", en: "Custom amount" },
  addEmployee: { ar: "إضافة موظف", en: "Add employee" },
  remove: { ar: "نزع", en: "Remove" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  noneEligible: { ar: "لا مستحقّين بعد", en: "None eligible yet" },
  modeHint: {
    ar: "الثابت يُصرف كما هو، والسقف يُدخل الموظف أقلّ منه",
    en: "Fixed is exact; cap lets them claim less",
  },
};

type Allowance = {
  id: number; code: string; name_ar: string; description: string;
  mode: string; mode_label: string; amount: string;
  requires_attachment: boolean; component_code: string;
  is_active: boolean; eligible_count: number;
};
type Mode = { value: string; label: string };
type Eligible = {
  employment_id: number; employee_no: string; name: string;
  department: string; custom_amount: string | null;
};
type Peer = { employment_id: number; name: string; job_title: string };

export default function AllowancesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Allowance[]>([]);
  const [modes, setModes] = useState<Mode[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Allowance | null>(null);
  const [adding, setAdding] = useState(false);
  const [assigning, setAssigning] = useState<Allowance | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ allowances: Allowance[]; modes: Mode[] }>(
        "/allowances/");
      setRows(d.allowances);
      setModes(d.modes);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (a: Allowance) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ deactivated?: boolean;
                                    detail?: string }>(
        `/allowances/${a.id}/`);
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
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 120 }}>{L("mode")}</th>
                  <th style={{ width: 110 }}>{L("amount")}</th>
                  <th style={{ width: 110 }}>{L("eligible")}</th>
                  <th style={{ width: 230 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} style={{ opacity: a.is_active ? 1 : .55 }}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {a.name_ar}
                        {a.requires_attachment && (
                          <span className="badge badge-warn"
                                style={{ marginInlineStart: 6,
                                         fontSize: ".68rem" }}>
                            {L("attach")}
                          </span>
                        )}
                      </div>
                      <div className="muted num"
                           style={{ fontSize: ".75rem" }}>{a.code}</div>
                    </td>
                    <td className="muted">{a.mode_label}</td>
                    <td><span className="num">{a.amount}</span></td>
                    <td><span className="num">{a.eligible_count}</span></td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm"
                                onClick={() => setAssigning(a)}>
                          {L("assign")}
                        </button>
                        <button className="btn btn-sm"
                                onClick={() => { setEditing(a);
                                                 setErr(""); }}>
                          {L("edit")}
                        </button>
                        <button className="btn btn-sm btn-danger"
                                disabled={acting}
                                onClick={() => remove(a)}>{L("del")}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {(editing || adding) && (
        <AllowanceDialog a={editing} modes={modes} L={L}
                         onClose={() => { setEditing(null);
                                          setAdding(false); }}
                         onSaved={async () => {
                           setEditing(null); setAdding(false);
                           setMsg(L("savedOk"));
                           setTimeout(() => setMsg(""), 3000);
                           await load();
                         }} />
      )}

      {assigning && (
        <EligibilityDialog a={assigning} L={L}
                           onClose={() => setAssigning(null)}
                           onChanged={load} />
      )}
    </div>
  );
}


/* ══ نافذة المخصّص ══ */

function AllowanceDialog({ a, modes, L, onClose, onSaved }: {
  a: Allowance | null;
  modes: Mode[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: a?.code || "",
    name_ar: a?.name_ar || "",
    description: a?.description || "",
    mode: a?.mode || "fixed",
    amount: a?.amount || "",
    requires_attachment: a?.requires_attachment ?? false,
    component_code: a?.component_code || "",
    is_active: a?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      if (a) await apiPut(`/allowances/${a.id}/`, f);
      else await apiPost("/allowances/", f);
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
      <div className="card" style={{ padding: 24, maxWidth: 480,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{a ? a.name_ar : L("newTitle")}</h3>

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
          {!a && (
            <label className="field" style={{ width: 130 }}>
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
        </div>

        <div className="row" style={{ gap: 12, marginTop: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("mode")}</span>
            <select className="select" value={f.mode}
                    onChange={(e) => setF({ ...f, mode: e.target.value })}>
              {modes.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </label>
          <label className="field" style={{ width: 140 }}>
            <span className="label">
              {f.mode === "cap" ? L("cap") : L("amount")}
            </span>
            <input className="input num" type="number" min={0} step="0.01"
                   value={f.amount}
                   onChange={(e) => setF({ ...f,
                     amount: e.target.value })} />
          </label>
        </div>
        <div className="muted" style={{ fontSize: ".78rem", marginTop: 4 }}>
          {L("modeHint")}
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("descr")}</span>
          <input className="input" value={f.description}
                 onChange={(e) => setF({ ...f,
                   description: e.target.value })} />
        </label>

        <label className="row" style={{ gap: 8, marginTop: 14,
                                        cursor: "pointer" }}>
          <input type="checkbox" checked={f.requires_attachment}
                 onChange={(e) => setF({ ...f,
                   requires_attachment: e.target.checked })} />
          <span>{L("attach")}</span>
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim() || !f.amount
                            || (!a && !f.code)}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


/* ══ نافذة الاستحقاق ══ */

function EligibilityDialog({ a, L, onClose, onChanged }: {
  a: Allowance;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [rows, setRows] = useState<Eligible[]>([]);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [pick, setPick] = useState("");
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [e, d] = await Promise.all([
        apiGet<Eligible[]>(`/allowances/${a.id}/eligibility/`),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setRows(e);
      setPeers(d.rows);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : String(e2));
    } finally { setBusy(false); }
  }, [a.id]);

  useEffect(() => { load(); }, [load]);

  const assign = async () => {
    if (!pick) return;
    setErr("");
    try {
      await apiPost(`/allowances/${a.id}/eligibility/`, {
        employment_id: Number(pick),
        custom_amount: custom || undefined,
      });
      setPick(""); setCustom("");
      await load();
      await onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };

  const drop = async (id: number) => {
    try {
      await apiDelete(`/allowances/${a.id}/eligibility/`,
                      { employment_id: id });
      await load();
      await onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };

  const assigned = new Set(rows.map((r) => r.employment_id));

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 560,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{a.name_ar} — {L("assign")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="row" style={{ gap: 8, marginTop: 16,
                                      alignItems: "flex-end" }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("addEmployee")}</span>
            <select className="select" value={pick}
                    onChange={(e) => setPick(e.target.value)}>
              <option value="">—</option>
              {peers.filter((p) => !assigned.has(p.employment_id))
                .map((p) => (
                  <option key={p.employment_id} value={p.employment_id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field" style={{ width: 130 }}>
            <span className="label">{L("customAmount")}</span>
            <input className="input num" type="number" min={0}
                   placeholder={a.amount} value={custom}
                   onChange={(e) => setCustom(e.target.value)} />
          </label>
          <button className="btn btn-primary" disabled={!pick}
                  onClick={assign} style={{ marginBottom: 2 }}>+</button>
        </div>

        <div style={{ marginTop: 16 }}>
          {busy ? (
            <div className="muted">{L("loading")}</div>
          ) : rows.length === 0 ? (
            <div className="muted" style={{ padding: "18px 0",
                                            textAlign: "center" }}>
              {L("noneEligible")}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("employee")}</th>
                  <th style={{ width: 130 }}>{L("dept")}</th>
                  <th style={{ width: 110 }}>{L("amount")}</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.employment_id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.name}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>
                        {r.employee_no}
                      </div>
                    </td>
                    <td className="muted">{r.department || "—"}</td>
                    <td>
                      <span className="num">
                        {r.custom_amount || a.amount}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-sm btn-ghost"
                              onClick={() => drop(r.employment_id)}>
                        {L("remove")}
                      </button>
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

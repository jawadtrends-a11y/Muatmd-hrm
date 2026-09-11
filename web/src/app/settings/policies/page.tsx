"use client";
/**
 * إدارة السياسات (ق-129).
 *
 * ⚠️ **ولوحةُ من أقرّ ومن لم يُقرّ** — فسياسةٌ نُشرت ولا يُعرف
 * من قرأها بلا فائدة.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "السياسات", en: "Policies" },
  sub: {
    ar: "اكتبها وانشرها — وتابع من أقرّ بها",
    en: "Write, publish, and track acknowledgements",
  },
  add: { ar: "سياسة جديدة", en: "New policy" },
  name: { ar: "العنوان", en: "Title" },
  version: { ar: "النسخة", en: "Version" },
  effective: { ar: "سريان من", en: "Effective" },
  audience: { ar: "الفئة", en: "Audience" },
  state: { ar: "الحالة", en: "State" },
  published: { ar: "منشورة", en: "Published" },
  draft: { ar: "مسودّة", en: "Draft" },
  publish: { ar: "نشر", en: "Publish" },
  compliance: { ar: "الإقرارات", en: "Acks" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  close: { ar: "إغلاق", en: "Close" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "السياسات غير متاحة في باقتكم", en: "Not in your plan" },
  empty: { ar: "لم تكتب سياسة بعد", en: "No policies yet" },
  code: { ar: "الرمز", en: "Code" },
  body: { ar: "نصّ السياسة", en: "Body" },
  requiresAck: { ar: "يلزمه إقرار", en: "Requires acknowledgement" },
  ackHint: {
    ar: "مطفأ = تُنشر للاطّلاع بلا توقيع",
    en: "Off = published for information only",
  },
  newTitle: { ar: "سياسة جديدة", en: "New policy" },
  bumpWarn: {
    ar: "⚠️ تعديل النصّ بعد النشر يرفع النسخة ويُبطل الإقرارات",
    en: "Editing after publish bumps the version and resets acks",
  },
  acked: { ar: "أقرّوا", en: "Acknowledged" },
  pending: { ar: "لم يُقرّوا", en: "Pending" },
  rate: { ar: "النسبة", en: "Rate" },
  employee: { ar: "الموظف", en: "Employee" },
  dept: { ar: "الإدارة", en: "Department" },
  savedOk: { ar: "حُفظت", en: "Saved" },
  publishedOk: { ar: "نُشرت السياسة", en: "Policy published" },
};

type Policy = {
  id: number; code: string; title_ar: string; body_ar: string;
  version: number; effective_from: string;
  audience: string; audience_label: string;
  requires_ack: boolean; is_published: boolean;
};
type Audience = { value: string; label: string };
type Compliance = {
  version: number; total: number; acknowledged: number; pending: number;
  rate: number;
  done_rows: { employment_id: number; employee_no: string;
               name: string; department: string }[];
  pending_rows: { employment_id: number; employee_no: string;
                  name: string; department: string }[];
};

export default function PoliciesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Policy[]>([]);
  const [auds, setAuds] = useState<Audience[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Policy | null>(null);
  const [adding, setAdding] = useState(false);
  const [comp, setComp] = useState<{ policy: Policy;
                                     data: Compliance } | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ policies: Policy[]; audiences: Audience[] }>(
        "/policies/");
      setRows(d.policies);
      setAuds(d.audiences);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    setActing(true); setErr("");
    try {
      await fn();
      if (ok) { setMsg(ok); setTimeout(() => setMsg(""), 4000); }
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const showCompliance = async (p: Policy) => {
    setErr("");
    try {
      setComp({ policy: p,
                data: await apiGet<Compliance>(
                  `/policies/${p.id}/compliance/`) });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
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
                  <th style={{ width: 80 }}>{L("version")}</th>
                  <th style={{ width: 115 }}>{L("effective")}</th>
                  <th style={{ width: 130 }}>{L("audience")}</th>
                  <th style={{ width: 95 }}>{L("state")}</th>
                  <th style={{ width: 230 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{p.title_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".76rem" }}>{p.code}</div>
                    </td>
                    <td><span className="num">{p.version}</span></td>
                    <td><span className="num">{p.effective_from}</span></td>
                    <td className="muted">{p.audience_label}</td>
                    <td>
                      <span className={`badge ${p.is_published ? "badge-ok" : ""}`}>
                        {p.is_published ? L("published") : L("draft")}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        {!p.is_published && (
                          <button className="btn btn-sm btn-primary"
                                  disabled={acting}
                                  onClick={() => act(
                                    () => apiPost(
                                      `/policies/${p.id}/publish/`, {}),
                                    L("publishedOk"))}>
                            {L("publish")}
                          </button>
                        )}
                        {p.is_published && p.requires_ack && (
                          <button className="btn btn-sm"
                                  onClick={() => showCompliance(p)}>
                            {L("compliance")}
                          </button>
                        )}
                        <button className="btn btn-sm"
                                onClick={() => { setEditing(p);
                                                 setErr(""); }}>
                          {L("edit")}
                        </button>
                        <button className="btn btn-sm btn-danger"
                                disabled={acting}
                                onClick={() => act(
                                  () => apiDelete(`/policies/${p.id}/`))}>
                          {L("del")}
                        </button>
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
        <PolicyDialog policy={editing} auds={auds} L={L}
                      onClose={() => { setEditing(null); setAdding(false); }}
                      onSaved={async () => {
                        setEditing(null); setAdding(false);
                        setMsg(L("savedOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}

      {comp && (
        <ComplianceDialog info={comp} L={L}
                          onClose={() => setComp(null)} />
      )}
    </div>
  );
}


/* ══ نافذة السياسة ══ */

function PolicyDialog({ policy, auds, L, onClose, onSaved }: {
  policy: Policy | null;
  auds: Audience[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: policy?.code || "",
    title_ar: policy?.title_ar || "",
    body_ar: policy?.body_ar || "",
    effective_from: policy?.effective_from
      || new Date().toISOString().slice(0, 10),
    audience: policy?.audience || "all",
    requires_ack: policy?.requires_ack ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const bodyChanged = policy && f.body_ar !== policy.body_ar;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      if (policy) await apiPut(`/policies/${policy.id}/`, f);
      else await apiPost("/policies/", f);
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
      <div className="card" style={{ padding: 24, maxWidth: 640,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>
          {policy ? policy.title_ar : L("newTitle")}
        </h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        {policy?.is_published && bodyChanged && (
          <div style={{ background: "var(--copper-soft)",
                        color: "var(--copper)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".84rem", marginTop: 14 }}>
            {L("bumpWarn")}
          </div>
        )}

        <div className="row" style={{ gap: 12, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {!policy && (
            <label className="field" style={{ minWidth: 150 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={f.code}
                     onChange={(e) => setF({ ...f,
                       code: e.target.value.trim().toUpperCase() })} />
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 200 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.title_ar}
                   onChange={(e) => setF({ ...f,
                     title_ar: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 12, marginTop: 12,
                                      flexWrap: "wrap" }}>
          <div className="field" style={{ minWidth: 160 }}>
            <label className="label">{L("effective")}</label>
            <DateField value={f.effective_from}
                       onChange={(v) => setF({ ...f, effective_from: v })} />
          </div>
          <label className="field" style={{ minWidth: 170 }}>
            <span className="label">{L("audience")}</span>
            <select className="select" value={f.audience}
                    onChange={(e) => setF({ ...f,
                      audience: e.target.value })}>
              {auds.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="field" style={{ marginTop: 14 }}>
          <span className="label">{L("body")}</span>
          <textarea className="input" rows={10} value={f.body_ar}
                    onChange={(e) => setF({ ...f,
                      body_ar: e.target.value })} />
        </label>

        <label className="row" style={{ gap: 8, marginTop: 12,
                                        cursor: "pointer",
                                        alignItems: "flex-start" }}>
          <input type="checkbox" checked={f.requires_ack}
                 style={{ marginTop: 3 }}
                 onChange={(e) => setF({ ...f,
                   requires_ack: e.target.checked })} />
          <span>
            {L("requiresAck")}
            <div className="muted" style={{ fontSize: ".78rem" }}>
              {L("ackHint")}
            </div>
          </span>
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.title_ar.trim() || !f.body_ar.trim()
                            || (!policy && !f.code)}
                  onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


/* ══ لوحة الإقرارات ══ */

function ComplianceDialog({ info, L, onClose }: {
  info: { policy: Policy; data: Compliance };
  L: (k: string, f?: string) => string;
  onClose: () => void;
}) {
  const { policy, data } = info;
  const [tab, setTab] = useState<"pending" | "done">("pending");
  const list = tab === "pending" ? data.pending_rows : data.done_rows;

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
        <h3 style={{ margin: 0 }}>{policy.title_ar}</h3>
        <div className="muted" style={{ fontSize: ".82rem", marginTop: 4 }}>
          {L("version")} <span className="num">{data.version}</span>
        </div>

        <div className="row" style={{ gap: 16, marginTop: 16,
                                      flexWrap: "wrap" }}>
          <Stat label={L("acked")} value={data.acknowledged}
                tone="var(--ok)" />
          <Stat label={L("pending")} value={data.pending}
                tone="var(--copper)" />
          <Stat label={L("rate")} value={`${data.rate}%`} />
        </div>

        <div className="row" style={{ gap: 6, marginTop: 18 }}>
          <button className={`btn btn-sm ${tab === "pending" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab("pending")}>
            {L("pending")}
          </button>
          <button className={`btn btn-sm ${tab === "done" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab("done")}>
            {L("acked")}
          </button>
        </div>

        <div style={{ marginTop: 12, maxHeight: "40vh",
                      overflowY: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>{L("employee")}</th>
                <th style={{ width: 160 }}>{L("dept")}</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.employment_id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{r.name}</div>
                    <div className="muted num"
                         style={{ fontSize: ".76rem" }}>{r.employee_no}</div>
                  </td>
                  <td className="muted">{r.department || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <button className="btn" style={{ marginTop: 16 }}
                onClick={onClose}>{L("close")}</button>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: {
  label: string; value: number | string; tone?: string;
}) {
  return (
    <div>
      <div className="muted" style={{ fontSize: ".78rem" }}>{label}</div>
      <div className="num" style={{ fontSize: "1.4rem", fontWeight: 600,
                                    color: tone }}>{value}</div>
    </div>
  );
}

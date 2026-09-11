"use client";
/**
 * المهامّ (ق-131).
 *
 * **تُسنَد وتُتابَع** — لا رسالةً تضيع في محادثة.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "المهامّ", en: "Tasks" },
  sub: { ar: "ما عليك وما أسندتَه", en: "Yours and what you assigned" },
  mine: { ar: "عليّ", en: "Mine" },
  assigned: { ar: "أسندتُها", en: "I assigned" },
  team: { ar: "فريقي", en: "Team" },
  add: { ar: "مهمّة جديدة", en: "New task" },
  task: { ar: "المهمّة", en: "Task" },
  assignee: { ar: "المسنَد إليه", en: "Assignee" },
  due: { ar: "الاستحقاق", en: "Due" },
  priority: { ar: "الأولوية", en: "Priority" },
  state: { ar: "الحالة", en: "Status" },
  start: { ar: "بدء", en: "Start" },
  done: { ar: "إنجاز", en: "Complete" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  save: { ar: "حفظ", en: "Save" },
  close: { ar: "إغلاق", en: "Close" },
  overdue: { ar: "متأخّرة", en: "Overdue" },
  empty: { ar: "لا مهامّ", en: "No tasks" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "المهامّ غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "مهمّة جديدة", en: "New task" },
  details: { ar: "التفاصيل", en: "Details" },
  pickAssignee: { ar: "اختر الموظف", en: "Pick employee" },
  savedOk: { ar: "حُفظت", en: "Saved" },
};

type Task = {
  id: number; title: string; description: string;
  assignee_id: number; assignee: string; assigned_by: string;
  due_date: string | null;
  priority: string; priority_label: string;
  status: string; status_label: string; overdue: boolean;
};
type Peer = { employment_id: number; name: string; job_title: string };

const TONE: Record<string, string> = {
  urgent: "badge-danger", high: "badge-warn",
  normal: "badge", low: "badge",
};

export default function TasksPage() {
  const { L } = useT(T);
  const [scope, setScope] = useState<"mine" | "assigned" | "team">("mine");
  const [rows, setRows] = useState<Task[]>([]);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [t, d] = await Promise.all([
        apiGet<Task[]>(`/tasks/?scope=${scope}`),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setRows(t);
      setPeers(d.rows);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [scope]);

  useEffect(() => { load(); }, [load]);

  const setStatus = async (t: Task, status: string) => {
    setActing(true); setErr("");
    try {
      await apiPut(`/tasks/${t.id}/`, { status });
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

      <div className="row" style={{ gap: 6 }}>
        {(["mine", "assigned", "team"] as const).map((s) => (
          <button key={s}
                  className={`btn btn-sm ${scope === s ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setScope(s)}>{L(s)}</button>
        ))}
      </div>

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
                  <th>{L("task")}</th>
                  <th style={{ width: 150 }}>{L("assignee")}</th>
                  <th style={{ width: 125 }}>{L("due")}</th>
                  <th style={{ width: 95 }}>{L("priority")}</th>
                  <th style={{ width: 110 }}>{L("state")}</th>
                  <th style={{ width: 150 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{t.title}</div>
                      {t.description && (
                        <div className="muted truncate"
                             style={{ fontSize: ".78rem", maxWidth: 320 }}>
                          {t.description}
                        </div>
                      )}
                    </td>
                    <td className="muted">{t.assignee}</td>
                    <td>
                      {t.due_date ? (
                        <span className="num"
                              style={t.overdue
                                ? { color: "var(--danger)" } : undefined}>
                          {t.due_date}
                          {t.overdue && ` — ${L("overdue")}`}
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      <span className={`badge ${TONE[t.priority] || "badge"}`}>
                        {t.priority_label}
                      </span>
                    </td>
                    <td className="muted">{t.status_label}</td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        {t.status === "open" && (
                          <button className="btn btn-sm" disabled={acting}
                                  onClick={() => setStatus(t, "in_progress")}>
                            {L("start")}
                          </button>
                        )}
                        {t.status !== "done" && (
                          <button className="btn btn-sm btn-primary"
                                  disabled={acting}
                                  onClick={() => setStatus(t, "done")}>
                            {L("done")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding && (
        <TaskDialog peers={peers} L={L}
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


function TaskDialog({ peers, L, onClose, onSaved }: {
  peers: Peer[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    title: "", description: "", assignee_id: "",
    due_date: "", priority: "normal",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/tasks/", {
        ...f,
        assignee_id: f.assignee_id ? Number(f.assignee_id) : undefined,
        due_date: f.due_date || undefined,
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
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 480,
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
            <span className="label">{L("task")}</span>
            <input className="input" value={f.title} autoFocus
                   onChange={(e) => setF({ ...f, title: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("details")}</span>
            <textarea className="input" rows={3} value={f.description}
                      onChange={(e) => setF({ ...f,
                        description: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("assignee")}</span>
            <select className="select" value={f.assignee_id}
                    onChange={(e) => setF({ ...f,
                      assignee_id: e.target.value })}>
              <option value="">{L("pickAssignee")}</option>
              {peers.map((p) => (
                <option key={p.employment_id} value={p.employment_id}>
                  {p.name}{p.job_title ? ` — ${p.job_title}` : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="row" style={{ gap: 12 }}>
            <div className="field" style={{ flex: 1 }}>
              <label className="label">{L("due")}</label>
              <DateField value={f.due_date}
                         onChange={(v) => setF({ ...f, due_date: v })} />
            </div>
            <label className="field" style={{ width: 140 }}>
              <span className="label">{L("priority")}</span>
              <select className="select" value={f.priority}
                      onChange={(e) => setF({ ...f,
                        priority: e.target.value })}>
                <option value="low">منخفضة</option>
                <option value="normal">عادية</option>
                <option value="high">عالية</option>
                <option value="urgent">عاجلة</option>
              </select>
            </label>
          </div>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.title.trim()} onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("close")}</button>
        </div>
      </div>
    </div>
  );
}

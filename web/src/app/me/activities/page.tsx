"use client";
/**
 * أنشطتي اليومية (ق-143).
 *
 * ⚠️ **وما ينتظر إقراري أوّلًا** — فالشاشة عملٌ ينتظر لا سجلٌّ
 * يُقرأ.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أنشطتي", en: "My activities" },
  sub: {
    ar: "ما طُلب منك — وما ينتظر إقرارك أوّلًا",
    en: "What's assigned to you — pending first",
  },
  day: { ar: "اليوم", en: "Day" },
  activity: { ar: "النشاط", en: "Activity" },
  target: { ar: "المستهدَف", en: "Target" },
  state: { ar: "الحالة", en: "Status" },
  report: { ar: "إقرار", en: "Report" },
  empty: { ar: "لا أنشطة", en: "No activities" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "أنشطة العمل غير متاحة", en: "Not available" },
  reportTitle: { ar: "إقرار النشاط", en: "Report activity" },
  doneCount: { ar: "العدد المنجَز", en: "Completed" },
  doneNote: { ar: "ما أُنجز", en: "What was done" },
  pendingNote: { ar: "ما لم يُنجَز وسببه", en: "What wasn't, and why" },
  pendingHint: {
    ar: "⚠️ بيّنه — فالمدير يعرف العائق لا الرقم وحده",
    en: "Explain it — your manager needs the blocker",
  },
  save: { ar: "حفظ الإقرار", en: "Submit" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  savedOk: { ar: "سُجّل إقرارك", en: "Reported" },
  reviewed: { ar: "رُوجع", en: "Reviewed" },
  amount: { ar: "المعتمَد", en: "Settled" },
  of: { ar: "من", en: "of" },
};

type Activity = {
  id: number; work_date: string; title: string; description: string;
  target_count: number | null; unit: string;
  status: string; status_label: string;
  done_count: number | null; done_note: string; pending_note: string;
  achievement: number | null;
  is_reviewed: boolean; settled_amount: string | null;
};
type Opt = { value: string; label: string };

const TONE: Record<string, string> = {
  pending: "badge-warn", done: "badge-ok",
  partial: "badge", not_done: "badge-danger",
};

export default function MyActivitiesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Activity[]>([]);
  const [statuses, setStatuses] = useState<Opt[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [reporting, setReporting] = useState<Activity | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ activities: Activity[];
                               statuses: Opt[] }>("/me/activities/");
      setRows(d.activities);
      setStatuses(d.statuses);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

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
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
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
                  <th style={{ width: 115 }}>{L("day")}</th>
                  <th>{L("activity")}</th>
                  <th style={{ width: 130 }}>{L("target")}</th>
                  <th style={{ width: 140 }}>{L("state")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td><span className="num">{a.work_date}</span></td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{a.title}</div>
                      {a.description && (
                        <div className="muted"
                             style={{ fontSize: ".76rem" }}>
                          {a.description}
                        </div>
                      )}
                      {a.pending_note && (
                        <div style={{ fontSize: ".76rem",
                                      color: "var(--copper)" }}>
                          {a.pending_note}
                        </div>
                      )}
                    </td>
                    <td>
                      {a.target_count ? (
                        <span>
                          <span className="num">
                            {a.done_count ?? "—"}
                          </span>
                          {" "}{L("of")}{" "}
                          <span className="num">{a.target_count}</span>
                          {a.unit && (
                            <span className="muted"
                                  style={{ fontSize: ".76rem" }}>
                              {" "}{a.unit}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${TONE[a.status] || "badge"}`}>
                        {a.status_label}
                      </span>
                      {a.is_reviewed && (
                        <div className="muted"
                             style={{ fontSize: ".74rem", marginTop: 3 }}>
                          {L("reviewed")}
                          {a.settled_amount && a.settled_amount !== "0.00"
                            && ` — ${a.settled_amount}`}
                        </div>
                      )}
                    </td>
                    <td>
                      {a.status === "pending" && (
                        <button className="btn btn-sm btn-primary"
                                onClick={() => setReporting(a)}>
                          {L("report")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {reporting && (
        <ReportDialog a={reporting} statuses={statuses} L={L}
                      onClose={() => setReporting(null)}
                      onSaved={async () => {
                        setReporting(null);
                        setMsg(L("savedOk"));
                        setTimeout(() => setMsg(""), 3500);
                        await load();
                      }} />
      )}
    </div>
  );
}


function ReportDialog({ a, statuses, L, onClose, onSaved }: {
  a: Activity;
  statuses: Opt[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [st, setSt] = useState("done");
  const [doneCount, setDoneCount] = useState(
    a.target_count ? String(a.target_count) : "");
  const [doneNote, setDoneNote] = useState("");
  const [pendingNote, setPendingNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const needsPending = st === "partial" || st === "not_done";
  const needsDone = st === "partial";

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/activities/${a.id}/report/`, {
        status: st,
        done_count: a.target_count ? Number(doneCount) : undefined,
        done_note: doneNote,
        pending_note: pendingNote,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("reportTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {a.title} — <span className="num">{a.work_date}</span>
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="row" style={{ gap: 6, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {statuses.map((s) => (
            <button key={s.value} type="button"
                    className={`btn btn-sm ${st === s.value ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setSt(s.value)}>
              {s.label}
            </button>
          ))}
        </div>

        {a.target_count !== null && (
          <label className="field" style={{ marginTop: 14, width: 160 }}>
            <span className="label">{L("doneCount")}</span>
            <input className="input num" type="number" min={0}
                   value={doneCount}
                   onChange={(e) => setDoneCount(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("of")} {a.target_count} {a.unit}
            </span>
          </label>
        )}

        {(needsDone || st === "done") && (
          <label className="field" style={{ marginTop: 12 }}>
            <span className="label">
              {L("doneNote")}
              {needsDone && <span style={{ color: "var(--danger)" }}> *</span>}
            </span>
            <textarea className="input" rows={2} value={doneNote}
                      onChange={(e) => setDoneNote(e.target.value)} />
          </label>
        )}

        {needsPending && (
          <label className="field" style={{ marginTop: 12 }}>
            <span className="label">
              {L("pendingNote")}
              <span style={{ color: "var(--danger)" }}> *</span>
            </span>
            <textarea className="input" rows={3} value={pendingNote}
                      onChange={(e) => setPendingNote(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("pendingHint")}
            </span>
          </label>
        )}

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || (needsPending && !pendingNote.trim())
                            || (needsDone && !doneNote.trim())}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

"use client";
/**
 * تدريبي (ق-149).
 *
 * ⚠️ **والمتوفّر يُرشَّح له لا يُطلَب** — فالطلب لغير المتاح.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تدريبي", en: "My training" },
  sub: {
    ar: "دوراتي، والمتاح، وطلب دورةٍ غير متوفّرة",
    en: "My courses, what's available, and requesting more",
  },
  budget: { ar: "ميزانية التدريب", en: "Training budget" },
  used: { ar: "المستعمل", en: "Used" },
  remaining: { ar: "المتبقّي", en: "Remaining" },
  unlimited: { ar: "بلا سقف محدَّد", en: "No set limit" },
  myCourses: { ar: "دوراتي", en: "My courses" },
  available: { ar: "الدورات المتاحة", en: "Available courses" },
  myRequests: { ar: "طلباتي", en: "My requests" },
  course: { ar: "الدورة", en: "Course" },
  provider: { ar: "الجهة", en: "Provider" },
  date: { ar: "الموعد", en: "Date" },
  state: { ar: "الحالة", en: "Status" },
  score: { ar: "الدرجة", en: "Score" },
  certificate: { ar: "الشهادة", en: "Certificate" },
  duration: { ar: "المدّة", en: "Duration" },
  hours: { ar: "ساعة", en: "h" },
  cost: { ar: "التكلفة", en: "Cost" },
  askFor: { ar: "طلب دورة غير متوفّرة", en: "Request a course" },
  askHint: {
    ar: "⚠️ المتوفّرة أعلاه تُطلب من مديرك ترشيحك لها — وهذا لغيرها",
    en: "Available courses are nominated by your manager",
  },
  courseName: { ar: "اسم الدورة", en: "Course name" },
  estCost: { ar: "التكلفة التقديرية", en: "Estimated cost" },
  link: { ar: "رابط الدورة", en: "Course link" },
  why: { ar: "مبرّر الطلب", en: "Justification" },
  whyHint: {
    ar: "⚠️ إلزاميّ — فطلبٌ بلا مبرّر لا يُدرَس",
    en: "Required — requests without justification aren't reviewed",
  },
  send: { ar: "إرسال الطلب", en: "Send" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا شيء بعد", en: "Nothing yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "التدريب غير متاح", en: "Not available" },
  sentOk: { ar: "أُرسل طلبك", en: "Request sent" },
};

type Nom = {
  id: number; course: string; provider: string;
  scheduled_on: string | null; state: string; state_label: string;
  score: string | null; passed: boolean | null;
  certificate_url: string; completed_on: string | null;
};
type Req = {
  id: number; course_name: string; estimated_cost: string | null;
  justification: string; state: string; state_label: string;
  decision_note: string;
};
type Course = {
  id: number; name_ar: string; provider: string;
  duration_hours: number | null; cost: string | null;
  delivery_label: string;
};

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok",
  rejected: "badge-danger", attended: "badge-ok",
  no_show: "badge-danger",
};

export default function MyTrainingPage() {
  const { L } = useT(T);
  const [data, setData] = useState<{
    nominations: Nom[]; requests: Req[]; available: Course[];
    budget: { budget: string | null; used: string;
              remaining: string | null; unlimited: boolean } } | null>(
    null);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [asking, setAsking] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setData(await apiGet("/me/training/"));
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

  const b = data?.budget;

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
                onClick={() => setAsking(true)}>{L("askFor")}</button>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      {/* ⚠️ والميزانية تُعرض — فبلا سقفٍ ليست صفرًا */}
      <div className="card" style={{ padding: 18 }}>
        <div className="spread">
          <strong style={{ fontSize: ".92rem" }}>{L("budget")}</strong>
          {b?.unlimited ? (
            <span className="muted" style={{ fontSize: ".85rem" }}>
              {L("unlimited")}
            </span>
          ) : (
            <div className="row" style={{ gap: 20 }}>
              <div style={{ textAlign: "center" }}>
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("used")}
                </div>
                <div className="num">{b?.used}</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("remaining")}
                </div>
                <div className="num" style={{
                  color: Number(b?.remaining || 0) <= 0
                    ? "var(--danger)" : "var(--ok)" }}>
                  {b?.remaining}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <h3 style={{ fontSize: "1rem", marginTop: 6 }}>{L("myCourses")}</h3>
      <div className="card" style={{ overflow: "hidden" }}>
        {!data?.nominations.length ? (
          <Empty L={L} />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{L("course")}</th>
                <th style={{ width: 115 }}>{L("date")}</th>
                <th style={{ width: 130 }}>{L("state")}</th>
                <th style={{ width: 110 }} />
              </tr>
            </thead>
            <tbody>
              {data.nominations.map((n) => (
                <tr key={n.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{n.course}</div>
                    {n.provider && (
                      <div className="muted" style={{ fontSize: ".76rem" }}>
                        {n.provider}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="num">{n.scheduled_on || "—"}</span>
                  </td>
                  <td>
                    <span className={`badge ${TONE[n.state] || "badge"}`}>
                      {n.state_label}
                    </span>
                    {n.score && (
                      <div className="num" style={{ fontSize: ".75rem",
                                                    marginTop: 3 }}>
                        {L("score")}: {n.score}
                      </div>
                    )}
                  </td>
                  <td>
                    {n.certificate_url && (
                      <a className="btn btn-sm btn-ghost"
                         href={n.certificate_url} target="_blank"
                         rel="noreferrer">{L("certificate")}</a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h3 style={{ fontSize: "1rem", marginTop: 6 }}>{L("available")}</h3>
      <div className="card" style={{ overflow: "hidden" }}>
        {!data?.available.length ? (
          <Empty L={L} />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{L("course")}</th>
                <th style={{ width: 140 }}>{L("provider")}</th>
                <th style={{ width: 100 }}>{L("duration")}</th>
                <th style={{ width: 100 }}>{L("cost")}</th>
              </tr>
            </thead>
            <tbody>
              {data.available.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 500 }}>{c.name_ar}</td>
                  <td className="muted">{c.provider || "—"}</td>
                  <td>
                    {c.duration_hours
                      ? <span className="num">
                          {c.duration_hours} {L("hours")}
                        </span>
                      : <span className="muted">—</span>}
                  </td>
                  <td>
                    {c.cost
                      ? <span className="num">{c.cost}</span>
                      : <span className="muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!!data?.requests.length && (
        <>
          <h3 style={{ fontSize: "1rem", marginTop: 6 }}>
            {L("myRequests")}
          </h3>
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("course")}</th>
                  <th style={{ width: 120 }}>{L("estCost")}</th>
                  <th style={{ width: 130 }}>{L("state")}</th>
                </tr>
              </thead>
              <tbody>
                {data.requests.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {r.course_name}
                      </div>
                      {r.decision_note && (
                        <div className="muted"
                             style={{ fontSize: ".75rem" }}>
                          {r.decision_note}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="num">
                        {r.estimated_cost || "—"}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${TONE[r.state] || "badge"}`}>
                        {r.state_label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {asking && (
        <RequestDialog L={L} onClose={() => setAsking(false)}
                       onSaved={async () => {
                         setAsking(false);
                         setMsg(L("sentOk"));
                         setTimeout(() => setMsg(""), 4000);
                         await load();
                       }} />
      )}
    </div>
  );
}


function Empty({ L }: { L: (k: string) => string }) {
  return (
    <div style={{ padding: 32, textAlign: "center",
                  color: "var(--ink-3)" }}>
      <IcDoc size={20} />
      <div style={{ marginTop: 8 }}>{L("empty")}</div>
    </div>
  );
}


function RequestDialog({ L, onClose, onSaved }: {
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    course_name: "", provider: "", estimated_cost: "",
    justification: "", reference_url: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/training/requests/", {
        ...f, estimated_cost: f.estimated_cost || undefined,
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
      <div className="card" style={{ padding: 24, maxWidth: 460,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("askFor")}</h3>
        <div className="muted" style={{ fontSize: ".82rem", marginTop: 4,
                                        lineHeight: 1.8 }}>
          {L("askHint")}
        </div>

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
            <span className="label">{L("courseName")}</span>
            <input className="input" value={f.course_name}
                   onChange={(e) => setF({ ...f,
                     course_name: e.target.value })} />
          </label>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ flex: 1 }}>
              <span className="label">{L("provider")}</span>
              <input className="input" value={f.provider}
                     onChange={(e) => setF({ ...f,
                       provider: e.target.value })} />
            </label>
            <label className="field" style={{ width: 140 }}>
              <span className="label">{L("estCost")}</span>
              <input className="input num" type="number" min={0}
                     value={f.estimated_cost}
                     onChange={(e) => setF({ ...f,
                       estimated_cost: e.target.value })} />
            </label>
          </div>

          <label className="field">
            <span className="label">{L("link")}</span>
            <input className="input" dir="ltr" value={f.reference_url}
                   placeholder="https://…"
                   onChange={(e) => setF({ ...f,
                     reference_url: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">
              {L("why")}
              <span style={{ color: "var(--danger)" }}> *</span>
            </span>
            <textarea className="input" rows={3} value={f.justification}
                      onChange={(e) => setF({ ...f,
                        justification: e.target.value })} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("whyHint")}
            </span>
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.course_name.trim()
                            || !f.justification.trim()}
                  onClick={submit}>{busy ? "…" : L("send")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}

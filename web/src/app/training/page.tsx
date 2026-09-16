"use client";
/**
 * التدريب والدورات (ق-149).
 *
 * ⚠️ **والترشيح يُعتمد من الموارد** — فترشيحٌ بلا مراجعة يصرف
 * ميزانيةً بلا ضابط.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "التدريب والدورات", en: "Training" },
  sub: {
    ar: "الدورات المتاحة، والترشيحات، وطلبات الموظفين",
    en: "Courses, nominations and employee requests",
  },
  tabCourses: { ar: "الدورات", en: "Courses" },
  tabNoms: { ar: "الترشيحات", en: "Nominations" },
  tabReqs: { ar: "طلبات الموظفين", en: "Requests" },
  addCourse: { ar: "دورة جديدة", en: "New course" },
  nominate: { ar: "ترشيح موظف", en: "Nominate" },
  name: { ar: "الدورة", en: "Course" },
  code: { ar: "الرمز", en: "Code" },
  provider: { ar: "الجهة", en: "Provider" },
  duration: { ar: "المدّة", en: "Duration" },
  hours: { ar: "ساعة", en: "h" },
  cost: { ar: "التكلفة", en: "Cost" },
  mode: { ar: "النمط", en: "Mode" },
  employee: { ar: "الموظف", en: "Employee" },
  scheduled: { ar: "الموعد", en: "Date" },
  state: { ar: "الحالة", en: "Status" },
  approve: { ar: "اعتماد", en: "Approve" },
  reject: { ar: "رفض", en: "Reject" },
  result: { ar: "النتيجة", en: "Result" },
  attended: { ar: "حضر", en: "Attended" },
  noShow: { ar: "لم يحضر", en: "No show" },
  score: { ar: "الدرجة", en: "Score" },
  certificate: { ar: "الشهادة", en: "Certificate" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا شيء بعد", en: "Nothing yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "التدريب غير متاح في باقتكم", en: "Not in your plan" },
  descr: { ar: "الوصف", en: "Description" },
  justification: { ar: "المبرّر", en: "Justification" },
  estCost: { ar: "التكلفة التقديرية", en: "Estimated cost" },
  addToCatalog: { ar: "إضافتها للدورات", en: "Add to catalog" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  doneOk: { ar: "سُجّل القرار", en: "Recorded" },
  budgetWarn: { ar: "تنبيه ميزانية", en: "Budget warning" },
  resultTitle: { ar: "تسجيل النتيجة", en: "Record result" },
  passed: { ar: "اجتاز", en: "Passed" },
  note: { ar: "ملاحظة", en: "Note" },
};

type Course = {
  id: number; code: string; name_ar: string; provider: string;
  description: string; duration_hours: number | null;
  cost: string | null; delivery_mode: string; delivery_label: string;
  is_active: boolean;
};
type Nom = {
  id: number; course: string; course_id: number; provider: string;
  employment_id: number; employee: string; employee_no: string;
  scheduled_on: string | null; cost: string | null;
  state: string; state_label: string; decision_note: string;
  score: string | null; passed: boolean | null;
  certificate_url: string; completed_on: string | null;
};
type Req = {
  id: number; course_name: string; provider: string;
  employee: string; estimated_cost: string | null;
  justification: string; reference_url: string;
  state: string; state_label: string; created_course_id: number | null;
};
type Opt = { value: string; label: string };
type Peer = { employment_id: number; name: string };

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok",
  rejected: "badge-danger", attended: "badge-ok",
  no_show: "badge-danger", cancelled: "badge",
};

export default function TrainingPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"courses" | "noms" | "reqs">("courses");
  const [courses, setCourses] = useState<Course[]>([]);
  const [noms, setNoms] = useState<Nom[]>([]);
  const [reqs, setReqs] = useState<Req[]>([]);
  const [warnings, setWarnings] = useState<Record<number, string>>({});
  const [modes, setModes] = useState<Opt[]>([]);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [dialog, setDialog] = useState<"course" | "nominate" | null>(null);
  const [editing, setEditing] = useState<Course | null>(null);
  const [resulting, setResulting] = useState<Nom | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [c, n, r, dir] = await Promise.all([
        apiGet<{ courses: Course[]; modes: Opt[] }>(
          "/training/courses/?active=0"),
        apiGet<{ nominations: Nom[];
                 budget_warnings: Record<number, string> }>(
          "/training/nominations/"),
        apiGet<{ requests: Req[] }>("/training/requests/"),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setCourses(c.courses);
      setModes(c.modes);
      setNoms(n.nominations);
      setWarnings(n.budget_warnings || {});
      setReqs(r.requests);
      setPeers(dir.rows);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = async (n: Nom, approve: boolean) => {
    setActing(true); setErr("");
    try {
      const note = approve ? "" : (prompt(L("reject")) || "");
      await apiPost(`/training/nominations/${n.id}/decide/`,
                    { approve, note });
      setMsg(L("doneOk"));
      setTimeout(() => setMsg(""), 3000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const decideReq = async (r: Req, approve: boolean) => {
    setActing(true); setErr("");
    try {
      const addIt = approve && confirm(L("addToCatalog"));
      const code = addIt ? (prompt(L("code")) || "") : "";
      await apiPost(`/training/requests/${r.id}/decide/`, {
        approve, create_course: addIt, code,
      });
      setMsg(L("doneOk"));
      setTimeout(() => setMsg(""), 3000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const removeCourse = async (c: Course) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ deactivated?: boolean;
                                    detail?: string }>(
        `/training/courses/${c.id}/`);
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
        {tab !== "reqs" && (
          <button className="btn btn-primary btn-sm"
                  onClick={() => setDialog(
                    tab === "courses" ? "course" : "nominate")}>
            {tab === "courses" ? L("addCourse") : L("nominate")}
          </button>
        )}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        {(["courses", "noms", "reqs"] as const).map((t) => (
          <button key={t}
                  className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab(t)}>
            {t === "courses" ? L("tabCourses")
              : t === "noms" ? L("tabNoms") : L("tabReqs")}
          </button>
        ))}
      </div>

      {tab === "courses" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {courses.length === 0 ? (
            <Empty L={L} />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 150 }}>{L("provider")}</th>
                  <th style={{ width: 100 }}>{L("duration")}</th>
                  <th style={{ width: 110 }}>{L("cost")}</th>
                  <th style={{ width: 110 }}>{L("mode")}</th>
                  <th style={{ width: 150 }} />
                </tr>
              </thead>
              <tbody>
                {courses.map((c) => (
                  <tr key={c.id} style={{ opacity: c.is_active ? 1 : .55 }}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{c.name_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".75rem" }}>{c.code}</div>
                    </td>
                    <td className="muted">{c.provider || "—"}</td>
                    <td>
                      {c.duration_hours
                        ? <span className="num">{c.duration_hours} {L("hours")}</span>
                        : <span className="muted">—</span>}
                    </td>
                    <td>
                      {c.cost
                        ? <span className="num">{c.cost}</span>
                        : <span className="muted">—</span>}
                    </td>
                    <td className="muted">{c.delivery_label}</td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm"
                                onClick={() => setEditing(c)}>
                          {L("edit")}
                        </button>
                        <button className="btn btn-sm btn-danger"
                                disabled={acting}
                                onClick={() => removeCourse(c)}>
                          {L("del")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "noms" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {noms.length === 0 ? (
            <Empty L={L} />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 170 }}>{L("employee")}</th>
                    <th>{L("name")}</th>
                    <th style={{ width: 115 }}>{L("scheduled")}</th>
                    <th style={{ width: 100 }}>{L("cost")}</th>
                    <th style={{ width: 130 }}>{L("state")}</th>
                    <th style={{ width: 175 }} />
                  </tr>
                </thead>
                <tbody>
                  {noms.map((n) => (
                    <tr key={n.id}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{n.employee}</div>
                        <div className="muted num"
                             style={{ fontSize: ".73rem" }}>
                          {n.employee_no}
                        </div>
                      </td>
                      <td>
                        <div>{n.course}</div>
                        {/* ⚠️ تنبيه الميزانية مع المعلَّق — فالقرار
                            على بصيرة */}
                        {warnings[n.id] && (
                          <div style={{ fontSize: ".74rem",
                                        color: "var(--copper)" }}>
                            {warnings[n.id]}
                          </div>
                        )}
                        {n.decision_note && (
                          <div className="muted"
                               style={{ fontSize: ".73rem" }}>
                            {n.decision_note}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="num">
                          {n.scheduled_on || "—"}
                        </span>
                      </td>
                      <td>
                        <span className="num">{n.cost || "—"}</span>
                      </td>
                      <td>
                        <span className={`badge ${TONE[n.state] || "badge"}`}>
                          {n.state_label}
                        </span>
                        {n.score && (
                          <div className="num"
                               style={{ fontSize: ".75rem",
                                        marginTop: 3 }}>
                            {L("score")}: {n.score}
                          </div>
                        )}
                      </td>
                      <td>
                        <div className="row" style={{ gap: 5 }}>
                          {n.state === "pending" && (
                            <>
                              <button className="btn btn-sm btn-primary"
                                      disabled={acting}
                                      onClick={() => decide(n, true)}>
                                {L("approve")}
                              </button>
                              <button className="btn btn-sm btn-danger"
                                      disabled={acting}
                                      onClick={() => decide(n, false)}>
                                {L("reject")}
                              </button>
                            </>
                          )}
                          {n.state === "approved" && (
                            <button className="btn btn-sm"
                                    onClick={() => setResulting(n)}>
                              {L("result")}
                            </button>
                          )}
                          {n.certificate_url && (
                            <a className="btn btn-sm btn-ghost"
                               href={n.certificate_url} target="_blank"
                               rel="noreferrer">
                              {L("certificate")}
                            </a>
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
      )}

      {tab === "reqs" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {reqs.length === 0 ? (
            <Empty L={L} />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 160 }}>{L("employee")}</th>
                  <th>{L("name")}</th>
                  <th style={{ width: 120 }}>{L("estCost")}</th>
                  <th style={{ width: 120 }}>{L("state")}</th>
                  <th style={{ width: 150 }} />
                </tr>
              </thead>
              <tbody>
                {reqs.map((r) => (
                  <tr key={r.id}>
                    <td className="muted">{r.employee}</td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.course_name}</div>
                      <div className="muted" style={{ fontSize: ".76rem" }}>
                        {r.justification}
                      </div>
                      {r.reference_url && (
                        <a href={r.reference_url} target="_blank"
                           rel="noreferrer"
                           style={{ fontSize: ".74rem" }}>
                          {r.provider || r.reference_url.slice(0, 40)}
                        </a>
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
                    <td>
                      {r.state === "pending" && (
                        <div className="row" style={{ gap: 5 }}>
                          <button className="btn btn-sm btn-primary"
                                  disabled={acting}
                                  onClick={() => decideReq(r, true)}>
                            {L("approve")}
                          </button>
                          <button className="btn btn-sm btn-danger"
                                  disabled={acting}
                                  onClick={() => decideReq(r, false)}>
                            {L("reject")}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {(dialog === "course" || editing) && (
        <CourseDialog c={editing} modes={modes} L={L}
                      onClose={() => { setDialog(null);
                                       setEditing(null); }}
                      onSaved={async () => {
                        setDialog(null); setEditing(null);
                        setMsg(L("savedOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}

      {dialog === "nominate" && (
        <NominateDialog courses={courses.filter((c) => c.is_active)}
                        peers={peers} L={L}
                        onClose={() => setDialog(null)}
                        onSaved={async (w) => {
                          setDialog(null);
                          setMsg(w || L("savedOk"));
                          setTimeout(() => setMsg(""), 5000);
                          await load();
                        }} />
      )}

      {resulting && (
        <ResultDialog n={resulting} L={L}
                      onClose={() => setResulting(null)}
                      onSaved={async () => {
                        setResulting(null);
                        setMsg(L("doneOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}
    </div>
  );
}


function Empty({ L }: { L: (k: string) => string }) {
  return (
    <div style={{ padding: 40, textAlign: "center",
                  color: "var(--ink-3)" }}>
      <IcDoc size={22} />
      <div style={{ marginTop: 8 }}>{L("empty")}</div>
    </div>
  );
}


function CourseDialog({ c, modes, L, onClose, onSaved }: {
  c: Course | null; modes: Opt[];
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: c?.code || "", name_ar: c?.name_ar || "",
    provider: c?.provider || "", description: c?.description || "",
    duration_hours: c?.duration_hours ? String(c.duration_hours) : "",
    cost: c?.cost || "", delivery_mode: c?.delivery_mode || "onsite",
    is_active: c?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = {
        ...f,
        duration_hours: f.duration_hours
          ? Number(f.duration_hours) : undefined,
        cost: f.cost || undefined,
      };
      if (c) await apiPut(`/training/courses/${c.id}/`, body);
      else await apiPost("/training/courses/", body);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{c ? c.name_ar : L("addCourse")}</h3>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="row" style={{ gap: 12, marginTop: 16,
                                    flexWrap: "wrap" }}>
        {!c && (
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
          <span className="label">{L("provider")}</span>
          <input className="input" value={f.provider}
                 onChange={(e) => setF({ ...f,
                   provider: e.target.value })} />
        </label>
        <label className="field" style={{ width: 130 }}>
          <span className="label">{L("mode")}</span>
          <select className="select" value={f.delivery_mode}
                  onChange={(e) => setF({ ...f,
                    delivery_mode: e.target.value })}>
            {modes.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="row" style={{ gap: 12, marginTop: 12 }}>
        <label className="field" style={{ width: 140 }}>
          <span className="label">{L("duration")} ({L("hours")})</span>
          <input className="input num" type="number" min={1}
                 value={f.duration_hours}
                 onChange={(e) => setF({ ...f,
                   duration_hours: e.target.value })} />
        </label>
        <label className="field" style={{ width: 150 }}>
          <span className="label">{L("cost")}</span>
          <input className="input num" type="number" min={0} step="0.01"
                 value={f.cost}
                 onChange={(e) => setF({ ...f, cost: e.target.value })} />
        </label>
      </div>

      <label className="field" style={{ marginTop: 12 }}>
        <span className="label">{L("descr")}</span>
        <textarea className="input" rows={2} value={f.description}
                  onChange={(e) => setF({ ...f,
                    description: e.target.value })} />
      </label>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!f.name_ar.trim() || (!c && !f.code)} />
    </Modal>
  );
}


function NominateDialog({ courses, peers, L, onClose, onSaved }: {
  courses: Course[]; peers: Peer[];
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: (warning?: string) => void;
}) {
  const [f, setF] = useState({
    employment_id: "", course_id: "",
    scheduled_on: new Date().toISOString().slice(0, 10),
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const course = courses.find((c) => String(c.id) === f.course_id);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const out = await apiPost<{ budget?: { exceeds: boolean;
                                             warning: string } }>(
        "/training/nominations/", {
          employment_id: Number(f.employment_id),
          course_id: Number(f.course_id),
          scheduled_on: f.scheduled_on,
        });
      onSaved(out?.budget?.exceeds ? out.budget.warning : undefined);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("nominate")}</h3>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="stack" style={{ gap: 12, marginTop: 16 }}>
        <label className="field">
          <span className="label">{L("employee")}</span>
          <select className="select" value={f.employment_id}
                  onChange={(e) => setF({ ...f,
                    employment_id: e.target.value })}>
            <option value="">—</option>
            {peers.map((p) => (
              <option key={p.employment_id} value={p.employment_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="label">{L("name")}</span>
          <select className="select" value={f.course_id}
                  onChange={(e) => setF({ ...f,
                    course_id: e.target.value })}>
            <option value="">—</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name_ar}{c.cost ? ` — ${c.cost}` : ""}
              </option>
            ))}
          </select>
          {course?.provider && (
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {course.provider}
            </span>
          )}
        </label>

        <div className="field">
          <label className="label">{L("scheduled")}</label>
          <DateField value={f.scheduled_on}
                     onChange={(v) => setF({ ...f, scheduled_on: v })} />
        </div>
      </div>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!f.employment_id || !f.course_id} />
    </Modal>
  );
}


function ResultDialog({ n, L, onClose, onSaved }: {
  n: Nom;
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [attended, setAttended] = useState(true);
  const [score, setScore] = useState("");
  const [passed, setPassed] = useState(true);
  const [cert, setCert] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/training/nominations/${n.id}/result/`, {
        attended, score: score || undefined,
        passed: attended ? passed : undefined,
        certificate_url: cert, note,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("resultTitle")}</h3>
      <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
        {n.employee} — {n.course}
      </div>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="row" style={{ gap: 6, marginTop: 16 }}>
        <button type="button"
                className={`btn btn-sm ${attended ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setAttended(true)}>{L("attended")}</button>
        <button type="button"
                className={`btn btn-sm ${!attended ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setAttended(false)}>{L("noShow")}</button>
      </div>

      {attended && (
        <>
          <div className="row" style={{ gap: 12, marginTop: 14,
                                        alignItems: "flex-end" }}>
            <label className="field" style={{ width: 130 }}>
              <span className="label">{L("score")}</span>
              <input className="input num" type="number" step="0.01"
                     value={score}
                     onChange={(e) => setScore(e.target.value)} />
            </label>
            <label className="row" style={{ gap: 7, cursor: "pointer",
                                            paddingBottom: 10 }}>
              <input type="checkbox" checked={passed}
                     onChange={(e) => setPassed(e.target.checked)} />
              <span>{L("passed")}</span>
            </label>
          </div>

          <label className="field" style={{ marginTop: 12 }}>
            <span className="label">{L("certificate")}</span>
            <input className="input" dir="ltr" value={cert}
                   placeholder="https://…"
                   onChange={(e) => setCert(e.target.value)} />
          </label>
        </>
      )}

      <label className="field" style={{ marginTop: 12 }}>
        <span className="label">{L("note")}</span>
        <input className="input" value={note}
               onChange={(e) => setNote(e.target.value)} />
      </label>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit} />
    </Modal>
  );
}


/* ══ عناصر مشتركة ══ */

function Modal({ children, onClose }: {
  children: React.ReactNode; onClose: () => void;
}) {
  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 480,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

function ErrBox({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: "var(--danger-soft)",
                  color: "var(--danger)", padding: "9px 12px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: ".86rem", marginTop: 14 }}>
      {children}
    </div>
  );
}

function Actions({ busy, disabled, L, onClose, onSubmit }: {
  busy: boolean; disabled?: boolean;
  L: (k: string, f?: string) => string;
  onClose: () => void; onSubmit: () => void;
}) {
  return (
    <div className="row" style={{ gap: 8, marginTop: 18 }}>
      <button className="btn btn-primary" disabled={busy || disabled}
              onClick={onSubmit}>{busy ? "…" : L("save")}</button>
      <button className="btn" onClick={onClose}>{L("cancel")}</button>
    </div>
  );
}

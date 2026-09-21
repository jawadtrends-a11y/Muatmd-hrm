"use client";
/**
 * تقييم الأداء (ق-146).
 *
 * ⚠️ **والمؤشّر لا يُقاس به قبل اعتماد الموارد**.
 */
import { useUrlTab } from "@/lib/useUrlTab";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تقييم الأداء", en: "Performance" },
  sub: {
    ar: "مؤشّرات إدارتك — وتعتمدها الموارد قبل القياس بها",
    en: "Your KPIs — approved by HR before use",
  },
  tabKpis: { ar: "المؤشّرات", en: "KPIs" },
  tabAssign: { ar: "الإسناد والإدخال", en: "Assignments" },
  tabCycles: { ar: "الدورات", en: "Cycles" },
  addKpi: { ar: "مؤشّر جديد", en: "New KPI" },
  addCycle: { ar: "دورة جديدة", en: "New cycle" },
  assign: { ar: "إسناد مؤشّر", en: "Assign KPI" },
  name: { ar: "المؤشّر", en: "KPI" },
  code: { ar: "الرمز", en: "Code" },
  dept: { ar: "الإدارة", en: "Department" },
  kind: { ar: "النوع", en: "Kind" },
  scale: { ar: "المقياس", en: "Scale" },
  direction: { ar: "الاتجاه", en: "Direction" },
  unit: { ar: "الوحدة", en: "Unit" },
  defTarget: { ar: "الهدف الافتراضيّ", en: "Default target" },
  descr: { ar: "التعريف", en: "Definition" },
  state: { ar: "الحالة", en: "Status" },
  approve: { ar: "اعتماد", en: "Approve" },
  reject: { ar: "رفض", en: "Reject" },
  employee: { ar: "الموظف", en: "Employee" },
  cycle: { ar: "الدورة", en: "Cycle" },
  target: { ar: "المستهدَف", en: "Target" },
  weight: { ar: "الوزن %", en: "Weight %" },
  actual: { ar: "الفعليّ", en: "Actual" },
  score: { ar: "الدرجة", en: "Score" },
  enterActual: { ar: "إدخال الفعليّ", en: "Enter actual" },
  scorecard: { ar: "البطاقة", en: "Scorecard" },
  scTitle: { ar: "بطاقة الأداء", en: "Scorecard" },
  scHint: {
    ar: "⚠️ تقريرٌ لا أثر ماليّ — والخلاصة تُعرض عند ثلاثة تقييمات حمايةً للهوية",
    en: "A report — no pay effect",
  },
  kpiScore: { ar: "درجة المؤشرات", en: "KPI score" },
  weightCovered: { ar: "الوزن المغطّى", en: "Weight covered" },
  behaviorAvg: { ar: "متوسط السلوك", en: "Behaviour" },
  noData: { ar: "لا بيانات بعد", en: "No data yet" },
  close2: { ar: "إغلاق", en: "Close" },
  weightHint: {
    ar: "⚠️ مجموع أوزان الموظف لا يتجاوز ١٠٠",
    en: "Total weights per employee cannot exceed 100",
  },
  approveHint: {
    ar: "⚠️ والمدخَل ليس نتيجةً قبل اعتماد الموارد",
    en: "Entries become results only after HR approval",
  },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  open: { ar: "مفتوحة", en: "Open" },
  closed: { ar: "مغلقة", en: "Closed" },
  selfReview: { ar: "تقييم ذاتيّ", en: "Self review" },
  upward: { ar: "تقييم المديرين", en: "Upward review" },
  upwardHint: {
    ar: "⚠️ مجهولٌ دائمًا — ولا يُنسب لصاحبه",
    en: "Always anonymous",
  },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا شيء بعد", en: "Nothing yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "تقييم الأداء غير متاح في باقتكم",
              en: "Not in your plan" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  pendingOnly: { ar: "بانتظار الاعتماد", en: "Pending" },
  all: { ar: "الكل", en: "All" },
};

type KPI = {
  id: number; code: string; name_ar: string; description: string;
  department: string; department_id: number;
  kind: string; kind_label: string;
  scale: string; scale_label: string;
  direction: string; direction_label: string;
  unit: string; default_target: string | null;
  state: string; state_label: string; decision_note: string;
  is_usable: boolean;
};
type Assign = {
  id: number; employee: string; employee_no: string;
  // ق-191: **رقم الارتباط** — فبطاقة الأداء تُفتح به
  employment_id: number; cycle_id: number;
  kpi: string;
  kpi_id: number; scale: string; unit: string;
  target: string; weight: number; actual: string | null;
  score: number | null; state: string; state_label: string;
};
type Cycle = {
  id: number; code: string; name_ar: string;
  start_date: string; end_date: string; is_open: boolean;
  self_review_enabled: boolean; upward_review_enabled: boolean;
};
type Opt = { value: string; label: string };
type Dept = { id: number; name_ar: string };
type Peer = { employment_id: number; name: string };

const TONE: Record<string, string> = {
  draft: "badge", pending: "badge-warn",
  approved: "badge-ok", rejected: "badge-danger",
};

export default function PerformancePage() {
  const { L } = useT(T);
  const [tab, setTab] = useUrlTab<"kpis" | "assign" | "cycles">(["kpis", "assign", "cycles"], "kpis");
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [assigns, setAssigns] = useState<Assign[]>([]);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [scales, setScales] = useState<Opt[]>([]);
  const [kinds, setKinds] = useState<Opt[]>([]);
  const [directions, setDirections] = useState<Opt[]>([]);
  const [depts, setDepts] = useState<Dept[]>([]);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [cycleId, setCycleId] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [dialog, setDialog] = useState<"kpi" | "cycle" | "assign" | null>(
    null);
  const [entering, setEntering] = useState<Assign | null>(null);
  // ق-191: **بطاقة الأداء** — ⚠️ **تقريرٌ لا أثر ماليّ**
  const [card, setCard] = useState<Assign | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [k, c, dir] = await Promise.all([
        apiGet<{ kpis: KPI[]; scales: Opt[]; kinds: Opt[];
                 directions: Opt[]; departments: Dept[] }>(
          "/performance/kpis/"),
        apiGet<Cycle[]>("/performance/cycles/"),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setKpis(k.kpis);
      setScales(k.scales);
      setKinds(k.kinds);
      setDirections(k.directions);
      setDepts(k.departments);
      setCycles(c);
      setPeers(dir.rows);
      if (!cycleId && c.length) setCycleId(String(c[0].id));

      const a = await apiGet<{ assignments: Assign[] }>(
        `/performance/assignments/?cycle_id=${cycleId || c[0]?.id || 0}`
        + (pendingOnly ? "&pending_approval=1" : ""));
      setAssigns(a.assignments);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [cycleId, pendingOnly]);

  useEffect(() => { load(); }, [load]);

  const decideKpi = async (k: KPI, approve: boolean) => {
    setActing(true); setErr("");
    try {
      const note = approve ? "" : (prompt(L("reject")) || "");
      await apiPost(`/performance/kpis/${k.id}/decide/`,
                    { approve, note });
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const approveActual = async (a: Assign) => {
    setActing(true); setErr("");
    try {
      await apiPost(`/performance/assignments/${a.id}/approve/`,
                    { approve: true });
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
                onClick={() => setDialog(
                  tab === "cycles" ? "cycle"
                  : tab === "assign" ? "assign" : "kpi")}>
          {tab === "cycles" ? L("addCycle")
            : tab === "assign" ? L("assign") : L("addKpi")}
        </button>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        {(["kpis", "assign", "cycles"] as const).map((t) => (
          <button key={t}
                  className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab(t)}>
            {t === "kpis" ? L("tabKpis")
              : t === "assign" ? L("tabAssign") : L("tabCycles")}
          </button>
        ))}
      </div>

      {tab === "kpis" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {kpis.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>
              <IcDoc size={22} />
              <div style={{ marginTop: 8 }}>{L("empty")}</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 140 }}>{L("dept")}</th>
                  <th style={{ width: 120 }}>{L("scale")}</th>
                  <th style={{ width: 120 }}>{L("direction")}</th>
                  <th style={{ width: 130 }}>{L("state")}</th>
                  <th style={{ width: 150 }} />
                </tr>
              </thead>
              <tbody>
                {kpis.map((k) => (
                  <tr key={k.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{k.name_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".75rem" }}>
                        {k.code}
                        {k.kind === "behavioral" && ` · ${k.kind_label}`}
                      </div>
                    </td>
                    <td className="muted">{k.department}</td>
                    <td className="muted">{k.scale_label}</td>
                    <td className="muted">{k.direction_label}</td>
                    <td>
                      <span className={`badge ${TONE[k.state] || "badge"}`}>
                        {k.state_label}
                      </span>
                      {k.decision_note && (
                        <div className="muted"
                             style={{ fontSize: ".73rem" }}>
                          {k.decision_note}
                        </div>
                      )}
                    </td>
                    <td>
                      {k.state === "pending" && (
                        <div className="row" style={{ gap: 5 }}>
                          <button className="btn btn-sm btn-primary"
                                  disabled={acting}
                                  onClick={() => decideKpi(k, true)}>
                            {L("approve")}
                          </button>
                          <button className="btn btn-sm btn-danger"
                                  disabled={acting}
                                  onClick={() => decideKpi(k, false)}>
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

      {tab === "assign" && (
        <>
          <div className="row" style={{ gap: 10, flexWrap: "wrap",
                                        alignItems: "flex-end" }}>
            <label className="field" style={{ width: 220 }}>
              <span className="label">{L("cycle")}</span>
              <select className="select" value={cycleId}
                      onChange={(e) => setCycleId(e.target.value)}>
                {cycles.map((c) => (
                  <option key={c.id} value={c.id}>{c.name_ar}</option>
                ))}
              </select>
            </label>
            <button className={`btn btn-sm ${pendingOnly ? "btn-primary" : "btn-ghost"}`}
                    style={{ marginBottom: 2 }}
                    onClick={() => setPendingOnly(!pendingOnly)}>
              {pendingOnly ? L("pendingOnly") : L("all")}
            </button>
          </div>

          <div className="muted" style={{ fontSize: ".82rem" }}>
            {L("approveHint")}
          </div>

          <div className="card" style={{ overflow: "hidden" }}>
            {assigns.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center",
                            color: "var(--ink-3)" }}>
                {L("empty")}
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 160 }}>{L("employee")}</th>
                      <th>{L("name")}</th>
                      <th style={{ width: 95 }}>{L("target")}</th>
                      <th style={{ width: 85 }}>{L("weight")}</th>
                      <th style={{ width: 95 }}>{L("actual")}</th>
                      <th style={{ width: 90 }}>{L("score")}</th>
                      <th style={{ width: 120 }}>{L("state")}</th>
                      <th style={{ width: 130 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {assigns.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <div style={{ fontWeight: 500 }}>
                            {a.employee}
                          </div>
                          <div className="muted num"
                               style={{ fontSize: ".73rem" }}>
                            {a.employee_no}
                          </div>
                        </td>
                        <td className="muted">{a.kpi}</td>
                        <td><span className="num">{a.target}</span></td>
                        <td><span className="num">{a.weight}</span></td>
                        <td>
                          {a.actual !== null
                            ? <span className="num">{a.actual}</span>
                            : <span className="muted">—</span>}
                        </td>
                        <td>
                          {a.score !== null ? (
                            <span className="num" style={{
                              color: a.score >= 100 ? "var(--ok)"
                                : a.score >= 70 ? undefined
                                : "var(--danger)" }}>
                              {a.score}
                            </span>
                          ) : <span className="muted">—</span>}
                        </td>
                        <td>
                          <span className={`badge ${TONE[a.state] || "badge"}`}>
                            {a.state_label}
                          </span>
                        </td>
                        <td>
                          <div className="row" style={{ gap: 5 }}>
                            {/* ق-191: **بطاقة الأداء** — فالمسار
                                كان يتيمًا */}
                            <button className="btn btn-sm btn-ghost"
                                    onClick={() => setCard(a)}>
                              {L("scorecard")}
                            </button>
                            {a.state !== "approved" && (
                              <button className="btn btn-sm"
                                      onClick={() => setEntering(a)}>
                                {L("enterActual")}
                              </button>
                            )}
                            {a.state === "pending"
                              && a.actual !== null && (
                              <button className="btn btn-sm btn-primary"
                                      disabled={acting}
                                      onClick={() => approveActual(a)}>
                                {L("approve")}
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
        </>
      )}

      {tab === "cycles" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {cycles.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>{L("empty")}</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("cycle")}</th>
                  <th style={{ width: 220 }}>{L("from")} — {L("to")}</th>
                  <th style={{ width: 220 }} />
                  <th style={{ width: 110 }}>{L("state")}</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{c.name_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>{c.code}</div>
                    </td>
                    <td>
                      <span className="num" style={{ fontSize: ".83rem" }}>
                        {c.start_date} → {c.end_date}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5,
                                                    flexWrap: "wrap" }}>
                        {c.self_review_enabled && (
                          <span className="badge"
                                style={{ fontSize: ".7rem" }}>
                            {L("selfReview")}
                          </span>
                        )}
                        {c.upward_review_enabled && (
                          <span className="badge"
                                style={{ fontSize: ".7rem" }}>
                            {L("upward")}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <button className={`btn btn-sm ${c.is_open ? "btn-ghost" : ""}`}
                              onClick={async () => {
                                await apiPut(
                                  `/performance/cycles/${c.id}/`,
                                  { is_open: !c.is_open });
                                await load();
                              }}>
                        {c.is_open ? L("open") : L("closed")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {dialog === "kpi" && (
        <KpiDialog depts={depts} scales={scales} kinds={kinds}
                   directions={directions} L={L}
                   onClose={() => setDialog(null)}
                   onSaved={async () => {
                     setDialog(null);
                     setMsg(L("savedOk"));
                     setTimeout(() => setMsg(""), 3000);
                     await load();
                   }} />
      )}

      {dialog === "cycle" && (
        <CycleDialog L={L} onClose={() => setDialog(null)}
                     onSaved={async () => {
                       setDialog(null);
                       setMsg(L("savedOk"));
                       setTimeout(() => setMsg(""), 3000);
                       await load();
                     }} />
      )}

      {dialog === "assign" && (
        <AssignDialog cycles={cycles} kpis={kpis.filter((k) => k.is_usable)}
                      peers={peers} L={L}
                      onClose={() => setDialog(null)}
                      onSaved={async () => {
                        setDialog(null);
                        setMsg(L("savedOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}
      {card && (
        <ScorecardDialog a={card} L={L}
                         onClose={() => setCard(null)} />
      )}


      {entering && (
        <ActualDialog a={entering} L={L}
                      onClose={() => setEntering(null)}
                      onSaved={async () => {
                        setEntering(null);
                        setMsg(L("savedOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}
    </div>
  );
}


function KpiDialog({ depts, scales, kinds, directions, L,
                     onClose, onSaved }: {
  depts: Dept[]; scales: Opt[]; kinds: Opt[]; directions: Opt[];
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    department_id: "", code: "", name_ar: "", description: "",
    kind: "quantitative", scale: "percent", direction: "higher",
    unit: "", default_target: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/performance/kpis/", {
        ...f, department_id: Number(f.department_id),
        default_target: f.default_target || undefined,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("addKpi")}</h3>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="stack" style={{ gap: 12, marginTop: 16 }}>
        <label className="field">
          <span className="label">{L("dept")}</span>
          <select className="select" value={f.department_id}
                  onChange={(e) => setF({ ...f,
                    department_id: e.target.value })}>
            <option value="">—</option>
            {depts.map((d) => (
              <option key={d.id} value={d.id}>{d.name_ar}</option>
            ))}
          </select>
        </label>

        <div className="row" style={{ gap: 12 }}>
          <label className="field" style={{ width: 130 }}>
            <span className="label">{L("code")}</span>
            <input className="input" dir="ltr" value={f.code}
                   onChange={(e) => setF({ ...f,
                     code: e.target.value.trim().toUpperCase() })} />
          </label>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("kind")}</span>
            <select className="select" value={f.kind}
                    onChange={(e) => setF({ ...f, kind: e.target.value })}>
              {kinds.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("scale")}</span>
            <select className="select" value={f.scale}
                    onChange={(e) => setF({ ...f,
                      scale: e.target.value })}>
              {scales.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="row" style={{ gap: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("direction")}</span>
            <select className="select" value={f.direction}
                    onChange={(e) => setF({ ...f,
                      direction: e.target.value })}>
              {directions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          {f.scale === "count" && (
            <label className="field" style={{ width: 120 }}>
              <span className="label">{L("unit")}</span>
              <input className="input" value={f.unit}
                     onChange={(e) => setF({ ...f,
                       unit: e.target.value })} />
            </label>
          )}
          <label className="field" style={{ width: 130 }}>
            <span className="label">{L("defTarget")}</span>
            <input className="input num" type="number" step="0.01"
                   value={f.default_target}
                   onChange={(e) => setF({ ...f,
                     default_target: e.target.value })} />
          </label>
        </div>

        <label className="field">
          <span className="label">{L("descr")}</span>
          <textarea className="input" rows={2} value={f.description}
                    onChange={(e) => setF({ ...f,
                      description: e.target.value })} />
        </label>
      </div>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!f.department_id || !f.code || !f.name_ar} />
    </Modal>
  );
}


function CycleDialog({ L, onClose, onSaved }: {
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const y = new Date().getFullYear();
  const [f, setF] = useState({
    code: "", name_ar: "",
    start_date: `${y}-01-01`, end_date: `${y}-12-31`,
    self_review_enabled: true, upward_review_enabled: true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/performance/cycles/", f);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("addCycle")}</h3>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="row" style={{ gap: 12, marginTop: 16 }}>
        <label className="field" style={{ width: 130 }}>
          <span className="label">{L("code")}</span>
          <input className="input" dir="ltr" value={f.code}
                 onChange={(e) => setF({ ...f,
                   code: e.target.value.trim().toUpperCase() })} />
        </label>
        <label className="field" style={{ flex: 1 }}>
          <span className="label">{L("cycle")}</span>
          <input className="input" value={f.name_ar}
                 onChange={(e) => setF({ ...f,
                   name_ar: e.target.value })} />
        </label>
      </div>

      <div className="row" style={{ gap: 12, marginTop: 12 }}>
        <div className="field" style={{ flex: 1 }}>
          <label className="label">{L("from")}</label>
          <DateField value={f.start_date}
                     onChange={(v) => setF({ ...f, start_date: v })} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label className="label">{L("to")}</label>
          <DateField value={f.end_date}
                     onChange={(v) => setF({ ...f, end_date: v })} />
        </div>
      </div>

      <label className="row" style={{ gap: 8, marginTop: 14,
                                      cursor: "pointer" }}>
        <input type="checkbox" checked={f.self_review_enabled}
               onChange={(e) => setF({ ...f,
                 self_review_enabled: e.target.checked })} />
        <span>{L("selfReview")}</span>
      </label>

      <label className="row" style={{ gap: 8, marginTop: 10,
                                      cursor: "pointer",
                                      alignItems: "flex-start" }}>
        <input type="checkbox" checked={f.upward_review_enabled}
               style={{ marginTop: 3 }}
               onChange={(e) => setF({ ...f,
                 upward_review_enabled: e.target.checked })} />
        <span>
          {L("upward")}
          <div className="muted" style={{ fontSize: ".78rem" }}>
            {L("upwardHint")}
          </div>
        </span>
      </label>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!f.code || !f.name_ar} />
    </Modal>
  );
}


function AssignDialog({ cycles, kpis, peers, L, onClose, onSaved }: {
  cycles: Cycle[]; kpis: KPI[]; peers: Peer[];
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    cycle_id: cycles[0] ? String(cycles[0].id) : "",
    employment_id: "", kpi_id: "", target: "", weight: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const kpi = kpis.find((k) => String(k.id) === f.kpi_id);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/performance/assignments/", {
        cycle_id: Number(f.cycle_id),
        employment_id: Number(f.employment_id),
        kpi_id: Number(f.kpi_id),
        target: f.target, weight: Number(f.weight),
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("assign")}</h3>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="stack" style={{ gap: 12, marginTop: 16 }}>
        <label className="field">
          <span className="label">{L("cycle")}</span>
          <select className="select" value={f.cycle_id}
                  onChange={(e) => setF({ ...f,
                    cycle_id: e.target.value })}>
            {cycles.map((c) => (
              <option key={c.id} value={c.id}>{c.name_ar}</option>
            ))}
          </select>
        </label>

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
          <select className="select" value={f.kpi_id}
                  onChange={(e) => setF({ ...f, kpi_id: e.target.value,
                    target: kpis.find((k) =>
                      String(k.id) === e.target.value
                    )?.default_target || f.target })}>
            <option value="">—</option>
            {kpis.map((k) => (
              <option key={k.id} value={k.id}>{k.name_ar}</option>
            ))}
          </select>
        </label>

        <div className="row" style={{ gap: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">
              {L("target")}
              {kpi?.unit && (
                <span className="muted"> ({kpi.unit})</span>
              )}
            </span>
            <input className="input num" type="number" step="0.01"
                   value={f.target}
                   onChange={(e) => setF({ ...f,
                     target: e.target.value })} />
          </label>
          <label className="field" style={{ width: 130 }}>
            <span className="label">{L("weight")}</span>
            <input className="input num" type="number" min={1} max={100}
                   value={f.weight}
                   onChange={(e) => setF({ ...f,
                     weight: e.target.value })} />
          </label>
        </div>
        <div className="muted" style={{ fontSize: ".78rem",
                                        marginTop: -6 }}>
          {L("weightHint")}
        </div>
      </div>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!f.cycle_id || !f.employment_id || !f.kpi_id
                         || !f.target || !f.weight} />
    </Modal>
  );
}


function ActualDialog({ a, L, onClose, onSaved }: {
  a: Assign;
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [actual, setActual] = useState(a.actual || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/performance/assignments/${a.id}/actual/`,
                    { actual, note });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("enterActual")}</h3>
      <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
        {a.employee} — {a.kpi}
      </div>
      {err && <ErrBox>{err}</ErrBox>}

      <div className="row" style={{ gap: 12, marginTop: 16 }}>
        <label className="field" style={{ width: 150 }}>
          <span className="label">{L("actual")}</span>
          <input className="input num" type="number" step="0.01"
                 value={actual}
                 onChange={(e) => setActual(e.target.value)} />
        </label>
        <div style={{ paddingBottom: 8 }}>
          <div className="muted" style={{ fontSize: ".78rem" }}>
            {L("target")}
          </div>
          <div className="num">{a.target} {a.unit}</div>
        </div>
      </div>

      <label className="field" style={{ marginTop: 12 }}>
        <span className="label">{L("descr")}</span>
        <input className="input" value={note}
               onChange={(e) => setNote(e.target.value)} />
      </label>

      <Actions busy={busy} L={L} onClose={onClose} onSubmit={submit}
               disabled={!actual} />
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
      <div className="card" style={{ padding: 24, maxWidth: 490,
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


/**
 * بطاقة أداء موظفٍ في دورة (ق-191).
 *
 * ⚠️⚠️ **وتقريرٌ لا أثر ماليّ**: فالمسار كان **مبنيًّا بلا شاشة**
 * — كشفه الجرد.
 *
 * ⚠️ **والخلاصة تُعرض عند ثلاثة تقييمات** حمايةً للهوية (ق-146).
 */
function ScorecardDialog({ a, L, onClose }: {
  a: Assign; L: (k: string) => string; onClose: () => void;
}) {
  type Card = {
    kpi_score: number | null;
    weight_covered: number;
    behavior_average: number | null;
    affects_pay: boolean;
    employee: string;
    cycle: string;
    self_review: { comment?: string } | null;
    upward: { count: number; average: number | null;
              comments: string[]; note?: string } | null;
    details: { kpi: string; target: string; actual: string | null;
               weight: number; score: number | null }[];
  };

  const [d, setD] = useState<Card | null>(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiGet<Card>(
      `/performance/scorecard/${a.employment_id}/${qs({
        cycle_id: a.cycle_id })}`)
      .then(setD)
      .catch((e) => setErr(e instanceof ApiError ? e.message
                                                 : String(e)))
      .finally(() => setBusy(false));
  }, [a]);

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 60,
      background: "rgba(16,28,38,.45)", display: "grid",
      placeItems: "center", padding: 16,
    }}>
      <div className="card" style={{
        padding: 22, maxWidth: 560, width: "100%",
        maxHeight: "88vh", overflowY: "auto",
      }}>
        <div className="spread" style={{ marginBottom: 4 }}>
          <h3 style={{ margin: 0 }}>{L("scTitle")}</h3>
          <button className="btn btn-sm btn-ghost" onClick={onClose}>
            {L("close2")}
          </button>
        </div>

        <div className="muted" style={{ fontSize: ".78rem",
                                        lineHeight: 1.9,
                                        marginBottom: 16 }}>
          {L("scHint")}
        </div>

        {busy ? (
          <div className="muted" style={{ padding: 20,
                                          textAlign: "center" }}>…</div>
        ) : err ? (
          <div className="card" style={{ borderColor: "var(--danger)",
                                         color: "var(--danger)" }}>
            {err}
          </div>
        ) : d ? (
          <>
            <div style={{ marginBottom: 14 }}>
              <strong>{d.employee}</strong>
              <div className="muted" style={{ fontSize: ".8rem" }}>
                {d.cycle}
              </div>
            </div>

            <div style={{
              display: "grid", gap: 12,
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            }}>
              <Box label={L("kpiScore")}
                   value={d.kpi_score == null ? "—"
                                              : String(d.kpi_score)} />
              <Box label={L("weightCovered")}
                   value={`${d.weight_covered}`} />
              <Box label={L("behaviorAvg")}
                   value={d.behavior_average == null ? "—"
                     : String(d.behavior_average)} />
            </div>

            {d.details?.length > 0 && (
              <table className="table" style={{ marginTop: 16 }}>
                <thead>
                  <tr>
                    <th>{L("kpi")}</th>
                    <th style={{ width: 80 }}>{L("target")}</th>
                    <th style={{ width: 80 }}>{L("actual")}</th>
                    <th style={{ width: 70 }}>{L("weight")}</th>
                  </tr>
                </thead>
                <tbody>
                  {d.details.map((x, i) => (
                    <tr key={i}>
                      <td>{x.kpi}</td>
                      <td><span className="num">{x.target}</span></td>
                      <td>
                        <span className="num">{x.actual ?? "—"}</span>
                      </td>
                      <td><span className="num">{x.weight}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* ⚠️ **وتقييم المرؤوسين مجهول** — والخلاصة تُحجب دون
                ثلاثة (ق-146) */}
            {d.upward && (
              <div style={{ marginTop: 16, padding: "12px 14px",
                            background: "var(--paper-2)",
                            borderRadius: "var(--radius-sm)" }}>
                <div className="spread">
                  <strong style={{ fontSize: ".9rem" }}>
                    {L("upward")}
                  </strong>
                  <span className="num">
                    {d.upward.average ?? "—"}
                    <span className="muted"
                          style={{ fontSize: ".76rem",
                                   marginInlineStart: 6 }}>
                      ({d.upward.count})
                    </span>
                  </span>
                </div>
                {d.upward.note && (
                  <div className="muted" style={{ fontSize: ".76rem",
                                                  marginTop: 5 }}>
                    {d.upward.note}
                  </div>
                )}
              </div>
            )}

            {d.self_review?.comment && (
              <div style={{ marginTop: 12 }}>
                <strong style={{ fontSize: ".88rem" }}>
                  {L("selfReview")}
                </strong>
                <div className="muted" style={{ fontSize: ".84rem",
                                                marginTop: 4,
                                                lineHeight: 1.9 }}>
                  {d.self_review.comment}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="muted">{L("noData")}</div>
        )}
      </div>
    </div>
  );
}


function Box({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "10px 12px", background: "var(--paper-2)",
                  borderRadius: "var(--radius-sm)" }}>
      <div className="muted" style={{ fontSize: ".74rem",
                                      marginBottom: 3 }}>
        {label}
      </div>
      <div className="num" style={{ fontWeight: 600 }}>{value}</div>
    </div>
  );
}

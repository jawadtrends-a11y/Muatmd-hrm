"use client";
/**
 * الجزاءات التأديبية (ق-119، ق-121).
 *
 * **السجلّ يعرض المخالف والمسؤول يوقّع بضغطة** — فما لا يُعرض لا
 * يُطبَّق، ولا يفتح أحدٌ شاشةً ليبحث عن مخالف.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الجزاءات", en: "Penalties" },
  sub: {
    ar: "مخالفات لم يُوقَّع عليها — راجعها ووقّع ما تراه",
    en: "Unsigned violations — review and apply",
  },
  tabBoard: { ar: "المقترحة", en: "Pending" },
  tabRegister: { ar: "صحيفة الجزاءات", en: "Register" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  employee: { ar: "الموظف", en: "Employee" },
  date: { ar: "التاريخ", en: "Date" },
  state: { ar: "الحالة", en: "State" },
  minutes: { ar: "الدقائق", en: "Minutes" },
  timeDed: { ar: "حسم الوقت", en: "Time deduction" },
  action: { ar: "إجراء", en: "Action" },
  apply: { ar: "توقيع الجزاء", en: "Apply" },
  applyAll: { ar: "توقيع كل السجلّ", en: "Apply all" },
  applying: { ar: "جارٍ التوقيع…", en: "Applying…" },
  empty: { ar: "لا مخالفات في هذه المدّة", en: "No violations in range" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك عرض الجزاءات", en: "Not permitted" },
  violation: { ar: "المخالفة", en: "Violation" },
  kind: { ar: "الجزاء", en: "Penalty" },
  days: { ar: "الأيام", en: "Days" },
  amount: { ar: "المبلغ", en: "Amount" },
  occurrence: { ar: "التكرار", en: "Occurrence" },
  status: { ar: "الحالة", en: "Status" },
  dlgTitle: { ar: "توقيع الجزاء", en: "Apply penalty" },
  dlgIntro: {
    ar: "الجزاء المقترح من لائحتكم — راجعه قبل التوقيع",
    en: "Suggested from your policy — review before applying",
  },
  fViolation: { ar: "المخالفة", en: "Violation" },
  fDesc: { ar: "وصف الواقعة", en: "Description" },
  fStatement: { ar: "إفادة الموظف", en: "Employee statement" },
  stmtHint: {
    ar: "ما تجاوز أجر يوم يلزمه سماع أقواله وإثباتها",
    en: "Above one day's wage requires a recorded statement",
  },
  fApply: { ar: "طبّق الخصم", en: "Apply deduction" },
  fCount: { ar: "احتسب في التكرار", en: "Count as repeat" },
  countHint: {
    ar: "غير المحتسَب لا يرفع درجته في المخالفة القادمة",
    en: "Uncounted repeats do not escalate",
  },
  fOccurrence: { ar: "عدد مرات التكرار", en: "Occurrence" },
  occHint: {
    ar: "محسوب تلقائيًّا — يمكنك تعديله",
    en: "Calculated automatically — editable",
  },
  go: { ar: "توقيع", en: "Apply" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  cap: { ar: "تنبيه السقف", en: "Cap notice" },
  done: { ar: "وُقّع {n} جزاءً", en: "{n} applied" },
  someFailed: { ar: "وتعذّر {n}", en: "{n} failed" },
};

type Row = {
  employment_id: number; employee_no: string; name: string;
  date: string; state: string; attendance_status: string;
  minutes: number; time_deduction: string;
};
type Violation = {
  id: number; code: string; name_ar: string; financial_effect: boolean;
};
type Preview = {
  occurrence: number; suggested_occurrence: number;
  kind_label: string; days: string; amount: string;
  deductible: boolean; block_reason: string; capped: boolean;
  cap_note: string; deducted_this_month: string; monthly_cap: string;
};
type RegRow = {
  id: number; name: string; employee_no: string; violation: string;
  occurred_on: string; occurrence: number; kind_label: string;
  days: string; amount: string; status_label: string;
  applied: boolean; counted: boolean;
};

const monthStart = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};

export default function PenaltiesPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"board" | "register">("board");
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<Row[]>([]);
  const [reg, setReg] = useState<RegRow[]>([]);
  const [vios, setVios] = useState<Violation[]>([]);
  const [perms, setPerms] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [acting, setActing] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState<Row | null>(null);

  const canView = perms.includes("attendance.view")
    || perms.includes("employees.view");
  const canEdit = perms.includes("employees.edit");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      const [b, v, r] = await Promise.all([
        apiGet<{ rows: Row[] }>(
          `/penalties/board/?from=${from}&to=${to}`).catch(() => ({ rows: [] })),
        apiGet<{ violations: Violation[] }>("/penalties/violations/")
          .catch(() => ({ violations: [] })),
        apiGet<RegRow[]>("/penalties/").catch(() => []),
      ]);
      setRows(b.rows || []);
      setVios(v.violations || []);
      setReg(r);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [from, to]);

  useEffect(() => { load(); }, [load]);

  const applyAll = async () => {
    setActing(true); setErr("");
    try {
      const out = await apiPost<{ issued: number; failed: unknown[] }>(
        "/penalties/issue-batch/",
        { rows, employee_statement: "" });
      setMsg(L("done").replace("{n}", String(out.issued))
        + (out.failed.length
          ? " — " + L("someFailed").replace("{n}", String(out.failed.length))
          : ""));
      setTimeout(() => setMsg(""), 6000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  if (busy) return <div className="card" style={{ padding: 40,
    textAlign: "center", color: "var(--ink-3)" }}>{L("loading")}</div>;

  if (!canView) return (
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
        {tab === "board" && canEdit && rows.length > 0 && (
          <button className="btn btn-primary" disabled={acting}
                  onClick={applyAll}>
            {acting ? L("applying") : L("applyAll")}
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
        <button className={`btn btn-sm ${tab === "board" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("board")}>{L("tabBoard")}</button>
        <button className={`btn btn-sm ${tab === "register" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("register")}>{L("tabRegister")}</button>
      </div>

      {tab === "board" && (
        <>
          <div className="card" style={{ padding: 16 }}>
            <div className="row" style={{ gap: 14, flexWrap: "wrap",
                                          alignItems: "flex-end" }}>
              <div className="field" style={{ minWidth: 160 }}>
                <label className="label">{L("from")}</label>
                <DateField value={from} onChange={setFrom} />
              </div>
              <div className="field" style={{ minWidth: 160 }}>
                <label className="label">{L("to")}</label>
                <DateField value={to} onChange={setTo} />
              </div>
            </div>
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
                      <th>{L("employee")}</th>
                      <th style={{ width: 120 }}>{L("date")}</th>
                      <th>{L("state")}</th>
                      <th style={{ width: 90 }}>{L("minutes")}</th>
                      <th style={{ width: 120 }}>{L("timeDed")}</th>
                      {canEdit && <th style={{ width: 140 }} />}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={`${r.employment_id}-${r.date}-${i}`}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{r.name}</div>
                          <div className="muted num"
                               style={{ fontSize: ".76rem" }}>
                            {r.employee_no}
                          </div>
                        </td>
                        <td><span className="num">{r.date}</span></td>
                        <td>
                          <span className="badge badge-warn">{r.state}</span>
                        </td>
                        <td><span className="num">{r.minutes || "—"}</span></td>
                        <td><span className="num">{r.time_deduction}</span></td>
                        {canEdit && (
                          <td>
                            <button className="btn btn-sm"
                                    onClick={() => { setDlg(r); setErr(""); }}>
                              {L("apply")}
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {tab === "register" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {reg.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>{L("empty")}</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>{L("employee")}</th>
                    <th>{L("violation")}</th>
                    <th style={{ width: 110 }}>{L("date")}</th>
                    <th style={{ width: 80 }}>{L("occurrence")}</th>
                    <th>{L("kind")}</th>
                    <th style={{ width: 80 }}>{L("days")}</th>
                    <th style={{ width: 110 }}>{L("amount")}</th>
                    <th style={{ width: 90 }}>{L("status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {reg.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{p.name}</div>
                        <div className="muted num"
                             style={{ fontSize: ".76rem" }}>{p.employee_no}</div>
                      </td>
                      <td className="truncate">{p.violation}</td>
                      <td><span className="num">{p.occurred_on}</span></td>
                      <td><span className="num">{p.occurrence}</span></td>
                      <td className="muted">{p.kind_label}</td>
                      <td><span className="num">{p.days}</span></td>
                      <td>
                        <span className="num">
                          {p.applied ? p.amount : "—"}
                        </span>
                      </td>
                      <td>
                        <span className="badge">{p.status_label}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {dlg && (
        <ApplyDialog row={dlg} vios={vios} L={L}
                     onClose={() => setDlg(null)}
                     onDone={async () => { setDlg(null); await load(); }} />
      )}
    </div>
  );
}


/* ══ نافذة التوقيع ══ */

function ApplyDialog({ row, vios, L, onClose, onDone }: {
  row: Row;
  vios: Violation[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [vid, setVid] = useState<string>(String(vios[0]?.id || ""));
  const [desc, setDesc] = useState(`${row.state} — ${row.minutes} دقيقة`);
  const [stmt, setStmt] = useState("");
  const [apply, setApply] = useState(true);
  const [count, setCount] = useState(true);
  const [occ, setOcc] = useState<string>("");
  const [pv, setPv] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!vid) return;
    apiPost<Preview>("/penalties/preview/", {
      employment_id: row.employment_id,
      violation_id: Number(vid),
      occurred_on: row.date,
      occurrence: occ ? Number(occ) : undefined,
    }).then(setPv).catch(() => setPv(null));
  }, [vid, row, occ]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/penalties/issue/", {
        employment_id: row.employment_id,
        violation_id: Number(vid),
        occurred_on: row.date,
        description: desc,
        employee_statement: stmt,
        apply_deduction: apply,
        count_occurrence: count,
        occurrence: occ ? Number(occ) : undefined,
      });
      onDone();
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
      <div className="card" style={{ padding: 24, maxWidth: 520,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("dlgTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {row.name} · {row.date} · {row.state} — {L("dlgIntro")}
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
            <span className="label">{L("fViolation")}</span>
            <select className="select" value={vid}
                    onChange={(e) => setVid(e.target.value)}>
              {vios.map((v) => (
                <option key={v.id} value={v.id}>{v.name_ar}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">{L("fOccurrence")}</span>
            <input className="input num" type="number" min={1}
                   placeholder={pv ? String(pv.suggested_occurrence) : ""}
                   value={occ}
                   onChange={(e) => setOcc(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("occHint")}
            </span>
          </label>

          {pv && (
            <div style={{ padding: "10px 14px",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--paper-2)",
                          fontSize: ".85rem", display: "grid", gap: 4 }}>
              <div className="spread">
                <span className="muted">{L("occurrence")}</span>
                <span className="num">{pv.occurrence}</span>
              </div>
              <div className="spread">
                <span className="muted">{L("kind")}</span>
                <span>{pv.kind_label}</span>
              </div>
              <div className="spread">
                <span className="muted">{L("days")}</span>
                <span className="num">{pv.days}</span>
              </div>
              <div className="spread" style={{ fontWeight: 600 }}>
                <span>{L("amount")}</span>
                <span className="num">{pv.amount}</span>
              </div>
              {(pv.cap_note || pv.block_reason) && (
                <div style={{ color: "var(--copper)", fontSize: ".8rem",
                              marginTop: 4 }}>
                  {pv.cap_note || pv.block_reason}
                </div>
              )}
            </div>
          )}

          <label className="field">
            <span className="label">{L("fDesc")}</span>
            <input className="input" value={desc}
                   onChange={(e) => setDesc(e.target.value)} />
          </label>

          <label className="field">
            <span className="label">{L("fStatement")}</span>
            <textarea className="input" rows={3} value={stmt}
                      onChange={(e) => setStmt(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("stmtHint")}
            </span>
          </label>

          <label className="row" style={{ gap: 8, cursor: "pointer",
                                          fontSize: ".88rem" }}>
            <input type="checkbox" checked={apply}
                   onChange={(e) => setApply(e.target.checked)} />
            <span>{L("fApply")}</span>
          </label>

          <label className="row" style={{ gap: 8, cursor: "pointer",
                                          fontSize: ".88rem",
                                          alignItems: "flex-start" }}>
            <input type="checkbox" checked={count} style={{ marginTop: 3 }}
                   onChange={(e) => setCount(e.target.checked)} />
            <span>
              {L("fCount")}
              <div className="muted" style={{ fontSize: ".78rem" }}>
                {L("countHint")}
              </div>
            </span>
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy || !vid}
                  onClick={submit}>
            {busy ? "…" : L("go")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
